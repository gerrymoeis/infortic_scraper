"""
Data Inserter V2 - Updated for Simplified Schema
Inserts normalized data into PostgreSQL database
Enhanced with Phase 1 (Expiration) and Phase 2 (Duplicate Detection)
"""

from typing import Dict, List, Optional, Tuple
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from extraction.utils.logger import setup_logger
from .client import DatabaseClient
from .duplicate_detector import DuplicateDetector

logger = setup_logger('inserter')

class DataInserter:
    """Inserts normalized opportunity data into database"""
    
    def __init__(self, db_client: DatabaseClient):
        """
        Initialize inserter
        
        Args:
            db_client: Database client instance
        """
        self.db = db_client
        self.duplicate_detector = DuplicateDetector(db_client)  # Phase 2
        logger.info("Data inserter initialized (V2 - Simplified Schema + Phase 1 & 2)")
    
    def _check_expiration(self, normalized_data: Dict) -> bool:
        """
        Check if opportunity is expired based on deadline_date
        
        Args:
            normalized_data: Normalized opportunity data
            
        Returns:
            True if expired, False otherwise
        """
        from datetime import datetime, date
        
        # Get deadline_date from dates dict
        dates = normalized_data.get('dates', {})
        deadline = dates.get('deadline_date')
        
        if not deadline:
            # No deadline, treat as active
            return False
        
        # Parse deadline to date object if string
        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(deadline).date()
            except:
                # Invalid date format, treat as active
                return False
        elif isinstance(deadline, datetime):
            deadline = deadline.date()
        
        # Compare with current date
        current_date = date.today()
        
        return deadline < current_date
    
    def _merge_duplicate(self, existing: Dict, new_data: Dict, confidence: int) -> Tuple[str, List[str]]:
        """
        Merge duplicate record into existing (Phase 2 - Task 2.3)
        
        Args:
            existing: Existing opportunity record from database
            new_data: New normalized opportunity data
            confidence: Confidence score (0-100)
            
        Returns:
            Tuple of (opportunity_id, fields_updated)
        """
        from datetime import datetime
        import json
        
        updates = {}
        fields_updated = []
        
        # STEP 1: Check deadline extension
        new_deadline = new_data.get('dates', {}).get('deadline_date')
        existing_deadline = existing.get('deadline_date')
        
        if new_deadline and existing_deadline:
            # Parse dates for comparison
            if isinstance(new_deadline, str):
                new_deadline_date = datetime.fromisoformat(new_deadline).date()
            else:
                new_deadline_date = new_deadline
            
            if isinstance(existing_deadline, str):
                existing_deadline_date = datetime.fromisoformat(existing_deadline).date()
            elif hasattr(existing_deadline, 'date'):
                existing_deadline_date = existing_deadline.date()
            else:
                existing_deadline_date = existing_deadline
            
            # Update if new deadline is later
            if new_deadline_date > existing_deadline_date:
                updates['deadline_date'] = new_deadline
                updates['registration_date'] = new_data.get('registration_date')
                fields_updated.append('deadline_date')
                logger.info(f"Deadline extended: {existing_deadline_date} to {new_deadline_date}")
        
        # STEP 2: Fill NULL fields
        for field in ['contact', 'description']:
            if not existing.get(field) and new_data.get(field):
                updates[field] = new_data[field]
                fields_updated.append(field)
        
        # STEP 3: Merge tags (union of both arrays)
        existing_tags = set(existing.get('tags', []))
        new_tags = set(new_data.get('tags', []))
        merged_tags = list(existing_tags | new_tags)
        
        if merged_tags != existing.get('tags'):
            updates['tags'] = merged_tags
            fields_updated.append('tags')
        
        # STEP 4: Add to secondary_sources
        secondary_sources = existing.get('secondary_sources', [])
        if not isinstance(secondary_sources, list):
            secondary_sources = []
        
        secondary_sources.append({
            'source_account': new_data.get('source_account'),
            'post_id': new_data.get('post_id'),
            'source_url': new_data.get('source_url'),
            'scraped_at': datetime.now().isoformat()
        })
        # Convert to JSON string for PostgreSQL JSONB
        updates['secondary_sources'] = json.dumps(secondary_sources)
        fields_updated.append('secondary_sources')
        
        # STEP 5: Update database
        if updates:
            self._update_opportunity_fields(existing['id'], updates)
            logger.info(
                f"[MERGED] {existing['title']} "
                f"(confidence: {confidence}%, fields: {', '.join(fields_updated)})"
            )
        
        return existing['id'], fields_updated
    
    def _update_opportunity_fields(self, opportunity_id: str, updates: Dict):
        """
        Update specific fields of an opportunity
        
        Args:
            opportunity_id: Opportunity UUID
            updates: Dictionary of fields to update
        """
        if not updates:
            return
        
        # Build UPDATE query dynamically
        set_clauses = []
        params = []
        
        for field, value in updates.items():
            set_clauses.append(f"{field} = %s")
            params.append(value)
        
        # Add updated_at
        set_clauses.append("updated_at = NOW()")
        
        # Add opportunity_id for WHERE clause
        params.append(opportunity_id)
        
        query = f"""
            UPDATE opportunities 
            SET {', '.join(set_clauses)}
            WHERE id = %s
        """
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, tuple(params))
    
    def insert_opportunity(self, data: Dict) -> tuple[Optional[str], str]:
        """
        Insert or update a single opportunity with all related data
        Enhanced with expiration detection (Phase 1) and duplicate detection (Phase 2)
        
        Args:
            data: Normalized opportunity data
            
        Returns:
            Tuple of (Opportunity ID or None, status_reason)
            status_reason: 'inserted', 'updated', 'expired', 'no_dates', 'error'
        """
        try:
            # STEP 0: Validate date fields (MANDATORY)
            # Registration date is REQUIRED to determine if post is expired
            dates = data.get('dates', {})
            has_registration_date = bool(dates.get('registration_date'))
            has_deadline_date = bool(dates.get('deadline_date'))
            
            if not has_registration_date and not has_deadline_date:
                logger.info(f"[SKIP] No registration_date or deadline_date: {data['title']} (post_id: {data.get('post_id')})")
                return None, 'no_dates'
            
            # STEP 1: Check Expiration (Phase 1 - Task 1.2)
            if self._check_expiration(data):
                # Opportunity is expired, skip insertion
                deadline = data.get('dates', {}).get('deadline_date')
                logger.info(f"[EXPIRED] Skipping expired opportunity: {data['title']} (deadline: {deadline})")
                return None, 'expired'
            
            # STEP 2: Check for Duplicates (Phase 2 - Task 2.2 & 2.3)
            duplicate, confidence, match_type = self.duplicate_detector.find_duplicates(data)
            
            if duplicate:
                if match_type == 'exact_post_id':
                    # Exact duplicate by post_id, update existing
                    logger.info(f"[UPDATE] Exact post_id match: {data['title']} (post_id: {data.get('post_id')})")
                    result = self._update_opportunity_record(duplicate['id'], data)
                    return result, 'updated' if result else 'error'
                
                elif confidence > 90:
                    # High confidence duplicate, merge
                    logger.info(f"[MERGE] High confidence duplicate detected: {data['title']} (confidence: {confidence}%)")
                    opportunity_id, fields_updated = self._merge_duplicate(duplicate, data, confidence)
                    return opportunity_id, 'updated' if opportunity_id else 'error'
                
                else:
                    # Low confidence (70-90%), log but insert as new
                    logger.warning(
                        f"[POSSIBLE DUPLICATE] Low confidence match: {data['title']} "
                        f"(confidence: {confidence}%) - Inserting as new record"
                    )
            
            # STEP 3: Get or create organizer
            organizer_id = None
            if data.get('organizer_name'):
                organizer_id = self.db.get_or_create_organizer(data['organizer_name'])
            
            # STEP 4: Insert new opportunity (with status = 'active')
            opportunity_id = self._insert_opportunity_record(data, organizer_id)
            
            if not opportunity_id:
                logger.error(f"Failed to insert opportunity: {data['title']}")
                return None, 'error'
            
            # STEP 5: Insert audience relationships
            self._insert_audiences(opportunity_id, data.get('audience_ids', []))
            
            logger.info(f"[SUCCESS] Inserted: {data['title']} (ID: {opportunity_id})")
            return opportunity_id, 'inserted'
            
        except Exception as e:
            logger.error(f"Error inserting opportunity {data.get('title')}: {e}")
            import traceback
            traceback.print_exc()
            return None, 'error'
    
    def _insert_opportunity_record(
        self,
        data: Dict,
        organizer_id: Optional[str]
    ) -> Optional[str]:
        """Insert main opportunity record with all fields"""
        
        dates = data.get('dates', {})
        
        query = """
            INSERT INTO opportunities (
                type_id,
                organizer_id,
                post_id,
                title,
                slug,
                description,
                raw_caption,
                registration_url,
                source_url,
                source_account,
                contact,
                registration_date,
                start_date,
                end_date,
                deadline_date,
                event_type,
                fee_type,
                image_url,
                downloaded_image,
                view_count,
                is_featured,
                tags,
                status,
                published_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, NOW()
            )
            RETURNING id
        """
        
        params = (
            data.get('type_id'),
            organizer_id,
            data.get('post_id'),
            data.get('title'),
            data.get('slug'),
            data.get('description'),
            data.get('raw_caption'),
            data.get('registration_url'),
            data.get('source_url'),
            data.get('source_account'),
            data.get('contact'),
            data.get('registration_date'),
            dates.get('start_date'),
            dates.get('end_date'),
            dates.get('deadline_date'),
            data.get('event_type'),
            data.get('fee_type'),
            data.get('image_url'),
            data.get('downloaded_image'),
            data.get('view_count', 0),
            data.get('is_featured', False),
            data.get('tags', []),
            'active',  # Set status to 'active' for new opportunities
        )
        
        return self.db.execute_insert(query, params)
    
    def _update_opportunity_record(
        self,
        opportunity_id: str,
        data: Dict
    ) -> str:
        """
        Update existing opportunity record with new data
        Updates ALL fields, not just non-null ones
        
        Args:
            opportunity_id: Existing opportunity UUID
            data: Normalized opportunity data
            
        Returns:
            Opportunity ID
        """
        dates = data.get('dates', {})
        
        # Get or create organizer if provided
        organizer_id = None
        if data.get('organizer_name'):
            organizer_id = self.db.get_or_create_organizer(data['organizer_name'])
        
        query = """
            UPDATE opportunities SET
                type_id = %s,
                organizer_id = %s,
                title = %s,
                description = %s,
                raw_caption = %s,
                registration_url = %s,
                source_url = %s,
                source_account = %s,
                contact = %s,
                registration_date = %s,
                start_date = %s,
                end_date = %s,
                deadline_date = %s,
                event_type = %s,
                fee_type = %s,
                image_url = %s,
                downloaded_image = %s,
                tags = %s,
                updated_at = NOW()
            WHERE id = %s
        """
        
        params = (
            data.get('type_id'),
            organizer_id,
            data.get('title'),
            data.get('description'),
            data.get('raw_caption'),
            data.get('registration_url'),
            data.get('source_url'),
            data.get('source_account'),
            data.get('contact'),
            data.get('registration_date'),
            dates.get('start_date'),
            dates.get('end_date'),
            dates.get('deadline_date'),
            data.get('event_type'),
            data.get('fee_type'),
            data.get('image_url'),
            data.get('downloaded_image'),
            data.get('tags', []),
            opportunity_id,
        )
        
        with self.db.get_cursor() as cursor:
            cursor.execute(query, params)
        
        # Update audience relationships (remove old, add new)
        self._update_audiences(opportunity_id, data.get('audience_ids', []))
        
        logger.info(f"[SUCCESS] Updated: {data['title']} (ID: {opportunity_id})")
        return opportunity_id
    
    def _update_audiences(self, opportunity_id: str, audience_ids: List[str]):
        """Update opportunity-audience relationships"""
        # Remove existing relationships
        delete_query = "DELETE FROM opportunity_audiences WHERE opportunity_id = %s"
        with self.db.get_cursor() as cursor:
            cursor.execute(delete_query, (opportunity_id,))
        
        # Insert new relationships
        self._insert_audiences(opportunity_id, audience_ids)
    
    def _insert_audiences(self, opportunity_id: str, audience_ids: List[str]):
        """Insert opportunity-audience relationships"""
        if not audience_ids:
            return
        
        query = """
            INSERT INTO opportunity_audiences (opportunity_id, audience_id)
            VALUES (%s, %s)
            ON CONFLICT DO NOTHING
        """
        
        params_list = [(opportunity_id, audience_id) for audience_id in audience_ids]
        self.db.execute_many(query, params_list)
    
    def insert_batch(self, data_list: List[Dict]) -> Dict[str, int]:
        """
        Insert or update a batch of opportunities
        
        Args:
            data_list: List of normalized opportunity data
            
        Returns:
            Statistics dictionary with detailed breakdown
        """
        stats = {
            'total_processed': len(data_list),
            'newly_inserted': 0,
            'updated_existing': 0,
            'skipped_expired': 0,
            'skipped_no_dates': 0,
            'database_errors': 0,
        }
        
        for i, data in enumerate(data_list, 1):
            logger.info(f"[{i}/{stats['total_processed']}] Processing: {data.get('title', 'Unknown')}")
            
            # Check if exists BEFORE processing
            was_existing = self.db.check_duplicate_opportunity(
                post_id=data.get('post_id'),
                title=data.get('title')
            ) is not None
            
            result, status_reason = self.insert_opportunity(data)
            
            # Track specific categories
            if status_reason == 'inserted':
                stats['newly_inserted'] += 1
            elif status_reason == 'updated':
                stats['updated_existing'] += 1
            elif status_reason == 'expired':
                stats['skipped_expired'] += 1
            elif status_reason == 'no_dates':
                stats['skipped_no_dates'] += 1
            elif status_reason == 'error':
                stats['database_errors'] += 1
        
        # Calculate totals for summary
        total_saved = stats['newly_inserted'] + stats['updated_existing']
        total_skipped = stats['skipped_expired'] + stats['skipped_no_dates']
        
        # Improved logging with clear categories
        logger.info(f"\n{'='*60}")
        logger.info(f"[METRICS] Database Insertion Summary:")
        logger.info(f"  Total Processed:        {stats['total_processed']} records")
        logger.info(f"")
        logger.info(f"  Successfully Saved:")
        logger.info(f"    - Newly Inserted:     {stats['newly_inserted']} records ({stats['newly_inserted']/stats['total_processed']*100:.1f}%)")
        logger.info(f"    - Updated Existing:   {stats['updated_existing']} records ({stats['updated_existing']/stats['total_processed']*100:.1f}%)")
        logger.info(f"")
        logger.info(f"  Skipped (Expected):")
        logger.info(f"    - Expired:            {stats['skipped_expired']} records ({stats['skipped_expired']/stats['total_processed']*100:.1f}%) - deadline passed")
        logger.info(f"    - No Dates:           {stats['skipped_no_dates']} records ({stats['skipped_no_dates']/stats['total_processed']*100:.1f}%) - missing registration_date AND deadline_date")
        logger.info(f"")
        logger.info(f"  Errors (Unexpected):")
        logger.info(f"    - Database Errors:    {stats['database_errors']} records ({stats['database_errors']/stats['total_processed']*100:.1f}%)")
        logger.info(f"")
        logger.info(f"  Success Rate: {total_saved/stats['total_processed']*100:.1f}% ({total_saved}/{stats['total_processed']} saved to database)")
        logger.info(f"  Skip Rate: {total_skipped/stats['total_processed']*100:.1f}% ({total_skipped}/{stats['total_processed']} filtered as expected)")
        logger.info(f"  Error Rate: {stats['database_errors']/stats['total_processed']*100:.1f}% ({stats['database_errors']}/{stats['total_processed']} actual failures)")
        logger.info(f"{'='*60}\n")
        
        return stats
