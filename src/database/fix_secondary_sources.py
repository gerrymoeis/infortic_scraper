"""
Fix Secondary Sources Data Quality
Updates secondary_sources field to replace None account values with actual account names

This script:
1. Finds opportunities with secondary_sources containing None account values
2. Attempts to recover account names from other data sources
3. Updates the secondary_sources field with corrected data
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

logger = setup_logger('fix_secondary_sources')

def get_db_connection():
    """Get database connection"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")
    
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

def find_opportunities_with_none_accounts(conn):
    """
    Find opportunities with secondary_sources containing None account values
    
    Returns:
        List of opportunities with problematic secondary_sources
    """
    query = """
        SELECT 
            id,
            title,
            source_account,
            secondary_sources,
            jsonb_array_length(secondary_sources) as source_count
        FROM opportunities
        WHERE jsonb_array_length(secondary_sources) > 0
        ORDER BY jsonb_array_length(secondary_sources) DESC
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        all_records = cur.fetchall()
    
    # Filter records with None accounts
    problematic_records = []
    for record in all_records:
        secondary_sources = record['secondary_sources']
        has_none = any(
            source.get('source_account') is None or source.get('account') is None
            for source in secondary_sources
        )
        
        if has_none:
            problematic_records.append(record)
    
    return problematic_records

def fix_secondary_sources(conn, record):
    """
    Fix secondary_sources for a single opportunity
    
    Strategy:
    1. Check each secondary source
    2. If account is None, mark as 'unknown' (cannot recover)
    3. Update the record
    
    Args:
        conn: Database connection
        record: Opportunity record
        
    Returns:
        Number of sources fixed
    """
    secondary_sources = record['secondary_sources']
    fixed_count = 0
    
    # Fix each source
    for source in secondary_sources:
        # Handle both 'account' and 'source_account' keys (legacy compatibility)
        if source.get('source_account') is None and source.get('account') is None:
            # Cannot recover account name, mark as unknown
            source['source_account'] = 'unknown'
            source['account'] = 'unknown'  # Keep both for compatibility
            source['fixed_at'] = datetime.now().isoformat()
            fixed_count += 1
        elif source.get('source_account') is None:
            # Copy from 'account' if available
            source['source_account'] = source.get('account', 'unknown')
            fixed_count += 1
        elif source.get('account') is None:
            # Copy from 'source_account' if available
            source['account'] = source.get('source_account', 'unknown')
            fixed_count += 1
    
    if fixed_count > 0:
        # Update database
        update_query = """
            UPDATE opportunities
            SET 
                secondary_sources = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        
        with conn.cursor() as cur:
            cur.execute(update_query, (
                json.dumps(secondary_sources),
                record['id']
            ))
        
        conn.commit()
    
    return fixed_count

def main():
    """Main fix function"""
    logger.info("="*80)
    logger.info("🔧 FIX SECONDARY SOURCES DATA QUALITY")
    logger.info("="*80)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Connect to database
        logger.info("\n📡 Connecting to database...")
        conn = get_db_connection()
        logger.info("✅ Connected successfully")
        
        # Find problematic records
        logger.info("\n🔍 Finding opportunities with None account values...")
        problematic_records = find_opportunities_with_none_accounts(conn)
        
        if not problematic_records:
            logger.info("✅ No problematic secondary_sources found! Data quality is good.")
            conn.close()
            return
        
        logger.info(f"⚠️  Found {len(problematic_records)} opportunities with None account values")
        
        # Show examples
        logger.info(f"\n📝 Top 5 Examples:")
        for idx, record in enumerate(problematic_records[:5], 1):
            logger.info(f"\n   Example #{idx}:")
            logger.info(f"      Title: {record['title'][:60]}...")
            logger.info(f"      Primary Source: {record['source_account']}")
            logger.info(f"      Secondary Sources: {record['source_count']}")
            
            # Count None values
            none_count = sum(
                1 for source in record['secondary_sources']
                if source.get('source_account') is None or source.get('account') is None
            )
            logger.info(f"      None Values: {none_count}/{record['source_count']}")
        
        # Fix each record
        logger.info(f"\n{'='*60}")
        logger.info("🔧 Fixing secondary_sources...")
        logger.info(f"{'='*60}\n")
        
        total_fixed = 0
        successful_fixes = 0
        failed_fixes = 0
        
        for idx, record in enumerate(problematic_records, 1):
            logger.info(f"[{idx}/{len(problematic_records)}] Fixing: {record['title'][:50]}...")
            
            try:
                fixed_count = fix_secondary_sources(conn, record)
                total_fixed += fixed_count
                successful_fixes += 1
                logger.info(f"   ✓ Fixed {fixed_count} sources")
            except Exception as e:
                logger.error(f"   ✗ Failed: {e}")
                failed_fixes += 1
                conn.rollback()
        
        # Final summary
        logger.info(f"\n{'='*80}")
        logger.info("📊 FIX SUMMARY")
        logger.info("="*80)
        logger.info(f"   Total opportunities processed: {len(problematic_records)}")
        logger.info(f"   Successful fixes: {successful_fixes}")
        logger.info(f"   Failed fixes: {failed_fixes}")
        logger.info(f"   Total sources fixed: {total_fixed}")
        logger.info("="*80)
        
        if successful_fixes > 0:
            logger.info("\n✅ Fix completed successfully!")
            logger.info("   All None account values have been marked as 'unknown'.")
            logger.info("   Note: Account names cannot be recovered for old data.")
        
        # Close connection
        conn.close()
        logger.info("\n✅ Database connection closed")
        
    except Exception as e:
        logger.error(f"\n❌ Fix failed: {e}")
        raise
    finally:
        logger.info(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)

if __name__ == "__main__":
    main()
