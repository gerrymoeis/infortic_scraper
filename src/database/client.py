"""
PostgreSQL Database Client
Handles connection to Neon PostgreSQL database
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from typing import Optional, Dict, List, Any
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from extraction.utils.logger import setup_logger

logger = setup_logger('database')

class DatabaseClient:
    def __init__(self, database_url: str):
        """
        Initialize database client
        
        Args:
            database_url: PostgreSQL connection string
        """
        self.database_url = database_url
        self.connection = None
        logger.info("Database client initialized")
    
    def connect(self):
        """Establish database connection"""
        try:
            # Add sslmode=require for secure connections (Neon PostgreSQL)
            # This uses system's trusted root certificates
            connection_params = self.database_url
            
            # If sslmode not specified, add it
            if 'sslmode=' not in connection_params:
                separator = '&' if '?' in connection_params else '?'
                connection_params = f"{connection_params}{separator}sslmode=require"
            
            self.connection = psycopg2.connect(
                connection_params,
                cursor_factory=RealDictCursor,
                sslmode='require'  # Use system's trusted certificates
            )
            logger.info("[SUCCESS] Connected to database")
            return self.connection
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
    
    @contextmanager
    def get_cursor(self):
        """Context manager for database cursor"""
        if not self.connection:
            self.connect()
        
        cursor = self.connection.cursor()
        try:
            yield cursor
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            logger.error(f"Transaction rolled back: {e}")
            raise
        finally:
            cursor.close()
    
    def execute_query(self, query: str, params: tuple = None) -> List[Dict]:
        """
        Execute a SELECT query and return results
        
        Args:
            query: SQL query string
            params: Query parameters
            
        Returns:
            List of result dictionaries
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()
    
    def execute_insert(self, query: str, params: tuple = None) -> Optional[str]:
        """
        Execute an INSERT query and return the inserted ID
        
        Args:
            query: SQL INSERT query with RETURNING clause
            params: Query parameters
            
        Returns:
            Inserted record ID (UUID as string)
        """
        with self.get_cursor() as cursor:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result['id'] if result else None
    
    def execute_many(self, query: str, params_list: List[tuple]):
        """
        Execute multiple INSERT/UPDATE queries
        
        Args:
            query: SQL query string
            params_list: List of parameter tuples
        """
        with self.get_cursor() as cursor:
            cursor.executemany(query, params_list)
    
    def get_audience_mapping(self) -> Dict[str, str]:
        """
        Get mapping of audience codes to UUIDs
        
        Returns:
            Dictionary mapping code -> UUID
        """
        query = "SELECT code, id FROM audiences"
        results = self.execute_query(query)
        return {row['code']: row['id'] for row in results}
    
    def get_opportunity_type_mapping(self) -> Dict[str, str]:
        """
        Get mapping of opportunity type codes to UUIDs
        
        Returns:
            Dictionary mapping code -> UUID
        """
        query = "SELECT code, id FROM opportunity_types"
        results = self.execute_query(query)
        return {row['code']: row['id'] for row in results}
    
    def check_duplicate_opportunity(self, post_id: Optional[str] = None, title: Optional[str] = None, organizer_name: Optional[str] = None) -> Optional[str]:
        """
        Check if opportunity already exists (prioritize post_id for deduplication)
        
        Args:
            post_id: Instagram post ID (most reliable for deduplication)
            title: Opportunity title (fallback)
            organizer_name: Organizer name (optional, for title-based check)
            
        Returns:
            Existing opportunity ID if found, None otherwise
        """
        # Priority 1: Check by post_id (most reliable)
        if post_id:
            query = "SELECT id FROM opportunities WHERE post_id = %s LIMIT 1"
            results = self.execute_query(query, (post_id,))
            if results:
                return results[0]['id']
        
        # Priority 2: Check by title + organizer
        if title:
            if organizer_name:
                query = """
                    SELECT o.id 
                    FROM opportunities o
                    LEFT JOIN organizers org ON o.organizer_id = org.id
                    WHERE o.title = %s AND org.name = %s
                    LIMIT 1
                """
                params = (title, organizer_name)
            else:
                query = "SELECT id FROM opportunities WHERE title = %s LIMIT 1"
                params = (title,)
            
            results = self.execute_query(query, params)
            return results[0]['id'] if results else None
        
        return None
    
    def get_or_create_organizer(self, name: str) -> str:
        """
        Get existing organizer or create new one
        
        Args:
            name: Organizer name
            
        Returns:
            Organizer UUID
        """
        # Check if exists
        query = "SELECT id FROM organizers WHERE name = %s LIMIT 1"
        results = self.execute_query(query, (name,))
        
        if results:
            return results[0]['id']
        
        # Generate slug from name (no unique_id needed, will use UUID fallback)
        slug = self._generate_slug(name)
        
        # Create new
        insert_query = """
            INSERT INTO organizers (name, slug)
            VALUES (%s, %s)
            RETURNING id
        """
        return self.execute_insert(insert_query, (name, slug))
    
    def _generate_slug(self, text: str) -> str:
        """
        Generate URL-friendly slug from text (human-readable, SEO-friendly)
        NO dates, NO random IDs - just clean text
        
        Args:
            text: Input text
            
        Returns:
            URL-friendly slug
        """
        import re
        from datetime import datetime
        
        if not text:
            # Fallback for empty text - use timestamp
            return f"item-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Convert to lowercase
        slug = text.lower()
        
        # Remove special characters
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        
        # Replace spaces with hyphens
        slug = re.sub(r'\s+', '-', slug)
        
        # Remove consecutive hyphens
        slug = re.sub(r'-+', '-', slug)
        
        # Trim hyphens from ends
        slug = slug.strip('-')
        
        # Limit length
        if len(slug) > 80:
            slug = slug[:80].rsplit('-', 1)[0]
        
        # Return clean slug WITHOUT any date or ID suffix
        return slug
    
    # REMOVED: get_or_create_location() - no longer needed (event_type stored directly)
    # REMOVED: get_or_create_fee() - no longer needed (fee_type stored directly)


    # Phase 1 - Task 1.4: Query methods for active opportunities
    def get_active_opportunities(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get only active opportunities (excludes expired)
        
        Args:
            limit: Optional limit on number of results
            
        Returns:
            List of active opportunity dictionaries
        """
        query = """
            SELECT * FROM opportunities 
            WHERE status = 'active'
            ORDER BY created_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        return self.execute_query(query)
    
    def get_opportunities_by_status(self, status: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Get opportunities filtered by status
        
        Args:
            status: Status to filter by ('active', 'expired', 'archived')
            limit: Optional limit on number of results
            
        Returns:
            List of opportunity dictionaries
        """
        query = """
            SELECT * FROM opportunities 
            WHERE status = %s
            ORDER BY created_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        return self.execute_query(query, (status,))
    
    def get_all_opportunities_with_status(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get all opportunities including status information
        
        Args:
            limit: Optional limit on number of results
            
        Returns:
            List of opportunity dictionaries with status
        """
        query = """
            SELECT 
                id,
                title,
                slug,
                status,
                deadline_date,
                expired_at,
                auto_expired,
                created_at
            FROM opportunities 
            ORDER BY created_at DESC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        return self.execute_query(query)
    
    # ============================================================================
    # PHASE 2: BATCH PROCESSING METHODS
    # ============================================================================
    
    def get_existing_post_ids(self, post_ids: List[str]) -> set:
        """
        Bulk check which post_ids already exist in database
        
        Args:
            post_ids: List of post IDs to check
            
        Returns:
            Set of existing post_ids
        """
        if not post_ids:
            return set()
        
        # Use ANY operator for efficient bulk check
        query = "SELECT post_id FROM opportunities WHERE post_id = ANY(%s)"
        results = self.execute_query(query, (post_ids,))
        
        return {row['post_id'] for row in results if row['post_id']}
    
    def bulk_insert_opportunities(self, records: List[Dict]) -> List[str]:
        """
        Bulk insert multiple opportunities at once
        
        Args:
            records: List of normalized opportunity dictionaries
            
        Returns:
            List of inserted opportunity IDs
        """
        if not records:
            return []
        
        from psycopg2.extras import execute_values
        
        # Prepare data tuples
        values = []
        for record in records:
            dates = record.get('dates', {})
            values.append((
                record.get('type_id'),
                record.get('organizer_id'),
                record.get('post_id'),
                record.get('title'),
                record.get('slug'),
                record.get('description'),
                record.get('raw_caption'),
                record.get('registration_url'),
                record.get('source_url'),
                record.get('source_account'),
                record.get('contact'),
                record.get('registration_date'),
                dates.get('start_date'),
                dates.get('end_date'),
                dates.get('deadline_date'),
                record.get('event_type'),
                record.get('fee_type'),
                record.get('image_url'),
                record.get('downloaded_image'),
                record.get('view_count', 0),
                record.get('is_featured', False),
                record.get('tags', []),
                'active',  # status
            ))
        
        query = """
            INSERT INTO opportunities (
                type_id, organizer_id, post_id, title, slug, description,
                raw_caption, registration_url, source_url, source_account,
                contact, registration_date, start_date, end_date, deadline_date,
                event_type, fee_type, image_url, downloaded_image, view_count,
                is_featured, tags, status, published_at
            ) VALUES %s
            RETURNING id
        """
        
        with self.get_cursor() as cursor:
            # Use execute_values for bulk insert (much faster)
            result = execute_values(
                cursor,
                query,
                values,
                template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())",
                fetch=True
            )
            return [row['id'] for row in result]
    
    def bulk_update_opportunities(self, records: List[Dict]) -> int:
        """
        Bulk update multiple opportunities at once
        
        Args:
            records: List of normalized opportunity dictionaries with 'id' field
            
        Returns:
            Number of records updated
        """
        if not records:
            return 0
        
        from psycopg2.extras import execute_values
        
        # Prepare data tuples
        values = []
        for record in records:
            dates = record.get('dates', {})
            values.append((
                record.get('type_id'),
                record.get('organizer_id'),
                record.get('title'),
                record.get('description'),
                record.get('raw_caption'),
                record.get('registration_url'),
                record.get('source_url'),
                record.get('source_account'),
                record.get('contact'),
                record.get('registration_date'),
                dates.get('start_date'),
                dates.get('end_date'),
                dates.get('deadline_date'),
                record.get('event_type'),
                record.get('fee_type'),
                record.get('image_url'),
                record.get('downloaded_image'),
                record.get('tags', []),
                record.get('id'),  # WHERE clause
            ))
        
        # Use temporary table approach for bulk update
        query = """
            UPDATE opportunities AS o SET
                type_id = v.type_id,
                organizer_id = v.organizer_id,
                title = v.title,
                description = v.description,
                raw_caption = v.raw_caption,
                registration_url = v.registration_url,
                source_url = v.source_url,
                source_account = v.source_account,
                contact = v.contact,
                registration_date = v.registration_date,
                start_date = v.start_date,
                end_date = v.end_date,
                deadline_date = v.deadline_date,
                event_type = v.event_type,
                fee_type = v.fee_type,
                image_url = v.image_url,
                downloaded_image = v.downloaded_image,
                tags = v.tags,
                updated_at = NOW()
            FROM (VALUES %s) AS v(
                type_id, organizer_id, title, description, raw_caption,
                registration_url, source_url, source_account, contact,
                registration_date, start_date, end_date, deadline_date,
                event_type, fee_type, image_url, downloaded_image, tags, id
            )
            WHERE o.id = v.id::uuid
        """
        
        with self.get_cursor() as cursor:
            execute_values(cursor, query, values)
            return cursor.rowcount
    
    def bulk_insert_audiences(self, opportunity_audiences: List[tuple]) -> int:
        """
        Bulk insert opportunity-audience relationships
        
        Args:
            opportunity_audiences: List of (opportunity_id, audience_id) tuples
            
        Returns:
            Number of relationships inserted
        """
        if not opportunity_audiences:
            return 0
        
        from psycopg2.extras import execute_values
        
        query = """
            INSERT INTO opportunity_audiences (opportunity_id, audience_id)
            VALUES %s
            ON CONFLICT DO NOTHING
        """
        
        with self.get_cursor() as cursor:
            execute_values(cursor, query, opportunity_audiences)
            return cursor.rowcount
    
    def bulk_get_or_create_organizers(self, organizer_names: List[str]) -> Dict[str, str]:
        """
        Bulk get or create organizers
        
        Args:
            organizer_names: List of unique organizer names
            
        Returns:
            Dictionary mapping organizer_name -> organizer_id
        """
        if not organizer_names:
            return {}
        
        # Remove duplicates and None values
        unique_names = list(set(name for name in organizer_names if name))
        
        if not unique_names:
            return {}
        
        # Step 1: Get existing organizers
        query = "SELECT name, id FROM organizers WHERE name = ANY(%s)"
        results = self.execute_query(query, (unique_names,))
        
        existing = {row['name']: row['id'] for row in results}
        
        # Step 2: Create missing organizers
        missing_names = [name for name in unique_names if name not in existing]
        
        if missing_names:
            from psycopg2.extras import execute_values
            
            # Prepare values with slugs
            values = [(name, self._generate_slug(name)) for name in missing_names]
            
            insert_query = """
                INSERT INTO organizers (name, slug)
                VALUES %s
                RETURNING name, id
            """
            
            with self.get_cursor() as cursor:
                new_results = execute_values(
                    cursor,
                    insert_query,
                    values,
                    fetch=True
                )
                
                for row in new_results:
                    existing[row['name']] = row['id']
        
        return existing
