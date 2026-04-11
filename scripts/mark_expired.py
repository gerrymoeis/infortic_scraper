#!/usr/bin/env python3
"""
Mark Expired Opportunities Script
Automatically marks opportunities as expired when their deadline has passed
"""

import sys
from pathlib import Path
from datetime import date, datetime

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.database.client import DatabaseClient
from src.extraction.utils.config import config
from src.extraction.utils.logger import setup_logger

logger = setup_logger('cleanup')

def mark_expired_opportunities():
    """
    Mark opportunities as expired based on deadline_date
    
    Queries for opportunities where:
    - status = 'active' (currently published)
    - deadline_date < today (deadline has passed)
    
    Updates matching records to:
    - status = 'expired'
    - updated_at = NOW()
    """
    
    start_time = datetime.now()
    
    print("\n" + "=" * 60)
    print("[CLEANUP] Expired Opportunity Cleanup")
    print("=" * 60)
    print(f"[CLEANUP] Started: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 60 + "\n")
    
    try:
        # Connect to database
        db = DatabaseClient(config.DATABASE_URL)
        db.connect()
        print("[CONNECT] Successfully connected to database\n")
        
    except Exception as e:
        print(f"[ERROR] Failed to connect to database: {e}")
        return False
    
    try:
        # Get today's date
        today = date.today()
        
        # Query for expired opportunities
        print("[QUERY] Searching for expired opportunities...")
        print(f"  [CRITERIA] status = 'active' AND deadline_date < {today}")
        print()
        
        expired_query = """
            SELECT id, title, deadline_date
            FROM opportunities
            WHERE status = 'active'
              AND deadline_date < %s
            ORDER BY deadline_date DESC
        """
        
        expired_opps = db.execute_query(expired_query, (today,))
        
        if not expired_opps:
            print("[FOUND] No expired opportunities found")
            print()
            
            # Get total active count for context
            total_active = db.execute_query(
                "SELECT COUNT(*) as count FROM opportunities WHERE status = 'active'"
            )[0]['count']
            
            print("[CLEANUP] Summary:")
            print(f"  Opportunities Checked:  {total_active}")
            print(f"  Expired Found:          0 (0.0%)")
            print(f"  Successfully Marked:    0")
            print(f"  Errors:                 0")
            
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            print(f"  Duration:               {duration:.1f}s")
            print()
            
            db.close()
            
            print("=" * 60)
            print("[CLEANUP] Cleanup Complete - No Expired Opportunities")
            print("=" * 60 + "\n")
            
            return True
        
        # Display found expired opportunities
        print(f"[FOUND] {len(expired_opps)} expired opportunities:")
        for i, opp in enumerate(expired_opps, 1):
            title = opp['title'][:50] + '...' if len(opp['title']) > 50 else opp['title']
            deadline = opp['deadline_date']
            print(f"  {i}. \"{title}\" (deadline: {deadline})")
        print()
        
        # Update opportunities to expired status
        print("[UPDATE] Marking opportunities as expired...")
        
        update_query = """
            UPDATE opportunities
            SET status = 'expired',
                updated_at = NOW()
            WHERE id = %s
            RETURNING id
        """
        
        success_count = 0
        error_count = 0
        
        for opp in expired_opps:
            try:
                result = db.execute_insert(update_query, (opp['id'],))
                if result:
                    success_count += 1
                else:
                    error_count += 1
                    logger.error(f"  [ERROR] Failed to update {opp['title']}: No result returned")
            except Exception as e:
                error_count += 1
                logger.error(f"  [ERROR] Failed to update {opp['title']}: {e}")
        
        print(f"  [PROGRESS] Updated {success_count}/{len(expired_opps)} records")
        
        if success_count == len(expired_opps):
            print(f"  [COMPLETE] All records marked successfully")
        elif success_count > 0:
            print(f"  [WARNING] {error_count} records failed to update")
        else:
            print(f"  [ERROR] All updates failed")
        print()
        
        # Get total active count for summary
        total_active = db.execute_query(
            "SELECT COUNT(*) as count FROM opportunities WHERE status = 'active'"
        )[0]['count']
        
        total_checked = total_active + len(expired_opps)
        
        # Summary
        print("[CLEANUP] Summary:")
        print(f"  Opportunities Checked:  {total_checked}")
        print(f"  Expired Found:          {len(expired_opps)} ({len(expired_opps)/total_checked*100:.1f}%)")
        print(f"  Successfully Marked:    {success_count} ({success_count/len(expired_opps)*100:.1f}%)")
        print(f"  Errors:                 {error_count} ({error_count/len(expired_opps)*100:.1f}%)")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"  Duration:               {duration:.1f}s")
        print()
        
        db.close()
        
        print("=" * 60)
        if error_count == 0:
            print("[CLEANUP] Cleanup Complete - All Expired Opportunities Marked")
        else:
            print("[CLEANUP] Cleanup Complete - Some Errors Occurred")
        print("=" * 60)
        print(f"[CLEANUP] Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 60 + "\n")
        
        return error_count == 0
        
    except Exception as e:
        print(f"\n[ERROR] Cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return False


if __name__ == '__main__':
    success = mark_expired_opportunities()
    sys.exit(0 if success else 1)
