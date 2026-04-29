"""
Data Normalizer V2 - Updated for Simplified Schema
Normalizes extracted data for database insertion
"""

import re
from typing import Dict, List, Optional
from datetime import datetime
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from extraction.utils.logger import setup_logger

logger = setup_logger('normalizer')

class DataNormalizer:
    """Normalizes extracted data for database insertion"""
    
    def __init__(self, audience_mapping: Dict[str, str], type_mapping: Dict[str, str]):
        """
        Initialize normalizer with database mappings
        
        Args:
            audience_mapping: Dict mapping audience codes to UUIDs
            type_mapping: Dict mapping opportunity type codes to UUIDs
        """
        self.audience_mapping = audience_mapping
        self.type_mapping = type_mapping
        logger.info("Data normalizer initialized (V2 - Simplified Schema)")
    
    def normalize_opportunity(self, data: Dict) -> Dict:
        """
        Normalize a single opportunity record for new simplified schema
        
        Args:
            data: Raw opportunity data from JSON extraction
            
        Returns:
            Normalized data ready for database insertion
        """
        normalized = {
            # Core identification
            'post_id': data.get('post_id'),  # NEW: Instagram post ID
            'title': self._normalize_title(data.get('title')),
            'slug': self._generate_slug(data.get('title')),
            'description': self._normalize_description(data.get('description')),
            'raw_caption': data.get('raw_caption'),
            
            # Foreign keys
            'type_id': self._normalize_type(data.get('category')),
            'audience_ids': self._normalize_audiences(data.get('audiences', [])),
            'organizer_name': self._normalize_organizer_name(data.get('organizer')),
            
            # URLs and contact (NEW fields)
            'registration_url': data.get('registration_url'),
            'source_url': data.get('source_url'),  # NEW
            'source_account': data.get('source_account'),  # NEW
            'contact': data.get('contact'),  # NEW
            
            # Dates
            'registration_date': data.get('registration_date'),  # Human-readable string
            'dates': self._parse_registration_date(data.get('registration_date')),
            
            # Event details (NEW: stored directly, no separate tables)
            'event_type': data.get('event_type'),  # NEW: online/offline/hybrid
            'fee_type': data.get('fee_type'),  # NEW: gratis/berbayar
            
            # Images (NEW fields)
            'image_url': data.get('image_url'),  # NEW
            'downloaded_image': data.get('downloaded_image'),  # NEW
            
            # Frontend fields (NEW)
            'view_count': 0,
            'is_featured': False,
            'tags': self._generate_tags(data),  # NEW
        }
        
        return normalized
    
    def _normalize_title(self, title: Optional[str]) -> str:
        """Normalize title"""
        if not title:
            return "Untitled Opportunity"
        
        # Remove excessive whitespace
        title = " ".join(title.split())
        
        # Limit length
        if len(title) > 200:
            title = title[:200].rsplit(' ', 1)[0] + '...'
        
        return title.strip()
    
    def _generate_slug(self, title: Optional[str]) -> str:
        """
        Generate URL-friendly slug from title (human-readable, SEO-friendly)
        NO dates, NO random IDs - just clean text
        
        Args:
            title: Opportunity title
            
        Returns:
            URL-friendly slug
        """
        if not title:
            # Fallback for empty titles - use timestamp
            return f"opportunity-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # Convert to lowercase
        slug = title.lower()
        
        # Remove special characters
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        
        # Replace spaces with hyphens
        slug = re.sub(r'\s+', '-', slug)
        
        # Remove consecutive hyphens
        slug = re.sub(r'-+', '-', slug)
        
        # Trim hyphens from ends
        slug = slug.strip('-')
        
        # Limit length
        if len(slug) > 100:
            slug = slug[:100].rsplit('-', 1)[0]
        
        # Return clean slug WITHOUT any date or ID suffix
        return slug
    
    def _normalize_description(self, description: Optional[str]) -> Optional[str]:
        """Normalize description"""
        if not description:
            return None
        
        # Remove excessive whitespace
        description = " ".join(description.split())
        
        # Limit length
        if len(description) > 500:
            description = description[:500].rsplit(' ', 1)[0] + '...'
        
        return description.strip() if description.strip() else None
    
    def _normalize_type(self, type_code: Optional[str]) -> Optional[str]:
        """
        Map opportunity type code to UUID
        
        Args:
            type_code: Type code (competition, scholarship, etc.)
            
        Returns:
            Type UUID or None
        """
        if not type_code:
            logger.warning("No opportunity type provided")
            return None
        
        # Mapping for types not in database
        TYPE_MAPPING = {
            'volunteer': 'training',  # Volunteer programs → Training (closest match)
        }
        
        # Map to existing type if needed
        mapped_type = TYPE_MAPPING.get(type_code, type_code)
        
        type_id = self.type_mapping.get(mapped_type)
        
        if not type_id:
            logger.warning(f"Unknown opportunity type: {type_code}")
            if mapped_type != type_code:
                logger.info(f"Mapped type: {type_code} → {mapped_type} (but still not found in database)")
        else:
            if mapped_type != type_code:
                logger.info(f"Mapped opportunity type: {type_code} → {mapped_type}")
        
        return type_id
    
    def _normalize_audiences(self, audience_codes: List[str]) -> List[str]:
        """
        Map audience codes to UUIDs
        
        Args:
            audience_codes: List of audience codes (smp, sma, s1, etc.)
            
        Returns:
            List of audience UUIDs
        """
        if not audience_codes:
            return []
        
        # Mapping for unknown codes to existing database codes
        AUDIENCE_MAPPING = {
            'd1': 'd2',  # Diploma 1 → Diploma 2 (similar level)
            's2': 'umum',  # S2/Master → General (broader audience)
            's3': 'umum',  # S3/PhD → General (broader audience)
        }
        
        audience_ids = []
        
        for code in audience_codes:
            # Map unknown codes to known codes
            mapped_code = AUDIENCE_MAPPING.get(code, code)
            
            audience_id = self.audience_mapping.get(mapped_code)
            if audience_id:
                audience_ids.append(audience_id)
                if mapped_code != code:
                    logger.info(f"Mapped audience code: {code} → {mapped_code}")
            else:
                logger.warning(f"Unknown audience code: {code}")
        
        return audience_ids
    
    def _normalize_organizer_name(self, name: Optional[str]) -> Optional[str]:
        """Normalize organizer name"""
        if not name:
            return None
        
        # Remove excessive whitespace
        name = " ".join(name.split())
        
        # Limit length
        if len(name) > 200:
            name = name[:200].rsplit(' ', 1)[0] + '...'
        
        return name.strip() if name.strip() else None
    
    def _parse_registration_date(self, date_string: Optional[str]) -> Dict[str, Optional[str]]:
        """
        Parse human-readable registration date string to database format
        
        Args:
            date_string: Registration date in format "DD Month YYYY - DD Month YYYY" or "DD Month YYYY"
            
        Returns:
            Dictionary with start_date, end_date, deadline_date in YYYY-MM-DD format
        """
        if not date_string:
            return {
                'start_date': None,
                'end_date': None,
                'deadline_date': None,
            }
        
        try:
            import dateparser
            
            # Check if it's a date range
            if ' - ' in date_string:
                parts = date_string.split(' - ')
                start_str = parts[0].strip()
                end_str = parts[1].strip()
                
                # Parse both dates
                start_date = dateparser.parse(start_str, languages=['id', 'en'])
                end_date = dateparser.parse(end_str, languages=['id', 'en'])
                
                return {
                    'start_date': start_date.strftime('%Y-%m-%d') if start_date else None,
                    'end_date': end_date.strftime('%Y-%m-%d') if end_date else None,
                    'deadline_date': end_date.strftime('%Y-%m-%d') if end_date else None,  # Deadline is end of registration
                }
            else:
                # Single date
                parsed_date = dateparser.parse(date_string, languages=['id', 'en'])
                
                if parsed_date:
                    date_str = parsed_date.strftime('%Y-%m-%d')
                    return {
                        'start_date': date_str,
                        'end_date': date_str,
                        'deadline_date': date_str,
                    }
        except Exception as e:
            logger.warning(f"Failed to parse registration date '{date_string}': {e}")
        
        return {
            'start_date': None,
            'end_date': None,
            'deadline_date': None,
        }
    
    def _generate_tags(self, data: Dict) -> List[str]:
        """
        Generate tags for search/filtering
        
        Args:
            data: Raw opportunity data
            
        Returns:
            List of tags
        """
        tags = []
        
        # Add category as tag
        if data.get('category'):
            tags.append(data['category'])
        
        # Add event_type as tag
        if data.get('event_type'):
            tags.append(data['event_type'])
        
        # Add fee_type as tag
        if data.get('fee_type'):
            tags.append(data['fee_type'])
        
        # Add audiences as tags
        if data.get('audiences'):
            tags.extend(data['audiences'])
        
        # Add organizer as tag (if exists)
        if data.get('organizer'):
            tags.append(data['organizer'])
        
        # Remove duplicates and return
        return list(set(tags))
