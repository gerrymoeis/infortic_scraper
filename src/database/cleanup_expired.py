"""
Auto-Expiration Cleanup Script
Marks opportunities as expired if deadline_date has passed
Should run daily via GitHub Actions
"""

import sys
from pathlib import Path
from datetime import date

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database.client import DatabaseClient
from src.extraction.utils.logger import setup_logger
from src.extraction.utils.config import config

logger = setup_logger('cleanup')

def expire_past_deadlines():
    """
    Mark opportunities as expired if deadline_date has passed
    
    Returns:
        Number of opportunities expired
    """
    db = DatabaseClient(config.DATABASE_URL)
    
    try:
        current_date = date.today()
        logger.info(f"[CLEANUP] Starting auto-expiration check for date: {current_date}")
        
        # Find active opportunities with past deadlines
        query = """
            UPDATE opportunities
            SET 
                status = 'expired',
                expired_at = NOW(),
                auto_expired = true,
                updated_at = NOW()
            WHERE 
                status = 'active'
                AND deadline_date IS NOT NULL
                AND deadline_date < %s
            RETURNING id, title, deadline_date, post_id
        """
        
        with db.get_cursor() as cursor:
            cursor.execute(query, (current_date,))
            expired = cursor.fetchall()
            
            if expired:
                logger.info(f"[CLEANUP] Expired {len(expired)} opportunities:")
                for opp in expired:
                    opp_id, title, deadline, post_id = opp
                    logger.info(f"  - {title[:50]} (deadline: {deadline}, post_id: {post_id})")
            else:
                logger.info("[CLEANUP] No opportunities to expire")
        
        logger.info(f"[SUCCESS] Cleanup complete: {len(expired)} opportunities expired")
        return len(expired)
        
    except Exception as e:
        logger.error(f"[ERROR] Cleanup failed: {e}")
        import traceback
        traceback.print_exc()
        return 0
    finally:
        db.close()

def get_expiration_stats():
    """
    Get statistics about expired opportunities
    
    Returns:
        Dictionary with expiration statistics
    """
    db = DatabaseClient(config.DATABASE_URL)
    
    try:
        query = """
            SELECT 
                COUNT(CASE WHEN status = 'active' THEN 1 END) as active_count,
                COUNT(CASE WHEN status = 'expired' THEN 1 END) as expired_count,
                COUNT(CASE WHEN status = 'expired' AND auto_expired = true THEN 1 END) as auto_expired_count,
                COUNT(CASE WHEN status = 'active' AND deadline_date < CURRENT_DATE THEN 1 END) as should_expire_count
            FROM opportunities
        """
        
        with db.get_cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()
            
            stats = {
                'active': result[0],
                'expired': result[1],
                'auto_expired': result[2],
                'should_expire': result[3]
            }
            
            logger.info(f"[STATS] Expiration Statistics:")
            logger.info(f"  Active opportunities:     {stats['active']}")
            logger.info(f"  Expired opportunities:    {stats['expired']}")
            logger.info(f"  Auto-expired:             {stats['auto_expired']}")
            logger.info(f"  Should be expired:        {stats['should_expire']}")
            
            return stats
        
    except Exception as e:
        logger.error(f"[ERROR] Failed to get stats: {e}")
        return {}
    finally:
        db.close()

def main():
    """Main execution function"""
    
    logger.info(f"\n{'='*60}")
    logger.info('[CLEANUP] Auto-Expiration Cleanup Starting...')
    logger.info('='*60 + '\n')
    
    try:
        # Get stats before cleanup
        logger.info("[STATS] Before cleanup:")
        stats_before = get_expiration_stats()
        
        # Run cleanup
        expired_count = expire_past_deadlines()
        
        # Get stats after cleanup
        logger.info("\n[STATS] After cleanup:")
        stats_after = get_expiration_stats()
        
        logger.info(f"\n{'='*60}")
        logger.info("[COMPLETE] Cleanup Complete!")
        logger.info('='*60)
        logger.info(f"[SUMMARY] Expired {expired_count} opportunities")
        logger.info('='*60 + '\n')
        
        return expired_count
        
    except Exception as e:
        logger.error(f"\n{'='*60}")
        logger.error(f"[ERROR] Fatal Error: {type(e).__name__}: {e}")
        logger.error('='*60)
        import traceback
        logger.debug(traceback.format_exc())
        sys.exit(1)

if __name__ == '__main__':
    expired_count = main()
    print(f"\nExpired {expired_count} opportunities")
    sys.exit(0)
