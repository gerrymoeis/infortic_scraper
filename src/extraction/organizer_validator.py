#!/usr/bin/env python3
"""
Organizer Validator
Validates extracted organizer names and assigns confidence scores
"""

import re
from typing import Optional, Tuple
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.extraction.utils.logger import setup_logger

logger = setup_logger('organizer_validator')


class OrganizerValidator:
    """
    Validates organizer names and assigns confidence scores
    
    Confidence Scoring:
    - 90-100: High confidence (Instagram @mention, known institution)
    - 60-89: Medium confidence (from "by/dari" pattern, partial match)
    - 30-59: Low confidence (inferred from context, short name)
    - 0-29: Rejected (generic phrase, blacklisted, too short)
    """
    
    def __init__(self):
        """Initialize validator with blacklists and patterns"""
        
        # Generic phrases that are NOT valid organizers
        self.generic_blacklist = [
            'para expert', 'sekolah yang sama', 'kreativitas', 'adu logika',
            'inovasi masa depan', 'kesempatan', 'teman-teman', 'sobat',
            'karena itu', 'oleh karena itu', 'oleh sebab itu',
            'berbagai kampus', 'kampus', 'sekolah', 'universitas',
            'para peserta', 'peserta', 'panitia', 'penyelenggara'
        ]
        
        # Source accounts that should not be organizers
        self.source_accounts = [
            'infolomba', 'lomba.it', 'lomba_id', 'info_lomba',
            'lombaindo', 'lombaindonesia'
        ]
        
        # Known institution keywords (increase confidence)
        self.institution_keywords = [
            'universitas', 'institut', 'sekolah', 'sma', 'smk', 'sd',
            'pondok pesantren', 'pesantren', 'yayasan', 'lembaga',
            'fakultas', 'jurusan', 'prodi', 'bem', 'himpunan',
            'organisasi', 'komunitas', 'perkumpulan'
        ]
        
        logger.info("[VALIDATOR] Organizer validator initialized")
    
    def validate(
        self, 
        organizer: Optional[str], 
        source_account: str, 
        caption: str,
        ocr_text: Optional[str] = None
    ) -> Tuple[Optional[str], int]:
        """
        Validate extracted organizer and return confidence score
        
        Args:
            organizer: Extracted organizer name
            source_account: Instagram source account (e.g., "infolomba")
            caption: Original caption text
            ocr_text: OCR extracted text (optional)
        
        Returns:
            Tuple of (validated_organizer or None, confidence_score 0-100)
        """
        
        # Handle None or empty
        if not organizer or not organizer.strip():
            return None, 0
        
        organizer = organizer.strip()
        organizer_lower = organizer.lower()
        
        # VALIDATION CHECKS
        
        # 1. Length check (too short or too long)
        if len(organizer) < 3:
            logger.debug(f"[VALIDATOR] Rejected (too short): '{organizer}'")
            return None, 0
        
        if len(organizer) > 100:
            logger.debug(f"[VALIDATOR] Rejected (too long): '{organizer}'")
            return None, 0
        
        # 2. Blacklist check (generic phrases)
        for phrase in self.generic_blacklist:
            if phrase in organizer_lower:
                logger.debug(f"[VALIDATOR] Rejected (blacklist): '{organizer}' contains '{phrase}'")
                return None, 0
        
        # 3. Source account check
        for account in self.source_accounts:
            if account in organizer_lower:
                logger.debug(f"[VALIDATOR] Rejected (source account): '{organizer}' contains '{account}'")
                return None, 0
        
        # 4. Single generic word check
        if organizer_lower in ['para', 'sekolah', 'teman', 'sobat', 'kesempatan', 'kreativitas', 'kampus']:
            logger.debug(f"[VALIDATOR] Rejected (single generic word): '{organizer}'")
            return None, 0
        
        # CONFIDENCE SCORING
        
        confidence = 50  # Base confidence
        
        # HIGH CONFIDENCE INDICATORS
        
        # Found in Instagram @mention (MOST RELIABLE)
        mention_pattern = r'@([a-zA-Z0-9._]+)'
        mentions = re.findall(mention_pattern, caption)
        
        # Check if organizer matches any @mention (fuzzy match)
        for mention in mentions:
            # Skip source accounts
            if mention.lower() in self.source_accounts:
                continue
            
            # Exact match or close match
            if mention.lower() in organizer_lower or organizer_lower in mention.lower():
                confidence = 95
                logger.debug(f"[VALIDATOR] High confidence (Instagram @mention): '{organizer}' matches @{mention}")
                break
        
        # Found with "by/dari/presented by" pattern
        if confidence < 90:
            by_patterns = [
                f"by {organizer_lower}",
                f"dari {organizer_lower}",
                f"oleh {organizer_lower}",
                f"presented by {organizer_lower}",
                f"diselenggarakan oleh {organizer_lower}"
            ]
            
            caption_lower = caption.lower()
            if ocr_text:
                caption_lower += " " + ocr_text.lower()
            
            if any(pattern in caption_lower for pattern in by_patterns):
                confidence = 80
                logger.debug(f"[VALIDATOR] Medium-high confidence (by/dari pattern): '{organizer}'")
        
        # MEDIUM CONFIDENCE INDICATORS
        
        # Contains known institution keywords
        if any(kw in organizer_lower for kw in self.institution_keywords):
            confidence += 15
            logger.debug(f"[VALIDATOR] Confidence boost (institution keyword): '{organizer}'")
        
        # Has proper capitalization (likely a real name)
        if organizer[0].isupper() and not organizer.isupper():
            confidence += 5
        
        # Contains multiple words (more specific)
        word_count = len(organizer.split())
        if word_count >= 2:
            confidence += 5
        if word_count >= 3:
            confidence += 5
        
        # LOW CONFIDENCE PENALTIES
        
        # Very short name (likely incomplete)
        if len(organizer) < 5:
            confidence -= 20
            logger.debug(f"[VALIDATOR] Confidence penalty (very short): '{organizer}'")
        
        # All lowercase (might be incomplete)
        if organizer.islower():
            confidence -= 10
        
        # All uppercase (might be acronym without context)
        if organizer.isupper() and len(organizer) < 10:
            confidence -= 5
        
        # Final confidence (clamp to 0-100)
        confidence = max(0, min(100, confidence))
        
        # Reject if confidence too low
        if confidence < 30:
            logger.debug(f"[VALIDATOR] Rejected (low confidence {confidence}%): '{organizer}'")
            return None, confidence
        
        # Log validation result
        if confidence >= 90:
            level = "HIGH"
        elif confidence >= 60:
            level = "MEDIUM"
        else:
            level = "LOW"
        
        logger.debug(f"[VALIDATOR] Validated ({level} {confidence}%): '{organizer}'")
        
        return organizer, confidence
    
    def extract_from_mentions(self, caption: str, ocr_text: Optional[str] = None) -> Optional[str]:
        """
        Extract organizer from Instagram @mentions
        
        Args:
            caption: Caption text
            ocr_text: OCR text (optional)
        
        Returns:
            Extracted organizer name or None
        """
        
        combined_text = caption
        if ocr_text:
            combined_text += " " + ocr_text
        
        # Find all @mentions
        mention_pattern = r'@([a-zA-Z0-9._]+)'
        mentions = re.findall(mention_pattern, combined_text)
        
        # Filter out source accounts
        valid_mentions = [
            m for m in mentions 
            if m.lower() not in self.source_accounts
        ]
        
        if not valid_mentions:
            return None
        
        # Return first valid mention (usually the organizer)
        # Convert @mention to readable name (basic cleanup)
        mention = valid_mentions[0]
        
        # Remove underscores and dots, capitalize words
        readable_name = mention.replace('_', ' ').replace('.', ' ')
        readable_name = ' '.join(word.capitalize() for word in readable_name.split())
        
        logger.debug(f"[VALIDATOR] Extracted from @mention: @{mention} → '{readable_name}'")
        
        return readable_name
