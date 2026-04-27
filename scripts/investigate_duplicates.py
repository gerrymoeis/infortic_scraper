"""
Database Duplicate Investigation Script
Investigates potential duplicate opportunities in the database

This script checks for:
1. Exact duplicates (same title + organizer)
2. Similar duplicates (fuzzy matching)
3. URL duplicates (same registration_url)
4. Secondary sources analysis (merge quality)
"""

import sys
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import json

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.extraction.utils.logger import setup_logger
from dotenv import load_dotenv
import os

# Load environment variables
env_path = Path(__file__).parent.parent / 'config' / '.env'
load_dotenv(env_path)

logger = setup_logger('duplicate_investigation')

def get_db_connection():
    """Get database connection"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")
    
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

def check_exact_duplicates(conn):
    """
    Check for exact duplicates (same title + organizer)
    
    Returns:
        List of duplicate groups
    """
    logger.info("\n" + "="*80)
    logger.info("1️⃣  CHECKING EXACT DUPLICATES (Same Title + Organizer)")
    logger.info("="*80)
    
    query = """
        SELECT 
            o.title,
            org.name as organizer_name,
            COUNT(*) as count,
            ARRAY_AGG(o.id) as opportunity_ids,
            ARRAY_AGG(o.post_id) as post_ids,
            ARRAY_AGG(o.source_account) as source_accounts,
            ARRAY_AGG(o.created_at) as created_dates
        FROM opportunities o
        LEFT JOIN organizers org ON o.organizer_id = org.id
        GROUP BY o.title, org.name
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        results = cur.fetchall()
    
    if not results:
        logger.info("✅ No exact duplicates found!")
        return []
    
    logger.warning(f"⚠️  Found {len(results)} groups of exact duplicates")
    
    for idx, row in enumerate(results, 1):
        logger.info(f"\n📋 Duplicate Group #{idx}:")
        logger.info(f"   Title: {row['title'][:80]}...")
        logger.info(f"   Organizer: {row['organizer_name']}")
        logger.info(f"   Count: {row['count']} duplicates")
        logger.info(f"   Post IDs: {row['post_ids']}")
        logger.info(f"   Source Accounts: {row['source_accounts']}")
    
    return results

def check_url_duplicates(conn):
    """
    Check for URL duplicates (same registration_url)
    
    Returns:
        List of duplicate groups
    """
    logger.info("\n" + "="*80)
    logger.info("2️⃣  CHECKING URL DUPLICATES (Same Registration URL)")
    logger.info("="*80)
    
    query = """
        SELECT 
            registration_url,
            COUNT(*) as count,
            ARRAY_AGG(id) as opportunity_ids,
            ARRAY_AGG(title) as titles,
            ARRAY_AGG(source_account) as source_accounts
        FROM opportunities
        WHERE registration_url IS NOT NULL
        GROUP BY registration_url
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        results = cur.fetchall()
    
    if not results:
        logger.info("✅ No URL duplicates found!")
        return []
    
    logger.warning(f"⚠️  Found {len(results)} groups of URL duplicates")
    
    for idx, row in enumerate(results, 1):
        logger.info(f"\n🔗 URL Duplicate Group #{idx}:")
        logger.info(f"   URL: {row['registration_url'][:80]}...")
        logger.info(f"   Count: {row['count']} duplicates")
        logger.info(f"   Titles: {[t[:50] + '...' if len(t) > 50 else t for t in row['titles']]}")
        logger.info(f"   Source Accounts: {row['source_accounts']}")
    
    return results

def check_post_id_duplicates(conn):
    """
    Check for post_id duplicates (should not happen with current deduplication)
    
    Returns:
        List of duplicate groups
    """
    logger.info("\n" + "="*80)
    logger.info("3️⃣  CHECKING POST_ID DUPLICATES (Should Not Exist)")
    logger.info("="*80)
    
    query = """
        SELECT 
            post_id,
            COUNT(*) as count,
            ARRAY_AGG(id) as opportunity_ids,
            ARRAY_AGG(title) as titles,
            ARRAY_AGG(source_account) as source_accounts
        FROM opportunities
        WHERE post_id IS NOT NULL
        GROUP BY post_id
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        results = cur.fetchall()
    
    if not results:
        logger.info("✅ No post_id duplicates found! (Expected)")
        return []
    
    logger.error(f"🚨 CRITICAL: Found {len(results)} groups of post_id duplicates!")
    logger.error("This should NOT happen with current deduplication logic!")
    
    for idx, row in enumerate(results, 1):
        logger.error(f"\n🚨 Post ID Duplicate Group #{idx}:")
        logger.error(f"   Post ID: {row['post_id']}")
        logger.error(f"   Count: {row['count']} duplicates")
        logger.error(f"   Titles: {row['titles']}")
        logger.error(f"   Source Accounts: {row['source_accounts']}")
    
    return results

def analyze_secondary_sources(conn):
    """
    Analyze secondary_sources field to check merge quality
    
    Returns:
        Statistics about merged opportunities
    """
    logger.info("\n" + "="*80)
    logger.info("4️⃣  ANALYZING SECONDARY SOURCES (Merge Quality)")
    logger.info("="*80)
    
    # Count opportunities with secondary sources
    query_count = """
        SELECT 
            COUNT(*) as total_with_merges,
            AVG(jsonb_array_length(secondary_sources)) as avg_sources,
            MAX(jsonb_array_length(secondary_sources)) as max_sources
        FROM opportunities
        WHERE jsonb_array_length(secondary_sources) > 0
    """
    
    with conn.cursor() as cur:
        cur.execute(query_count)
        stats = cur.fetchone()
    
    logger.info(f"\n📊 Merge Statistics:")
    logger.info(f"   Total opportunities with merges: {stats['total_with_merges']}")
    
    if stats['total_with_merges'] > 0:
        logger.info(f"   Average sources per merge: {stats['avg_sources']:.2f}")
        logger.info(f"   Maximum sources in one merge: {stats['max_sources']}")
        
        # Get examples of merged opportunities
        query_examples = """
            SELECT 
                id,
                title,
                source_account,
                secondary_sources,
                jsonb_array_length(secondary_sources) as source_count
            FROM opportunities
            WHERE jsonb_array_length(secondary_sources) > 0
            ORDER BY jsonb_array_length(secondary_sources) DESC
            LIMIT 5
        """
        
        with conn.cursor() as cur:
            cur.execute(query_examples)
            examples = cur.fetchall()
        
        logger.info(f"\n📝 Top 5 Merged Opportunities:")
        for idx, row in enumerate(examples, 1):
            logger.info(f"\n   Example #{idx}:")
            logger.info(f"      Title: {row['title'][:60]}...")
            logger.info(f"      Primary Source: {row['source_account']}")
            logger.info(f"      Merged Sources: {row['source_count']}")
            logger.info(f"      Secondary Accounts: {[s.get('account') for s in row['secondary_sources']]}")
    else:
        logger.info("   ℹ️  No merged opportunities found")
    
    return stats

def check_similar_titles(conn, similarity_threshold=0.85):
    """
    Check for similar titles using basic string comparison
    (Note: This is a simplified version without fuzzy matching library)
    
    Returns:
        List of potentially similar opportunities
    """
    logger.info("\n" + "="*80)
    logger.info("5️⃣  CHECKING SIMILAR TITLES (Basic Similarity)")
    logger.info("="*80)
    logger.info(f"   Note: Using basic string comparison (no fuzzy matching)")
    
    # Get all opportunities
    query = """
        SELECT 
            id,
            title,
            organizer_id,
            source_account,
            post_id
        FROM opportunities
        ORDER BY title
    """
    
    with conn.cursor() as cur:
        cur.execute(query)
        opportunities = cur.fetchall()
    
    logger.info(f"   Analyzing {len(opportunities)} opportunities...")
    
    # Simple similarity check: same first 50 characters
    similar_groups = []
    checked = set()
    
    for i, opp1 in enumerate(opportunities):
        if opp1['id'] in checked:
            continue
        
        title1_prefix = opp1['title'][:50].lower().strip()
        group = [opp1]
        
        for opp2 in opportunities[i+1:]:
            if opp2['id'] in checked:
                continue
            
            title2_prefix = opp2['title'][:50].lower().strip()
            
            # Check if titles start similarly
            if title1_prefix == title2_prefix and opp1['organizer_id'] == opp2['organizer_id']:
                group.append(opp2)
                checked.add(opp2['id'])
        
        if len(group) > 1:
            similar_groups.append(group)
            checked.add(opp1['id'])
    
    if not similar_groups:
        logger.info("✅ No similar titles found!")
        return []
    
    logger.warning(f"⚠️  Found {len(similar_groups)} groups of similar titles")
    
    for idx, group in enumerate(similar_groups[:10], 1):  # Show first 10
        logger.info(f"\n📋 Similar Group #{idx}:")
        logger.info(f"   Count: {len(group)} similar opportunities")
        for opp in group:
            logger.info(f"      - {opp['title'][:60]}... (Account: {opp['source_account']})")
    
    if len(similar_groups) > 10:
        logger.info(f"\n   ... and {len(similar_groups) - 10} more groups")
    
    return similar_groups

def generate_summary_report(conn, exact_dupes, url_dupes, post_id_dupes, merge_stats, similar_groups):
    """
    Generate summary report of investigation
    """
    logger.info("\n" + "="*80)
    logger.info("📊 INVESTIGATION SUMMARY REPORT")
    logger.info("="*80)
    
    # Get total opportunities
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) as total FROM opportunities")
        total = cur.fetchone()['total']
    
    logger.info(f"\n📈 Database Statistics:")
    logger.info(f"   Total Opportunities: {total}")
    
    logger.info(f"\n🔍 Duplicate Detection Results:")
    logger.info(f"   1. Exact Duplicates (Title + Organizer): {len(exact_dupes)} groups")
    logger.info(f"   2. URL Duplicates: {len(url_dupes)} groups")
    logger.info(f"   3. Post ID Duplicates: {len(post_id_dupes)} groups {'🚨 CRITICAL!' if post_id_dupes else '✅'}")
    logger.info(f"   4. Similar Titles: {len(similar_groups)} groups")
    
    logger.info(f"\n🔗 Merge Quality:")
    if merge_stats['total_with_merges'] > 0:
        logger.info(f"   Opportunities with merges: {merge_stats['total_with_merges']}")
        logger.info(f"   Average sources per merge: {merge_stats['avg_sources']:.2f}")
    else:
        logger.info(f"   No merged opportunities found")
    
    # Calculate duplicate percentage
    total_duplicate_opportunities = 0
    for group in exact_dupes:
        total_duplicate_opportunities += group['count'] - 1  # -1 because one is legitimate
    
    duplicate_percentage = (total_duplicate_opportunities / total * 100) if total > 0 else 0
    
    logger.info(f"\n📊 Impact Assessment:")
    logger.info(f"   Estimated duplicate records: {total_duplicate_opportunities}")
    logger.info(f"   Duplicate percentage: {duplicate_percentage:.2f}%")
    
    if duplicate_percentage < 1:
        logger.info(f"   ✅ Status: EXCELLENT - Very low duplicate rate")
    elif duplicate_percentage < 5:
        logger.info(f"   ⚠️  Status: GOOD - Acceptable duplicate rate")
    elif duplicate_percentage < 10:
        logger.info(f"   ⚠️  Status: MODERATE - Consider cleanup")
    else:
        logger.info(f"   🚨 Status: HIGH - Cleanup recommended")
    
    logger.info(f"\n💡 Recommendations:")
    if len(exact_dupes) > 0:
        logger.info(f"   • Implement automated duplicate cleanup for exact matches")
    if len(url_dupes) > 0:
        logger.info(f"   • Add URL-based duplicate detection to insertion logic")
    if len(post_id_dupes) > 0:
        logger.info(f"   • 🚨 URGENT: Fix post_id deduplication logic (should not have duplicates)")
    if len(similar_groups) > 5:
        logger.info(f"   • Consider implementing fuzzy matching for better duplicate detection")
    if merge_stats['total_with_merges'] == 0:
        logger.info(f"   • Verify merge logic is working correctly")
    
    # Save report to file
    report_data = {
        'timestamp': datetime.now().isoformat(),
        'total_opportunities': total,
        'exact_duplicates': len(exact_dupes),
        'url_duplicates': len(url_dupes),
        'post_id_duplicates': len(post_id_dupes),
        'similar_groups': len(similar_groups),
        'merge_stats': {
            'total_with_merges': merge_stats['total_with_merges'],
            'avg_sources': float(merge_stats['avg_sources']) if merge_stats['avg_sources'] else 0,
            'max_sources': merge_stats['max_sources']
        },
        'duplicate_percentage': duplicate_percentage,
        'estimated_duplicate_records': total_duplicate_opportunities
    }
    
    report_path = Path(__file__).parent.parent.parent / 'infortic_scraper_backup' / f'duplicate_investigation_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n💾 Report saved to: {report_path}")

def main():
    """Main investigation function"""
    logger.info("="*80)
    logger.info("🔍 DATABASE DUPLICATE INVESTIGATION")
    logger.info("="*80)
    logger.info(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Connect to database
        logger.info("\n📡 Connecting to database...")
        conn = get_db_connection()
        logger.info("✅ Connected successfully")
        
        # Run all checks
        exact_dupes = check_exact_duplicates(conn)
        url_dupes = check_url_duplicates(conn)
        post_id_dupes = check_post_id_duplicates(conn)
        merge_stats = analyze_secondary_sources(conn)
        similar_groups = check_similar_titles(conn)
        
        # Generate summary
        generate_summary_report(conn, exact_dupes, url_dupes, post_id_dupes, merge_stats, similar_groups)
        
        # Close connection
        conn.close()
        logger.info("\n✅ Investigation completed successfully!")
        
    except Exception as e:
        logger.error(f"\n❌ Investigation failed: {e}")
        raise
    finally:
        logger.info(f"\nFinished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*80)

if __name__ == "__main__":
    main()
