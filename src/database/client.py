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
