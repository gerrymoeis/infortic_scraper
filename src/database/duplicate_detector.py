"""
Duplicate Detector - Phase 2 Task 2.2
Detects and scores potential duplicate opportunities across accounts
"""

import logging
from typing import Dict, List, Optional, Tuple
from fuzzywuzzy import fuzz
from datetime import datetime, date

logger = logging.getLogger('duplicate_detector')

class DuplicateDetector:
    """Detects duplicate opportunities with confidence scoring"""
    
    def __init__(self, db_client):
        """
        Initialize duplicate detector
        
        Args:
            db_client: DatabaseClient instance
        """
        self.db = db_client
        logger.info("Duplicate detector initialized")
    
    def find_duplicates(self, new_record: Dict) -> Tuple[Optional[Dict], int, str]:
        """
        Find potential duplicates for new record
        
        Args:
            new_record: Normalized opportunity data
            
        Returns:
            Tuple of (matching_record, confidence_score, match_type)
            match_type: 'exact_post_id' | 'fuzzy_match' | 'no_match'
        """
        # STEP 1: Check exact post_id match (100% confidence)
        post_id = new_record.get('post_id')
        if post_id:
            existing = self._get_by_post_id(post_id)
            if existing:
                logger.info(f"Exact post_id match found: {post_id}")
                return existing, 100, 'exact_post_id'
        
        # STEP 2: Find candidates by title and/or organizer
        candidates = self._find_candidates(new_record)
        
        if not candidates:
            return None, 0, 'no_match'
        
        # STEP 3: Calculate confidence for each candidate
        best_match = None
        best_score = 0
        
        for candidate in candidates:
            score = self.calculate_confidence(new_record, candidate)
            
            if score > best_score:
                best_score = score
                best_match = candidate
        
        # STEP 4: Return best match if confidence >= 70%
        if best_score >= 70:
            logger.info(f"Fuzzy match found: {best_match.get('title')} (confidence: {best_score}%)")
            return best_match, best_score, 'fuzzy_match'
        
        return None, 0, 'no_match'
    
    def calculate_confidence(self, record1: Dict, record2: Dict) -> int:
        """
        Calculate duplicate confidence score (0-100)
        
        Scoring breakdown:
        - Exact title match: 40 points
        - Fuzzy title match >85%: 30 points
        - Same organizer: 30 points
        - Overlapping dates: 20 points
        - Same category: 10 points
        
        Args:
            record1: First opportunity record
            record2: Second opportunity record
            
        Returns:
            Confidence score (0-100)
        """
        score = 0
        
        # Title matching (40 or 30 points)
        title1 = record1.get('title', '').strip().lower()
        title2 = record2.get('title', '').strip().lower()
        
        if title1 and title2:
            if title1 == title2:
                score += 40
                logger.debug(f"Exact title match: +40 points")
            else:
                # Fuzzy match using Levenshtein distance
                similarity = fuzz.ratio(title1, title2)
                if similarity > 85:
                    score += 30
                    logger.debug(f"Fuzzy title match ({similarity}%): +30 points")
        
        # Organizer matching (30 points)
        org1 = record1.get('organizer_name', '').strip().lower()
        org2 = record2.get('organizer_name', '').strip().lower()
        
        if org1 and org2 and org1 == org2:
            score += 30
            logger.debug(f"Same organizer: +30 points")
        
        # Date overlap (20 points)
        if self._dates_overlap(record1, record2):
            score += 20
            logger.debug(f"Overlapping dates: +20 points")
        
        # Category matching (10 points)
        cat1 = record1.get('type_id')
        cat2 = record2.get('type_id')
        
        if cat1 and cat2 and cat1 == cat2:
            score += 10
            logger.debug(f"Same category: +10 points")
        
        logger.debug(f"Total confidence score: {score}")
        return score
    
    def _get_by_post_id(self, post_id: str) -> Optional[Dict]:
        """Get opportunity by post_id"""
        query = "SELECT * FROM opportunities WHERE post_id = %s LIMIT 1"
        results = self.db.execute_query(query, (post_id,))
        return results[0] if results else None
    
    def _find_candidates(self, new_record: Dict) -> List[Dict]:
        """
        Find candidate opportunities for duplicate checking
        
        Looks for opportunities with:
        - Same title, OR
        - Same organizer, OR
        - Similar title (for fuzzy matching)
        
        Args:
            new_record: New opportunity record
            
        Returns:
            List of candidate opportunity dictionaries
        """
        title = new_record.get('title', '') or ''
        title = title.strip()
        organizer_name = new_record.get('organizer_name', '') or ''
        organizer_name = organizer_name.strip()
        
        if not title:
            return []
        
        # Query for potential duplicates
        # We'll get opportunities with same title or same organizer
        # Then filter by fuzzy matching in calculate_confidence
        
        query = """
            SELECT o.*, org.name as organizer_name
            FROM opportunities o
            LEFT JOIN organizers org ON o.organizer_id = org.id
            WHERE o.title = %s
        """
        params = [title]
        
        # Also check by organizer if provided
        if organizer_name:
            query += " OR org.name = %s"
            params.append(organizer_name)
        
        query += " LIMIT 50"  # Limit to prevent too many comparisons
        
        results = self.db.execute_query(query, tuple(params))
        
        logger.debug(f"Found {len(results)} candidates for duplicate checking")
        return results
    
    def _dates_overlap(self, record1: Dict, record2: Dict) -> bool:
        """
        Check if registration dates overlap
        
        Args:
            record1: First opportunity record
            record2: Second opportunity record
            
        Returns:
            True if dates overlap, False otherwise
        """
        # Get deadline dates
        deadline1 = record1.get('dates', {}).get('deadline_date') if 'dates' in record1 else record1.get('deadline_date')
        deadline2 = record2.get('deadline_date')
        
        if not deadline1 or not deadline2:
            return False
        
        # Parse dates if strings
        if isinstance(deadline1, str):
            try:
                deadline1 = datetime.fromisoformat(deadline1).date()
            except:
                return False
        elif isinstance(deadline1, datetime):
            deadline1 = deadline1.date()
        
        if isinstance(deadline2, str):
            try:
                deadline2 = datetime.fromisoformat(deadline2).date()
            except:
                return False
        elif isinstance(deadline2, datetime):
            deadline2 = deadline2.date()
        
        # Check if dates are within 30 days of each other
        # (same event might have slightly different deadlines on different accounts)
        if isinstance(deadline1, date) and isinstance(deadline2, date):
            diff = abs((deadline1 - deadline2).days)
            return diff <= 30
        
        return False
