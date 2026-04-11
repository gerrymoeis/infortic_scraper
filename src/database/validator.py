"""
Data Validator
Validates extracted data before database insertion
"""

from typing import Dict, List, Optional, Tuple
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))
from extraction.utils.logger import setup_logger

logger = setup_logger('validator')

class DataValidator:
    """Validates extracted opportunity data"""
    
    VALID_TYPES = ['competition', 'scholarship', 'internship', 'job', 'freelance', 'training', 'tryout', 'workshop', 'festival', 'hackathon']
    VALID_AUDIENCES = ['smp', 'sma', 'd3', 'd4', 's1', 'umum']
    VALID_EVENT_TYPES = ['online', 'offline', 'hybrid']  # Changed from VALID_LOCATION_TYPES
    VALID_FEE_TYPES = ['gratis', 'berbayar']  # Simplified from ['gratis', 'htm', 'range']
    
    @staticmethod
    def validate_opportunity(data: Dict) -> Tuple[bool, List[str]]:
        """
        Validate a single opportunity record (simplified structure)
        
        Args:
            data: Opportunity data dictionary
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Required fields
        if not data.get('post_id'):
            errors.append("Missing required field: post_id")
        
        if not data.get('title') or not data.get('title').strip():
            errors.append("Missing or empty required field: title")
        
        # Changed from 'type' to 'category'
        if not data.get('category'):
            errors.append("Missing required field: category")
        elif data['category'] not in DataValidator.VALID_TYPES:
            errors.append(f"Invalid category: {data['category']}. Must be one of {DataValidator.VALID_TYPES}")
        
        # Validate audiences
        if data.get('audiences'):
            if not isinstance(data['audiences'], list):
                errors.append("audiences must be a list")
            else:
                invalid_audiences = [a for a in data['audiences'] if a not in DataValidator.VALID_AUDIENCES]
                if invalid_audiences:
                    errors.append(f"Invalid audience codes: {invalid_audiences}")
        
        # Validate event_type (changed from location_type)
        if data.get('event_type') and data['event_type'] not in DataValidator.VALID_EVENT_TYPES:
            errors.append(f"Invalid event_type: {data['event_type']}")
        
        # Validate fee_type (simplified)
        if data.get('fee_type') and data['fee_type'] not in DataValidator.VALID_FEE_TYPES:
            errors.append(f"Invalid fee_type: {data['fee_type']}")
        
        # Validate registration_date (string format)
        if data.get('registration_date'):
            if not isinstance(data['registration_date'], str):
                errors.append("registration_date must be a string")
        
        # Validate contact (single phone number)
        if data.get('contact'):
            if not isinstance(data['contact'], str):
                errors.append("contact must be a string")
        
        # Validate registration_url (single URL)
        if data.get('registration_url'):
            if not isinstance(data['registration_url'], str):
                errors.append("registration_url must be a string")
        
        is_valid = len(errors) == 0
        
        if not is_valid:
            logger.warning(f"Validation failed for {data.get('post_id', 'unknown')}: {errors}")
        
        return is_valid, errors
    
    @staticmethod
    def validate_batch(data_list: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Validate a batch of opportunities
        
        Args:
            data_list: List of opportunity dictionaries
            
        Returns:
            Tuple of (valid_records, invalid_records_with_errors)
        """
        valid = []
        invalid = []
        
        for data in data_list:
            is_valid, errors = DataValidator.validate_opportunity(data)
            
            if is_valid:
                valid.append(data)
            else:
                invalid.append({
                    'data': data,
                    'errors': errors
                })
        
        logger.info(f"Validation complete: {len(valid)} valid, {len(invalid)} invalid")
        
        return valid, invalid
    
    @staticmethod
    def sanitize_title(title: str) -> str:
        """
        Sanitize opportunity title
        
        Args:
            title: Raw title string
            
        Returns:
            Sanitized title
        """
        if not title:
            return ""
        
        # Remove excessive whitespace
        title = " ".join(title.split())
        
        # Limit length
        max_length = 200
        if len(title) > max_length:
            title = title[:max_length].rsplit(' ', 1)[0] + '...'
        
        return title.strip()
    
    @staticmethod
    def sanitize_description(description: Optional[str]) -> Optional[str]:
        """
        Sanitize opportunity description
        
        Args:
            description: Raw description string
            
        Returns:
            Sanitized description or None
        """
        if not description:
            return None
        
        # Remove excessive whitespace
        description = " ".join(description.split())
        
        # Limit length
        max_length = 500
        if len(description) > max_length:
            description = description[:max_length].rsplit(' ', 1)[0] + '...'
        
        return description.strip() if description.strip() else None

