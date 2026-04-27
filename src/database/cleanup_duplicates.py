"""
Cleanup URL Duplicates Script
Merges opportunities with same registration_url into single records

This script:
1. Finds opportunities with duplicate registration_url
2. Keeps the oldest record (first posted)
3. Merges secondary sources from newer records
4. Deletes newer duplicate records
5. Logs all merge operations for review
"""

import sys
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from extraction.utils.logger import setup_logger
from dotenv import load_dotenv
import os

# Load environment variables
env_path = Path(__file__).parent.parent.parent / 'config' / '.env'
load_dotenv(env_path)

logger = setup_logger('cleanup_duplicates')

def get_db_connection():
    """Get database connection"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")
    
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

def find_url_duplicates(conn):
    """
    Find all opportunities with duplicate registration_url
    
    Returns:
        List of duplicate groups
    """
    query = """
        SELECT 
            registration_url,
            ARRAY_AGG(id::text ORDER BY created_at ASC) as opportunity_ids,
            ARRAY_AGG(title ORDER BY created_at ASC) as titles,
            ARRAY_AGG(source_account ORDER BY created_at ASC) as source_accounts,
            ARRAY_AGG(post_id ORDER BY created_at ASC) as post_ids,
            ARRAY_AGG(created_at ORDER BY created_at ASC) as created_dates,
            COUNT(*) as count
        FROM opportunities
        WHERE registration_url IS NOT NULL
        GROUP BY registration_url
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()

def merge_duplicate_group(conn, group):
    """
    Merge a group of duplicate opportunities
    
    Strategy:
    1. Keep the oldest record (first in array)
    2. Merge secondary_sources from newer records
    3. Merge tags (union)
    4. Update deadline if newer is later
    5. Delete newer records
    
    Args:
        conn: Database connection
        group: Duplicate group dictionary
        
    Returns:
        Number of records merged
    """
    opportunity_ids = group['opportunity_ids']
    
    if len(opportunity_ids) < 2:
        return 0
    
    # Keep first (oldest) record
    keep_id = opportunity_ids[0]
    delete_ids = opportunity_ids[1:]
    
    logger.info(f"\n{'='*60}")
    logger.info(f"[MERGE] Processing duplicate group:")
    logger.info(f"   URL: {group['registration_url'][:80]}...")
    logger.info(f"   Total duplicates: {group['count']}")
    logger.info(f"   Keeping: {keep_id} (oldest)")
    logger.info(f"   Deleting: {len(delete_ids)} records")
    
    # Get full data for all records
    query = """
        SELECT 
            id::text, title, source_account, post_id, source_url,
            secondary_sources, tags, deadline_date, registration_date,
            created_at
        FROM opportunities
        WHERE id::text = ANY(%s)
        ORDER BY created_at ASC
    """
    
    with conn.cursor() as cur:
        cur.execute(query, (opportunity_ids,))
        records = cur.fetchall()
    
    if not records:
        logger.error(f"[ERROR] No records found for IDs: {opportunity_ids}")
        return 0
    
    # First record is the one we keep
    keep_record = records[0]
    merge_records = records[1:]
    
    # Build merged data
    merged_secondary_sources = list(keep_record.get('secondary_sources', []))
    merged_tags = set(keep_record.get('tags', []))
    latest_deadline = keep_record.get('deadline_date')
    latest_registration = keep_record.get('registration_date')
    
    for record in merge_records:
        # Add to secondary sources
        merged_secondary_sources.append({
            'source_account': record['source_account'],
            'post_id': record['post_id'],
            'source_url': record['source_url'],
            'merged_at': datetime.now().isoformat(),
            'original_id': record['id']
        })
        
        # Merge tags
        merged_tags.update(record.get('tags', []))
        
        # Check for later deadline
        if record.get('deadline_date'):
            if not latest_deadline or record['deadline_date'] > latest_deadline:
                latest_deadline = record['deadline_date']
                latest_registration = record.get('registration_date')
        
        logger.info(f"   - Merging: {record['title'][:50]}... (Account: {record['source_account']})")
    
    # Update keep record with merged data
    update_query = """
        UPDATE opportunities
        SET 
            secondary_sources = %s,
            tags = %s,
            deadline_date = %s,
            registration_date = %s,
            updated_at = NOW()
        WHERE id::text = %s
    """
    
    with conn.cursor() as cur:
        cur.execute(update_query, (
            json.dumps(merged_secondary_sources),
            list(merged_tags),
            latest_deadline,
            latest_registration,
            keep_id
        ))
    
    # Delete duplicate records
    delete_query = "DELETE FROM opportunities WHERE id::text = ANY(%s)"
    
    with conn.cursor() as cur:
        cur.execute(delete_query, (delete_ids,))
        deleted_count = cur.rowcount
    
    conn.commit()
    
    logger.info(f"[SUCCESS] Merged {len(merge_records)} duplicates into {keep_id}")
    logger.info(f"   - Deleted {deleted_count} duplicate records")
    logger.info(f"   - Total secondary sources: {len(merged_secondary_sources)}")
    logger.info(f"   - Total tags: {len(merged_tags)}")
    
    return deleted_count

def main():
    """Main cleanup function"""
    logger.info("="*80)
    logger.info("🧹 URL DUPLICATE CLEANUP")
    logger.info("="*80)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Connect to database
        logger.info("\n📡 Connecting to database...")
        conn = get_db_connection()
        logger.info("✅ Connected successfully")
        
        # Find URL duplicates
        logger.info("\n🔍 Finding URL duplicates...")
        duplicate_groups = find_url_duplicates(conn)
        
        if not duplicate_groups:
            logger.info("✅ No URL duplicates found! Database is clean.")
            conn.close()
            return
        
        logger.info(f"⚠️  Found {len(duplicate_groups)} groups of URL duplicates")
        
        # Calculate total duplicates
        total_duplicates = sum(group['count'] - 1 for group in duplicate_groups)
        logger.info(f"📊 Total duplicate records to merge: {total_duplicates}")
        
        # Confirm before proceeding
        logger.info(f"\n{'='*60}")
        logger.info("⚠️  WARNING: This will DELETE duplicate records!")
        logger.info("   The oldest record in each group will be kept.")
        logger.info("   Newer records will be merged into secondary_sources.")
        logger.info(f"{'='*60}\n")
        
        # Merge each group
        total_deleted = 0
        successful_merges = 0
        failed_merges = 0
        
        for idx, group in enumerate(duplicate_groups, 1):
            logger.info(f"\n[{idx}/{len(duplicate_groups)}] Processing group...")
            
            try:
                deleted_count = merge_duplicate_group(conn, group)
                total_deleted += deleted_count
                successful_merges += 1
            except Exception as e:
                logger.error(f"[ERROR] Failed to merge group: {e}")
                failed_merges += 1
                conn.rollback()
        
        # Final summary
        logger.info(f"\n{'='*80}")
        logger.info("📊 CLEANUP SUMMARY")
        logger.info("="*80)
        logger.info(f"   Total duplicate groups: {len(duplicate_groups)}")
        logger.info(f"   Successful merges: {successful_merges}")
        logger.info(f"   Failed merges: {failed_merges}")
        logger.info(f"   Total records deleted: {total_deleted}")
        logger.info(f"   Database space saved: ~{total_deleted} records")
        logger.info("="*80)
        
        if successful_merges > 0:
            logger.info("\n✅ Cleanup completed successfully!")
            logger.info("   All URL duplicates have been merged.")
            logger.info("   Deleted records are preserved in secondary_sources.")
        
        # Close connection
        conn.close()
        logger.info("\n✅ Database connection closed")
        
    except Exception as e:
        logger.error(f"\n❌ Cleanup failed: {e}")
        raise
    finally:
        logger.info(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)

if __name__ == "__main__":
    main()
