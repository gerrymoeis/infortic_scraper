"""
Database Insertion Pipeline
Main entry point for inserting extracted data into PostgreSQL
"""

import json
import sys
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from extraction.utils.config import config
from extraction.utils.logger import setup_logger
from database.client import DatabaseClient
from database.validator import DataValidator
from database.normalizer import DataNormalizer
from database.inserter import DataInserter

logger = setup_logger('database')

def load_extracted_data(file_path: Path) -> List[Dict]:
    """Load extracted data from JSON file"""
    logger.info(f"[LOAD] Loading extracted data from: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"[SUCCESS] Loaded {len(data)} records")
        return data
    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON format: {e}")
        sys.exit(1)

def save_failed_records(failed_records: List[Dict], output_dir: Path):
    """Save failed records for manual review"""
    if not failed_records:
        return
    
    from extraction.utils.helpers import get_timestamp
    
    output_file = output_dir / f'failed_records_{get_timestamp()}.json'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(failed_records, f, indent=2, ensure_ascii=False)
    
    logger.info(f"[SAVE] Failed records saved to: {output_file}")

def main():
    """Main execution function"""
    
    logger.info('[START] Database Insertion Pipeline Starting...\n')
    
    # Validate database configuration
    if not config.DATABASE_URL:
        logger.error("DATABASE_URL not set in environment!")
        logger.info("Please set DATABASE_URL in config/.env")
        sys.exit(1)
    
    # Get input file from command line or use latest
    if len(sys.argv) > 1:
        input_file = Path(sys.argv[1])
    else:
        # Find latest file in processed directory
        processed_files = list(config.PROCESSED_DIR.glob('extracted_data_*.json'))
        if not processed_files:
            logger.error("No input files found in data/processed/")
            logger.info("Usage: python src/database/main.py [input_file]")
            sys.exit(1)
        input_file = max(processed_files, key=lambda p: p.stat().st_mtime)
    
    # Load data
    extracted_data = load_extracted_data(input_file)
    
    if not extracted_data:
        logger.error("No data to process!")
        sys.exit(1)
    
    # Initialize database client
    logger.info(f"\n{'='*60}")
    logger.info("[CONNECT] Connecting to database...")
    logger.info('='*60)
    
    db_client = DatabaseClient(config.DATABASE_URL)
    
    try:
        db_client.connect()
        
        # Load mappings from database
        logger.info("\n[LOAD] Loading database mappings...")
        audience_mapping = db_client.get_audience_mapping()
        type_mapping = db_client.get_opportunity_type_mapping()
        
        logger.info(f"   - Audience codes: {len(audience_mapping)}")
        logger.info(f"   - Opportunity types: {len(type_mapping)}")
        
        # Validate data
        logger.info(f"\n{'='*60}")
        logger.info("[VALIDATE] Validating data...")
        logger.info('='*60)
        
        valid_records, invalid_records = DataValidator.validate_batch(extracted_data)
        
        if invalid_records:
            logger.warning(f"[WARNING] Found {len(invalid_records)} invalid records")
            save_failed_records(invalid_records, config.FAILED_DIR)
        
        if not valid_records:
            logger.error("No valid records to insert!")
            sys.exit(1)
        
        # Normalize data
        logger.info(f"\n{'='*60}")
        logger.info("[NORMALIZE] Normalizing data...")
        logger.info('='*60)
        
        normalizer = DataNormalizer(audience_mapping, type_mapping)
        normalized_data = [normalizer.normalize_opportunity(record) for record in valid_records]
        
        logger.info(f"[SUCCESS] Normalized {len(normalized_data)} records")
        
        # Insert data
        logger.info(f"\n{'='*60}")
        logger.info("[INSERT] Inserting data into database...")
        logger.info(f"[INSERT] Using optimized batch processing (Phase 2)")
        logger.info('='*60)
        
        inserter = DataInserter(db_client)
        
        # Try optimized batch processing first
        try:
            stats = inserter.insert_batch_optimized(normalized_data)
        except Exception as e:
            logger.error(f"[ERROR] Optimized batch failed: {e}")
            logger.warning("[FALLBACK] Switching to chunked batch processing...")
            
            try:
                stats = inserter.insert_batch_chunked(normalized_data, chunk_size=50)
            except Exception as e2:
                logger.error(f"[ERROR] Chunked batch failed: {e2}")
                logger.warning("[FALLBACK] Switching to legacy one-by-one processing...")
                stats = inserter.insert_batch(normalized_data)
        
        # Final summary - ENHANCED LOGGING (Phase 1)
        logger.info(f"\n{'='*60}")
        logger.info("[COMPLETE] DATABASE INSERTION COMPLETE!")
        logger.info('='*60)
        logger.info(f"[METRICS] Detailed Summary:")
        logger.info(f"   - Total records processed: {len(extracted_data)}")
        logger.info(f"   - Valid records: {len(valid_records)}")
        logger.info(f"   - Invalid records: {len(invalid_records)}")
        logger.info(f"")
        logger.info(f"   📊 INSERTION RESULTS:")
        logger.info(f"   - ✅ Newly Inserted: {stats['newly_inserted']} records")
        logger.info(f"   - 🔄 Updated Existing: {stats['updated_existing']} records")
        logger.info(f"   - ⏭️  Skipped (Expired): {stats['skipped_expired']} records")
        logger.info(f"   - ⏭️  Skipped (No Dates): {stats['skipped_no_dates']} records")
        logger.info(f"   - ⏭️  Skipped (Duplicate Slugs): {stats.get('skipped_duplicate_slugs', 0)} records")
        logger.info(f"   - ❌ Database Errors: {stats['database_errors']} records")
        logger.info(f"")
        
        # Calculate success rate and verify totals
        total_saved = stats['newly_inserted'] + stats['updated_existing']
        total_skipped = stats['skipped_expired'] + stats['skipped_no_dates'] + stats.get('skipped_duplicate_slugs', 0)
        total_accounted = total_saved + total_skipped + stats['database_errors']
        
        success_rate = (total_saved / len(valid_records) * 100) if valid_records else 0
        logger.info(f"   📈 SUCCESS RATE: {success_rate:.1f}% ({total_saved}/{len(valid_records)} saved to database)")
        logger.info(f"   📊 TOTAL ACCOUNTED: {total_accounted}/{len(valid_records)} records")
        
        # Warn if there's a discrepancy
        if total_accounted != len(valid_records):
            missing = len(valid_records) - total_accounted
            logger.warning(f"   ⚠️  DISCREPANCY: {missing} records unaccounted for!")
        
        logger.info('='*60)
        
        if stats['newly_inserted'] > 0 or stats['updated_existing'] > 0:
            logger.info("\n[SUCCESS] Data successfully processed!")
            
            # Additional context for updates vs inserts
            if stats['updated_existing'] > 0 and stats['newly_inserted'] == 0:
                logger.info(f"[INFO] All {stats['updated_existing']} records were UPDATES (posts already exist from previous runs)")
                logger.info(f"[INFO] This is normal behavior - duplicate posts are updated, not inserted again")
            elif stats['newly_inserted'] > 0:
                logger.info(f"[INFO] {stats['newly_inserted']} NEW opportunities added to database")
                if stats['updated_existing'] > 0:
                    logger.info(f"[INFO] {stats['updated_existing']} existing opportunities were updated")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db_client.close()

if __name__ == '__main__':
    main()

