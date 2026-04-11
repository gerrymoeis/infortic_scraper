"""
Clean Database - Delete All Data
Use with caution: This will delete all opportunities, organizers, and relationships
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from src.database.client import DatabaseClient
from src.extraction.utils.config import config
from src.extraction.utils.logger import setup_logger

logger = setup_logger('clean_database')

def clean_database():
    """Delete all data from database"""
    
    db = DatabaseClient(config.DATABASE_URL)
    db.connect()
    
    try:
        logger.info("=" * 60)
        logger.info("CLEANING DATABASE - DELETING ALL DATA")
        logger.info("=" * 60)
        
        # Get current counts
        opp_count = db.execute_query("SELECT COUNT(*) as count FROM opportunities")[0]['count']
        org_count = db.execute_query("SELECT COUNT(*) as count FROM organizers")[0]['count']
        rel_count = db.execute_query("SELECT COUNT(*) as count FROM opportunity_audiences")[0]['count']
        
        logger.info(f"\nCurrent data:")
        logger.info(f"  - Opportunities: {opp_count}")
        logger.info(f"  - Organizers: {org_count}")
        logger.info(f"  - Relationships: {rel_count}")
        
        # Confirm deletion
        print("\n" + "!" * 60)
        print("WARNING: This will DELETE ALL DATA from the database!")
        print("!" * 60)
        response = input("\nType 'DELETE ALL' to confirm: ")
        
        if response != "DELETE ALL":
            logger.info("Deletion cancelled by user")
            return
        
        logger.info("\nDeleting all data...")
        
        # Delete in correct order (respect foreign keys)
        with db.get_cursor() as cursor:
            cursor.execute("DELETE FROM opportunity_audiences")
            logger.info(f"✓ Deleted {rel_count} opportunity-audience relationships")
            
            cursor.execute("DELETE FROM opportunities")
            logger.info(f"✓ Deleted {opp_count} opportunities")
            
            cursor.execute("DELETE FROM organizers")
            logger.info(f"✓ Deleted {org_count} organizers")
        
        # Verify deletion
        opp_count = db.execute_query("SELECT COUNT(*) as count FROM opportunities")[0]['count']
        org_count = db.execute_query("SELECT COUNT(*) as count FROM organizers")[0]['count']
        rel_count = db.execute_query("SELECT COUNT(*) as count FROM opportunity_audiences")[0]['count']
        
        logger.info("\n" + "=" * 60)
        logger.info("DATABASE CLEANED SUCCESSFULLY")
        logger.info("=" * 60)
        logger.info(f"\nFinal counts:")
        logger.info(f"  - Opportunities: {opp_count}")
        logger.info(f"  - Organizers: {org_count}")
        logger.info(f"  - Relationships: {rel_count}")
        
    except Exception as e:
        logger.error(f"Error cleaning database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    clean_database()
