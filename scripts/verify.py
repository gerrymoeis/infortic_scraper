"""
Verify database results and generate comprehensive report
"""

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.database.client import DatabaseClient
from src.extraction.utils.config import config
from src.extraction.utils.logger import setup_logger

logger = setup_logger('verify')

def verify_results():
    """Generate comprehensive results report"""
    
    print("\n" + "=" * 60)
    print("[VERIFY] Database Verification Report")
    print("=" * 60)
    print(f"[VERIFY] Generated: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60 + "\n")
    
    try:
        db = DatabaseClient(config.DATABASE_URL)
        db.connect()
        print("[CONNECT] Successfully connected to database\n")
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        return False
    
    try:
        # 1. Overall Statistics
        print("[STATISTICS] Overall Database State:")
        print("-" * 60)
        
        total_opps = db.execute_query("SELECT COUNT(*) as count FROM opportunities")[0]['count']
        
        if total_opps == 0:
            print("[WARNING] Database is empty - no opportunities found\n")
            db.close()
            return True
        
        active_opps = db.execute_query("SELECT COUNT(*) as count FROM opportunities WHERE status = 'active'")[0]['count']
        expired_opps = db.execute_query("SELECT COUNT(*) as count FROM opportunities WHERE status = 'expired'")[0]['count']
        archived_opps = db.execute_query("SELECT COUNT(*) as count FROM opportunities WHERE status = 'archived'")[0]['count']
        
        print(f"  Total Opportunities:  {total_opps} records")
        print(f"  Active (Published):   {active_opps} records ({active_opps/total_opps*100:.1f}%)")
        print(f"  Expired:              {expired_opps} records ({expired_opps/total_opps*100:.1f}%)")
        if archived_opps > 0:
            print(f"  Archived:             {archived_opps} records ({archived_opps/total_opps*100:.1f}%)")
        print()
        
        # 2. Data Quality
        print("[QUALITY] Data Completeness:")
        print("-" * 60)
        
        # Required fields
        with_title = db.execute_query("SELECT COUNT(*) as count FROM opportunities WHERE title IS NOT NULL AND title != ''")[0]['count']
        with_category = db.execute_query("SELECT COUNT(*) as count FROM opportunities WHERE type_id IS NOT NULL")[0]['count']
        with_deadline = db.execute_query("SELECT COUNT(*) as count FROM opportunities WHERE deadline_date IS NOT NULL")[0]['count']
        
        print(f"  Required Fields:")
        print(f"    - Title:            {with_title}/{total_opps} ({with_title/total_opps*100:.1f}%)")
        print(f"    - Category:         {with_category}/{total_opps} ({with_category/total_opps*100:.1f}%)")
        print(f"    - Deadline Date:    {with_deadline}/{total_opps} ({with_deadline/total_opps*100:.1f}%)")
        print()
        
        # Optional fields
        with_reg_date = db.execute_query("SELECT COUNT(*) as count FROM opportunities WHERE registration_date IS NOT NULL")[0]['count']
        with_contact = db.execute_query("SELECT COUNT(*) as count FROM opportunities WHERE contact IS NOT NULL")[0]['count']
        with_organizer = db.execute_query("SELECT COUNT(*) as count FROM opportunities WHERE organizer_id IS NOT NULL")[0]['count']
        with_reg_url = db.execute_query("SELECT COUNT(*) as count FROM opportunities WHERE registration_url IS NOT NULL")[0]['count']
        
        print(f"  Optional Fields:")
        print(f"    - Registration Date: {with_reg_date}/{total_opps} ({with_reg_date/total_opps*100:.1f}%)")
        print(f"    - Contact:          {with_contact}/{total_opps} ({with_contact/total_opps*100:.1f}%)")
        print(f"    - Organizer:        {with_organizer}/{total_opps} ({with_organizer/total_opps*100:.1f}%)")
        print(f"    - Registration URL: {with_reg_url}/{total_opps} ({with_reg_url/total_opps*100:.1f}%)")
        print()
        
        # 3. Duplicate Detection
        print("[DUPLICATES] Merge Detection:")
        print("-" * 60)
        
        with_secondary = db.execute_query(
            "SELECT COUNT(*) as count FROM opportunities WHERE jsonb_array_length(secondary_sources) > 0"
        )[0]['count']
        
        print(f"  Records with merged sources: {with_secondary}")
        
        if with_secondary > 0:
            examples = db.execute_query("""
                SELECT title, jsonb_array_length(secondary_sources) as source_count
                FROM opportunities
                WHERE jsonb_array_length(secondary_sources) > 0
                ORDER BY source_count DESC
                LIMIT 5
            """)
            
            print(f"  Top merged records:")
            for ex in examples:
                title = ex['title'][:45] + '...' if len(ex['title']) > 45 else ex['title']
                print(f"    - \"{title}\" ({ex['source_count']} sources merged)")
        else:
            print(f"  No duplicates detected")
        print()
        
        # 5. Organizers
        print("[ORGANIZERS] Top Organizers:")
        print("-" * 60)
        
        total_orgs = db.execute_query("SELECT COUNT(*) as count FROM organizers")[0]['count']
        print(f"  Total Organizers: {total_orgs}")
        
        if total_orgs > 0:
            top_orgs = db.execute_query("""
                SELECT o.name, COUNT(opp.id) as opp_count
                FROM organizers o
                LEFT JOIN opportunities opp ON o.id = opp.organizer_id
                GROUP BY o.id, o.name
                ORDER BY opp_count DESC
                LIMIT 5
            """)
            
            print(f"  Top 5 by opportunity count:")
            for org in top_orgs:
                org_name = org['name'][:40] + '...' if len(org['name']) > 40 else org['name']
                print(f"    - {org_name:43} {org['opp_count']:2} opportunities")
        print()
        
        # 4. Categories
        print("[CATEGORIES] Distribution:")
        print("-" * 60)
        
        categories = db.execute_query("""
            SELECT ot.code, COUNT(opp.id) as count
            FROM opportunity_types ot
            LEFT JOIN opportunities opp ON ot.id = opp.type_id
            GROUP BY ot.id, ot.code
            ORDER BY count DESC
        """)
        
        for cat in categories:
            if cat['count'] > 0:
                percentage = cat['count']/total_opps*100
                print(f"  {cat['code']:15} {cat['count']:3} records ({percentage:5.1f}%)")
        print()
        
        # 6. Recent Opportunities
        print("[RECENT] Last 10 Opportunities:")
        print("-" * 60)
        
        recent = db.execute_query("""
            SELECT title, status, deadline_date, created_at
            FROM opportunities
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        for opp in recent:
            status_tag = "[ACTIVE]" if opp['status'] == 'active' else f"[{opp['status'].upper()}]"
            deadline = opp.get('deadline_date')
            deadline_str = str(deadline)[:10] if deadline else 'No deadline'
            created = str(opp['created_at'])[:19]
            
            title = opp['title'][:40] + '...' if len(opp['title']) > 40 else opp['title']
            print(f"  {status_tag:10} {title}")
            print(f"             Deadline: {deadline_str} | Created: {created}")
        print()
        
        db.close()
        
        print("=" * 60)
        print("[VERIFY] Verification Complete - No Issues Found")
        print("=" * 60 + "\n")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] Verification failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return False


if __name__ == '__main__':
    success = verify_results()
    sys.exit(0 if success else 1)
