"""
Helper utility functions for extractor
"""

import re
from datetime import datetime, timedelta
from typing import List, Optional
import dateparser

def extract_registration_date_fallback(text: str) -> Optional[str]:
    """
    Extract registration date in human-readable format as fallback when Gemini fails
    Looks for patterns near REGISTRATION keywords only (not event execution keywords)
    
    PHASE C ENHANCEMENT: Added more patterns for better coverage
    - Deadline-specific patterns (DL:, Batas Akhir:, Tutup:)
    - Abbreviated formats (tgl, s.d., hingga)
    - Numeric formats (DD/MM/YYYY, YYYY-MM-DD)
    
    Args:
        text: Text containing registration date information
        
    Returns:
        Human-readable date string in format "DD Month YYYY - DD Month YYYY" or None
    """
    import dateparser
    from datetime import datetime, timedelta
    
    # Keywords that indicate REGISTRATION dates (INCLUDE)
    # PHASE C: Added more deadline-specific keywords
    registration_keywords = [
        'pendaftaran', 'registrasi', 'daftar', 'registration', 'regist',
        'open submission', 'submission', 'open', 'batas pendaftaran', 
        'deadline', 'tutup pendaftaran', 'close registration', 'dl:', 'dl ',
        'tanggal pendaftaran', 'periode pendaftaran',
        # PHASE C NEW: More deadline keywords
        'batas', 'batas akhir', 'batas waktu', 'tutup', 'ditutup', 'penutupan',
        'terakhir', 'akhir', 'closing', 's.d.', 's/d', 'hingga', 'sampai'
    ]
    
    # Keywords that indicate EVENT dates, NOT registration (EXCLUDE)
    event_keywords = [
        'acara', 'pelaksanaan', 'start belajar', 'start acara', 'mulai acara',
        'jadwal acara', 'tanggal acara', 'waktu pelaksanaan', 'hari pelaksanaan',
        'pelaksanaan final', 'final lomba', 'hari h'
    ]
    
    # Split text into lines for better context
    lines = text.split('\n')
    
    today = datetime.now().date()
    # More flexible date range: allow dates from 1 year ago to 2 years future
    # This helps catch 2025 dates that might still be relevant
    min_date = today - timedelta(days=365)
    max_future = today + timedelta(days=730)
    
    for line in lines:
        line_lower = line.lower()
        
        # EXCLUDE: Skip if line contains event execution keywords
        if any(kw in line_lower for kw in event_keywords):
            continue
        
        # Check for date icons (📅, 📆, 🗓️) - these often indicate registration dates
        has_date_icon = any(icon in line for icon in ['📅', '📆', '🗓️'])
        
        # INCLUDE: Check if line contains registration keywords OR date icon
        if not (any(kw in line_lower for kw in registration_keywords) or has_date_icon):
            continue
        
        # Pattern 1: Date ranges with dash (e.g., "1–30 April 2026", "21-31 Maret 2026", "19 Oktober — 5 November 2025")
        range_patterns = [
            # "1–30 April 2026" or "1-30 April 2026"
            r'(\d{1,2})\s*[–\-—]\s*(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
            # "April 1 - April 30, 2026"
            r'(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\s*[–\-—]\s*(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})',
            # "27 April - 1 Mei 2026" or "19 Oktober — 5 November 2025"
            r'(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)\s*[–\-—]\s*(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
            # "1 Januari 2026 - 2 Februari 2026" (full date range)
            r'(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\s*[–\-—]\s*(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
            # "11 Oktober - 16 November 2" (incomplete year - assume 2025/2026)
            r'(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)\s*[–\-—]\s*(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})',
        ]
        
        for pattern in range_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                # Parse based on pattern type
                if len(groups) == 4 and groups[0].isdigit() and groups[3].isdigit() and len(groups[3]) == 4:  # Pattern 1: "1–30 April 2026"
                    day1, day2, month, year = groups
                    date1_str = f"{day1} {month} {year}"
                    date2_str = f"{day2} {month} {year}"
                    
                    parsed1 = dateparser.parse(date1_str, languages=['id', 'en'])
                    parsed2 = dateparser.parse(date2_str, languages=['id', 'en'])
                    
                    if parsed1 and parsed2:
                        date1 = parsed1.date()
                        date2 = parsed2.date()
                        
                        if min_date <= date1 <= max_future and min_date <= date2 <= max_future:
                            # Format in Indonesian
                            month_id = convert_month_to_indonesian(month)
                            return f"{day1} {month_id} {year} - {day2} {month_id} {year}"
                
                elif len(groups) == 5 and groups[0].isalpha():  # Pattern 2: "April 1 - April 30, 2026"
                    month1, day1, month2, day2, year = groups
                    date1_str = f"{day1} {month1} {year}"
                    date2_str = f"{day2} {month2} {year}"
                    
                    parsed1 = dateparser.parse(date1_str, languages=['id', 'en'])
                    parsed2 = dateparser.parse(date2_str, languages=['id', 'en'])
                    
                    if parsed1 and parsed2:
                        date1 = parsed1.date()
                        date2 = parsed2.date()
                        
                        if min_date <= date1 <= max_future and min_date <= date2 <= max_future:
                            month1_id = convert_month_to_indonesian(month1)
                            month2_id = convert_month_to_indonesian(month2)
                            return f"{day1} {month1_id} {year} - {day2} {month2_id} {year}"
                
                elif len(groups) == 5 and groups[0].isdigit():  # Pattern 3: "27 April - 1 Mei 2026"
                    day1, month1, day2, month2, year = groups
                    date1_str = f"{day1} {month1} {year}"
                    date2_str = f"{day2} {month2} {year}"
                    
                    parsed1 = dateparser.parse(date1_str, languages=['id', 'en'])
                    parsed2 = dateparser.parse(date2_str, languages=['id', 'en'])
                    
                    if parsed1 and parsed2:
                        date1 = parsed1.date()
                        date2 = parsed2.date()
                        
                        if min_date <= date1 <= max_future and min_date <= date2 <= max_future:
                            month1_id = convert_month_to_indonesian(month1)
                            month2_id = convert_month_to_indonesian(month2)
                            return f"{day1} {month1_id} {year} - {day2} {month2_id} {year}"
                
                elif len(groups) == 6:  # Pattern 4: "1 Januari 2026 - 2 Februari 2026"
                    day1, month1, year1, day2, month2, year2 = groups
                    date1_str = f"{day1} {month1} {year1}"
                    date2_str = f"{day2} {month2} {year2}"
                    
                    parsed1 = dateparser.parse(date1_str, languages=['id', 'en'])
                    parsed2 = dateparser.parse(date2_str, languages=['id', 'en'])
                    
                    if parsed1 and parsed2:
                        date1 = parsed1.date()
                        date2 = parsed2.date()
                        
                        if min_date <= date1 <= max_future and min_date <= date2 <= max_future:
                            month1_id = convert_month_to_indonesian(month1)
                            month2_id = convert_month_to_indonesian(month2)
                            return f"{day1} {month1_id} {year1} - {day2} {month2_id} {year2}"
                
                elif len(groups) == 5 and len(groups[4]) <= 2:  # Pattern 5: "11 Oktober - 16 November 2" (incomplete year)
                    day1, month1, day2, month2, year_partial = groups
                    # Assume 2025 or 2026 based on current date
                    current_year = datetime.now().year
                    # Try both years
                    for year in [current_year, current_year + 1, current_year - 1]:
                        date1_str = f"{day1} {month1} {year}"
                        date2_str = f"{day2} {month2} {year}"
                        
                        parsed1 = dateparser.parse(date1_str, languages=['id', 'en'])
                        parsed2 = dateparser.parse(date2_str, languages=['id', 'en'])
                        
                        if parsed1 and parsed2:
                            date1 = parsed1.date()
                            date2 = parsed2.date()
                            
                            if min_date <= date1 <= max_future and min_date <= date2 <= max_future:
                                month1_id = convert_month_to_indonesian(month1)
                                month2_id = convert_month_to_indonesian(month2)
                                return f"{day1} {month1_id} {year} - {day2} {month2_id} {year}"
        
        # Pattern 2: Single dates (e.g., "30 April 2026", "April 30, 2026", "DL: 4 APRIL 2026")
        single_patterns = [
            r'(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
            r'(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})',
        ]
        
        for pattern in single_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                if len(groups) == 3:
                    if groups[0].isdigit():  # "30 April 2026"
                        day, month, year = groups
                    else:  # "April 30, 2026"
                        month, day, year = groups
                    
                    date_str = f"{day} {month} {year}"
                    parsed = dateparser.parse(date_str, languages=['id', 'en'])
                    
                    if parsed:
                        date_obj = parsed.date()
                        
                        if min_date <= date_obj <= max_future:
                            month_id = convert_month_to_indonesian(month)
                            return f"{day} {month_id} {year}"
        
        # PHASE C NEW: Pattern 3 - Numeric date formats
        numeric_patterns = [
            # "01/04/2026" or "1/4/2026" (DD/MM/YYYY - Indonesian format)
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', 'dmy'),
            # "2026-04-01" (YYYY-MM-DD - ISO format)
            (r'(\d{4})-(\d{1,2})-(\d{1,2})', 'ymd'),
            # "01.04.2026" or "1.4.2026" (DD.MM.YYYY)
            (r'(\d{1,2})\.(\d{1,2})\.(\d{4})', 'dmy'),
        ]
        
        for pattern, format_type in numeric_patterns:
            match = re.search(pattern, line)
            if match:
                groups = match.groups()
                
                try:
                    if format_type == 'dmy':  # DD/MM/YYYY or DD.MM.YYYY
                        day, month, year = groups
                        date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    elif format_type == 'ymd':  # YYYY-MM-DD
                        year, month, day = groups
                        date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                    
                    parsed = dateparser.parse(date_str, languages=['id', 'en'])
                    
                    if parsed:
                        date_obj = parsed.date()
                        
                        if min_date <= date_obj <= max_future:
                            # Convert to Indonesian format
                            month_name = date_obj.strftime('%B')
                            month_id = convert_month_to_indonesian(month_name)
                            return f"{date_obj.day} {month_id} {date_obj.year}"
                except (ValueError, AttributeError):
                    continue
        
        # PHASE C NEW: Pattern 4 - Abbreviated formats without year
        # These need special handling to infer the year
        abbreviated_patterns = [
            # "tgl 1-5 April" or "tanggal 1-5 April"
            (r'(?:tgl|tanggal)\s*(\d{1,2})\s*[-–]\s*(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)', 'range'),
            # "s.d. 5 April" or "s/d 5 April" (sampai dengan)
            (r's[./]d[.]?\s*(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)', 'single'),
            # "hingga 5 April"
            (r'hingga\s+(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)', 'single'),
        ]
        
        for pattern, pattern_type in abbreviated_patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                groups = match.groups()
                
                # Infer year based on current date
                current_year = datetime.now().year
                current_month = datetime.now().month
                
                if pattern_type == 'range' and len(groups) == 3:  # "tgl 1-5 April" (range)
                    day1, day2, month = groups
                    
                    # Parse month to number
                    month_str = f"1 {month} {current_year}"
                    parsed_month = dateparser.parse(month_str, languages=['id', 'en'])
                    
                    if parsed_month:
                        target_month = parsed_month.month
                        
                        # If target month is before current month, assume next year
                        if target_month < current_month:
                            year = current_year + 1
                        else:
                            year = current_year
                        
                        date1_str = f"{day1} {month} {year}"
                        date2_str = f"{day2} {month} {year}"
                        
                        parsed1 = dateparser.parse(date1_str, languages=['id', 'en'])
                        parsed2 = dateparser.parse(date2_str, languages=['id', 'en'])
                        
                        if parsed1 and parsed2:
                            date1 = parsed1.date()
                            date2 = parsed2.date()
                            
                            if min_date <= date1 <= max_future and min_date <= date2 <= max_future:
                                month_id = convert_month_to_indonesian(month)
                                return f"{day1} {month_id} {year} - {day2} {month_id} {year}"
                
                elif pattern_type == 'single' and len(groups) == 2:  # "s.d. 5 April" or "hingga 5 April" (single date)
                    day, month = groups
                    
                    # Parse month to number
                    month_str = f"1 {month} {current_year}"
                    parsed_month = dateparser.parse(month_str, languages=['id', 'en'])
                    
                    if parsed_month:
                        target_month = parsed_month.month
                        
                        # If target month is before current month, assume next year
                        if target_month < current_month:
                            year = current_year + 1
                        else:
                            year = current_year
                        
                        date_str = f"{day} {month} {year}"
                        parsed = dateparser.parse(date_str, languages=['id', 'en'])
                        
                        if parsed:
                            date_obj = parsed.date()
                            
                            if min_date <= date_obj <= max_future:
                                month_id = convert_month_to_indonesian(month)
                                return f"{day} {month_id} {year}"
    
    return None

def extract_organizer_fallback(text: str, source_account: str = '') -> Optional[str]:
    """
    Extract organizer from multiple sources with validation
    Priority order:
    1. Instagram account tags (@mentions) - most reliable
    2. "by/oleh/dari" patterns
    3. Hashtags with organization names
    4. Organization names in specific contexts
    
    Args:
        text: Caption text
        source_account: Instagram source account (to avoid using it as organizer)
        
    Returns:
        Organizer name or None
    """
    # Blacklist: Generic phrases and source accounts that should NOT be organizers
    blacklist = [
        'para expert', 'sekolah yang sama', 'kreativitas', 'adu logika', 
        'inovasi masa depan', 'kesempatan', 'teman-teman', 'sobat',
        'kreativitas hingga kompetisi', 'pentas raya', 'adu logika dan kecepatan',
        'infolomba', 'lomba.it', source_account.lower(),
        'karena itu', 'oleh karena itu', 'karena', 'itu'  # Caption fragments
    ]
    
    def is_valid_organizer(org: str, title: str = '') -> bool:
        """Validate if extracted text is a real organizer"""
        if not org or len(org) < 3:
            return False
        
        org_lower = org.lower()
        
        # Check blacklist
        if any(phrase in org_lower for phrase in blacklist):
            return False
        
        # Too long (likely full organizational name)
        if len(org) > 80:
            return False
        
        # Generic words
        generic_words = ['para', 'sekolah', 'teman', 'sobat', 'kesempatan', 'kreativitas']
        if any(word == org_lower for word in generic_words):
            return False
        
        # Same as title (likely wrong)
        if title and org_lower == title.lower():
            return False
        
        return True
    
    def clean_organizer_name(org: str) -> str:
        """Clean and simplify organizer name"""
        # Remove excessive whitespace
        org = " ".join(org.split())
        
        # Simplification rules for universities/institutions
        if 'universitas' in org.lower() or 'institut' in org.lower():
            # "BEM Fakultas X Universitas Y" → "Universitas Y"
            # "Himpunan Mahasiswa X Universitas Y" → "Universitas Y"
            parts = org.split()
            for i, part in enumerate(parts):
                if part.lower() in ['universitas', 'institut', 'politeknik']:
                    # Take from this word onwards
                    return ' '.join(parts[i:])
        
        if 'himpunan mahasiswa' in org.lower():
            # "Himpunan Mahasiswa Informatika ITERA" → "ITERA"
            # Look for acronym at the end
            parts = org.split()
            if len(parts) > 2:
                last_word = parts[-1]
                # If last word is all caps and short, it's likely an acronym
                if last_word.isupper() and len(last_word) <= 10:
                    return last_word
        
        if 'departemen' in org.lower():
            # "Departemen X Institut Y" → "Institut Y"
            parts = org.split()
            for i, part in enumerate(parts):
                if part.lower() in ['institut', 'universitas', 'politeknik']:
                    return ' '.join(parts[i:])
        
        # Limit length
        if len(org) > 50:
            org = org[:50].rsplit(' ', 1)[0]
        
        return org.strip()
    
    def extract_from_instagram_tag(tag: str) -> Optional[str]:
        """
        Convert Instagram tag to readable organizer name
        Examples:
        - @almuhajirin3_purwakarta → "Pondok Pesantren Al-Muhajirin 3 Purwakarta"
        - @smptiga_almuhajirinpurwakarta → "SMP Tiga Al-Muhajirin Purwakarta"
        - @parekampunginggris → "Pare Kampung Inggris"
        """
        # Remove @ symbol
        tag = tag.lstrip('@').strip()
        
        # Skip if it's the source account
        if tag.lower() == source_account.lower():
            return None
        
        # Skip common non-organizer accounts
        skip_accounts = ['infolomba', 'lomba.it', 'lomba_id', 'info_lomba']
        if tag.lower() in skip_accounts:
            return None
        
        # Special known mappings
        known_mappings = {
            'parekampunginggris': 'Pare Kampung Inggris',
            'kampunginggris': 'Kampung Inggris',
            'almuhajirin3_purwakarta': 'Pondok Pesantren Al-Muhajirin 3 Purwakarta',
            'almuhajirin3purwakarta': 'Pondok Pesantren Al-Muhajirin 3 Purwakarta',
        }
        
        tag_lower = tag.lower()
        if tag_lower in known_mappings:
            return known_mappings[tag_lower]
        
        # Pattern 1: School/Institution tags (e.g., @smptiga_almuhajirinpurwakarta)
        if tag_lower.startswith(('smp', 'sma', 'smk', 'sd')):
            # Try to extract meaningful parts
            # "smptiga_almuhajirinpurwakarta" → "SMP Tiga Al-Muhajirin Purwakarta"
            parts = tag.replace('_', ' ').split()
            
            # Capitalize school type
            if parts[0].lower() in ['smp', 'sma', 'smk', 'sd']:
                parts[0] = parts[0].upper()
            
            # Try to identify and capitalize proper nouns
            result_parts = []
            for part in parts:
                # Check if it contains known institution names
                if 'muhajirin' in part.lower():
                    result_parts.append('Al-Muhajirin')
                elif 'tiga' in part.lower() or part.isdigit():
                    result_parts.append(part.title())
                elif len(part) > 3:  # Likely a place name
                    result_parts.append(part.title())
                else:
                    result_parts.append(part)
            
            return ' '.join(result_parts)
        
        # Pattern 2: Pondok Pesantren tags (e.g., @almuhajirin3_purwakarta)
        if 'muhajirin' in tag_lower or 'pesantren' in tag_lower or 'ponpes' in tag_lower:
            # Convert to readable format
            # Handle both "almuhajirin3_purwakarta" and "almuhajirin3purwakarta"
            tag_normalized = tag.replace('_', ' ')
            
            # Insert space before numbers if not present
            tag_normalized = re.sub(r'([a-z])(\d)', r'\1 \2', tag_normalized)
            
            parts = tag_normalized.split()
            result_parts = []
            
            for part in parts:
                if 'muhajirin' in part.lower():
                    result_parts.append('Al-Muhajirin')
                elif part.isdigit():
                    result_parts.append(part)
                elif len(part) > 3:
                    result_parts.append(part.title())
            
            # Add "Pondok Pesantren" prefix if not present
            result = ' '.join(result_parts)
            if 'pesantren' not in result.lower() and 'muhajirin' in result.lower():
                result = 'Pondok Pesantren ' + result
            
            return result
        
        # Pattern 3: University/Institution tags
        if any(kw in tag_lower for kw in ['univ', 'institut', 'poltek', 'its', 'itb', 'ugm', 'ui']):
            # Convert underscores to spaces and capitalize
            return tag.replace('_', ' ').title()
        
        # Pattern 4: Organization acronyms (all caps or mixed case)
        if tag.isupper() or (len(tag) <= 10 and any(c.isupper() for c in tag)):
            return tag.upper()
        
        # Default: Convert to title case with spaces
        return tag.replace('_', ' ').title()
    
    # PRIORITY 1: Instagram account tags (@mentions) - MOST RELIABLE
    # Look for @mentions that are likely organizers
    mention_pattern = r'@([a-zA-Z0-9._]+)'
    mentions = re.findall(mention_pattern, text)
    
    if mentions:
        # Filter out source account and common non-organizer accounts
        filtered_mentions = []
        for mention in mentions:
            mention_lower = mention.lower()
            # Skip source account
            if mention_lower == source_account.lower():
                continue
            # Skip common info accounts
            if mention_lower in ['infolomba', 'lomba.it', 'lomba_id', 'info_lomba']:
                continue
            # Skip personal accounts (usually have numbers or dots)
            if mention.count('.') > 1 or (any(c.isdigit() for c in mention) and len(mention) < 8):
                continue
            
            filtered_mentions.append(mention)
        
        # If we have mentions, try to extract organizer from the first one
        if filtered_mentions:
            # Prefer mentions that look like institutions
            institution_keywords = ['smp', 'sma', 'smk', 'sd', 'univ', 'institut', 'poltek', 
                                   'pesantren', 'ponpes', 'muhajirin', 'its', 'itb', 'ugm']
            
            # First, try to find institution mentions
            for mention in filtered_mentions:
                mention_lower = mention.lower()
                if any(kw in mention_lower for kw in institution_keywords):
                    organizer = extract_from_instagram_tag(mention)
                    if organizer and is_valid_organizer(organizer):
                        return clean_organizer_name(organizer)
            
            # If no institution found, use first filtered mention
            organizer = extract_from_instagram_tag(filtered_mentions[0])
            if organizer and is_valid_organizer(organizer):
                return clean_organizer_name(organizer)
    
    # PRIORITY 2: "by/oleh/dari" patterns
    # Improved to avoid matching "Oleh karena itu" and similar phrases
    by_patterns = [
        # "by [Name]" or "oleh [Name]" - must be followed by capital letter (proper noun)
        r'(?:^|\n|\s)(?:by|dari)\s+([A-Z][A-Za-z\s&]+?)(?:\n|$|[.!,])',
        # "oleh [Name]" - but NOT "oleh karena"
        r'(?:^|\n|\s)oleh\s+(?!karena)([A-Z][A-Za-z\s&]+?)(?:\n|$|[.!,])',
        # "presented by" or "dipersembahkan oleh"
        r'(?:presented by|dipersembahkan oleh)\s+([A-Z][A-Za-z\s&]+?)(?:\n|$|[.!,])',
    ]
    
    for pattern in by_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            organizer = match.group(1).strip()
            if is_valid_organizer(organizer):
                return clean_organizer_name(organizer)
    
    # PRIORITY 3: Hashtags with organization names
    hashtag_patterns = [
        r'#([a-zA-Z][a-zA-Z0-9]*(?:[A-Z][a-z]+)+)',  # CamelCase: #PareKampungInggris
        r'#([a-z]+(?:kampung|pare|inggris|english|academy|institute|university|college)[a-z]*)',  # Lowercase with keywords
    ]
    
    # Filter out common non-organizer hashtags
    exclude_keywords = [
        'lomba', 'kompetisi', 'beasiswa', 'gratis', 'free', 'indonesia',
        'jakarta', 'surabaya', 'bandung', 'online', 'offline', 'gapyear',
        'bahasainggris', 'freecourse', 'training', 'kursus', 'infolomba'
    ]
    
    for pattern in hashtag_patterns:
        hashtags = re.findall(pattern, text, re.IGNORECASE)
        for hashtag in hashtags:
            hashtag_lower = hashtag.lower()
            
            # Skip if it's in exclude list
            if hashtag_lower in exclude_keywords:
                continue
            
            # Check if it contains exclude keywords
            if any(kw == hashtag_lower for kw in exclude_keywords):
                continue
            
            # Special handling for known organizers
            if 'parekampunginggris' in hashtag_lower or 'kampunginggris' in hashtag_lower:
                return "Pare Kampung Inggris"
            
            # Convert CamelCase to Title Case with spaces
            # e.g., "PareKampungInggris" -> "Pare Kampung Inggris"
            spaced = re.sub(r'([a-z])([A-Z])', r'\1 \2', hashtag)
            if is_valid_organizer(spaced):
                return clean_organizer_name(spaced.title())
    
    # PRIORITY 4: Organization names in specific contexts
    # e.g., "MPK & OSIS SMA Negeri 63 Jakarta"
    org_patterns = [
        r'((?:MPK|OSIS|BEM|HIMA|UKM)\s+[A-Z][A-Za-z\s&0-9]+?)(?:\s+(?:presents|mengadakan|membuka))',
        r'((?:Universitas|Institut|Sekolah|SMA|SMK|Pondok Pesantren)\s+[A-Z][A-Za-z\s0-9\-]+?)(?:\s+(?:presents|mengadakan|membuka))',
    ]
    
    for pattern in org_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            organizer = match.group(1).strip()
            if is_valid_organizer(organizer):
                return clean_organizer_name(organizer)
    
    return None

def convert_month_to_indonesian(month: str) -> str:
    """Convert month name to Indonesian"""
    month_mapping = {
        'january': 'Januari', 'jan': 'Januari',
        'february': 'Februari', 'feb': 'Februari',
        'march': 'Maret', 'mar': 'Maret',
        'april': 'April', 'apr': 'April',
        'may': 'Mei',
        'june': 'Juni', 'jun': 'Juni',
        'july': 'Juli', 'jul': 'Juli',
        'august': 'Agustus', 'aug': 'Agustus', 'agu': 'Agustus',
        'september': 'September', 'sep': 'September',
        'october': 'Oktober', 'oct': 'Oktober', 'okt': 'Oktober',
        'november': 'November', 'nov': 'November',
        'december': 'Desember', 'dec': 'Desember', 'des': 'Desember',
    }
    
    month_lower = month.lower()
    return month_mapping.get(month_lower, month.title())

def extract_dates(text: str) -> List[str]:
    """
    Extract dates with validation and context awareness
    Handles Indonesian and English date formats, including date ranges
    
    Args:
        text: Text containing dates
        
    Returns:
        List of ISO format date strings (YYYY-MM-DD)
    """
    dates = []
    today = datetime.now().date()
    # Allow dates from 30 days ago (to catch recent past dates) to 2 years future
    min_date = today - timedelta(days=30)
    max_future = today + timedelta(days=730)
    
    # Pattern 1: Date ranges (e.g., "21-31 Maret 2026", "April 27 - May 1, 2026")
    range_patterns = [
        # Indonesian: "21-31 Maret 2026" or "21 - 31 Maret 2026"
        r'(\d{1,2})\s*[-–]\s*(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+(\d{4})',
        # English: "April 27 - May 1, 2026"
        r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\s*[-–,]*\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})',
        # Mixed: "27 April - 1 Mei 2026"
        r'(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)\s*[-–]\s*(\d{1,2})\s+(Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember|January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
    ]
    
    for pattern in range_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            if len(match) == 4:  # Pattern 1: "21-31 Maret 2026"
                day1, day2, month, year = match
                # Parse both dates
                date1_str = f"{day1} {month} {year}"
                date2_str = f"{day2} {month} {year}"
                for date_str in [date1_str, date2_str]:
                    parsed = dateparser.parse(date_str, languages=['id', 'en'])
                    if parsed:
                        date_obj = parsed.date()
                        if min_date <= date_obj <= max_future:
                            dates.append(date_obj.isoformat())
            
            elif len(match) == 5 and match[0].isalpha():  # Pattern 2: "April 27 - May 1, 2026"
                month1, day1, month2, day2, year = match
                date1_str = f"{month1} {day1}, {year}"
                date2_str = f"{month2} {day2}, {year}"
                for date_str in [date1_str, date2_str]:
                    parsed = dateparser.parse(date_str, languages=['id', 'en'])
                    if parsed:
                        date_obj = parsed.date()
                        if min_date <= date_obj <= max_future:
                            dates.append(date_obj.isoformat())
            
            elif len(match) == 5 and match[0].isdigit():  # Pattern 3: "27 April - 1 Mei 2026"
                day1, month1, day2, month2, year = match
                date1_str = f"{day1} {month1} {year}"
                date2_str = f"{day2} {month2} {year}"
                for date_str in [date1_str, date2_str]:
                    parsed = dateparser.parse(date_str, languages=['id', 'en'])
                    if parsed:
                        date_obj = parsed.date()
                        if min_date <= date_obj <= max_future:
                            dates.append(date_obj.isoformat())
    
    # Pattern 2: Single dates
    single_date_patterns = [
        # Full month names (Indonesian)
        r'\d{1,2}\s+(?:Januari|Februari|Maret|April|Mei|Juni|Juli|Agustus|September|Oktober|November|Desember)\s+\d{4}',
        # Abbreviated month names (Indonesian)
        r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|Mei|Jun|Jul|Agu|Sep|Okt|Nov|Des)\s+\d{4}',
        # English month names
        r'\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}',
        r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}',
        # Numeric formats
        r'\d{1,2}[/]\d{1,2}[/]\d{2,4}',
        r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',
    ]
    
    for pattern in single_date_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for date_str in matches:
            # Skip if this date is part of a range we already processed
            if any(date_str in match_str for match_str in [str(m) for m in re.findall(r'|'.join(range_patterns), text, re.IGNORECASE)]):
                continue
            
            parsed = dateparser.parse(date_str, languages=['id', 'en'])
            if parsed:
                date_obj = parsed.date()
                if min_date <= date_obj <= max_future:
                    dates.append(date_obj.isoformat())
    
    # Remove duplicates and sort
    return sorted(list(set(dates)))

def extract_fee_amount(text: str) -> Optional[float]:
    """
    Extract fee amount from Indonesian text
    
    Args:
        text: Text containing fee information
        
    Returns:
        Fee amount as float or None
    """
    # Check for free indicators first
    free_keywords = ['gratis', 'free', 'tanpa biaya', 'tidak dipungut biaya']
    for keyword in free_keywords:
        if keyword in text.lower():
            return None
    
    # Patterns for Indonesian currency
    patterns = [
        # Rp 350.000 or Rp 350,000 or Rp350000
        (r'Rp\s*(\d+(?:\.\d{3})*(?:,\d+)?)', 1),
        # 350.000 rupiah or 350,000 rupiah
        (r'(\d+(?:\.\d{3})*(?:,\d+)?)\s*[Rr]upiah', 1),
        # 10K, 25K (thousands notation)
        (r'(\d+)\s*[Kk](?:\s|$|[^a-zA-Z])', 1000),
        # biaya ... 350.000
        (r'biaya.*?(\d+(?:\.\d{3})*)', 1),
        # HTM ... 350.000
        (r'HTM.*?(\d+(?:\.\d{3})*)', 1),
    ]
    
    for pattern, multiplier in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            amount_str = matches[0]
            try:
                # Remove dots (thousand separators) and replace comma with dot
                amount_str = amount_str.replace('.', '').replace(',', '.')
                amount = float(amount_str)
                
                # Apply multiplier (for K notation)
                if isinstance(multiplier, int) and multiplier > 1:
                    amount *= multiplier
                
                # Sanity check: fee should be between 0 and 100 million IDR
                if 0 < amount <= 100_000_000:
                    return amount
            except (ValueError, AttributeError):
                continue
    
    return None

def extract_urls(text: str) -> List[str]:
    """Extract URLs using regex, including URLs without http/https prefix"""
    url_patterns = [
        r'https?://[^\s]+',  # Full URLs with http/https
        r'bit\.ly/[^\s]+',   # bit.ly short links
        r'linktr\.ee/[^\s]+', # Linktree
        r'forms\.gle/[^\s]+', # Google Forms
        r's\.id/[^\s]+',      # s.id short links
        r'[a-zA-Z0-9-]+\.[a-zA-Z]{2,}/[^\s]*',  # Domain with path (e.g., sahut.co/event)
    ]
    
    urls = []
    for pattern in url_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            # Clean up URL (remove trailing punctuation)
            url = match.rstrip('.,;:!?)')
            
            # Add https:// prefix if missing
            if not url.startswith('http'):
                url = 'https://' + url
            
            urls.append(url)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in urls:
        url_lower = url.lower()
        if url_lower not in seen:
            seen.add(url_lower)
            unique_urls.append(url)
    
    return unique_urls

def extract_phone_numbers(text: str) -> List[str]:
    """Extract Indonesian phone numbers"""
    phone_pattern = r'(?:\+62|0)[\s-]?\d{2,4}[\s-]?\d{3,4}[\s-]?\d{3,4}'
    phones = re.findall(phone_pattern, text)
    return [re.sub(r'[\s-]', '', phone) for phone in phones]

def extract_contacts(text: str) -> List[dict]:
    """
    Extract contact person names with phone numbers
    
    Args:
        text: Text containing contact information
        
    Returns:
        List of contact dictionaries with name, phone, and role
    """
    contacts = []
    
    # Patterns for name-phone pairs
    # Pattern 1: CP/Contact/Narahubung: Name - phone or Name (phone) or Name: phone
    patterns = [
        # CP: Name - phone or CP: Name (phone)
        r'(?:CP|Contact|Kontak|Narahubung|Info)[\s:]*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)[:\s\-\(]*(\+?62|0)[\s-]?(\d{2,4})[\s-]?(\d{3,4})[\s-]?(\d{3,4})',
        # Name: phone (with capital letter start)
        r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)[:\s]*(\+?62|0)[\s-]?(\d{2,4})[\s-]?(\d{3,4})[\s-]?(\d{3,4})',
        # - Name: phone (in lists)
        r'[\-\•]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)[:\s]*(\+?62|0)[\s-]?(\d{2,4})[\s-]?(\d{3,4})[\s-]?(\d{3,4})',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            if len(match) >= 5:
                name = match[0].strip()
                phone_prefix = match[1]
                phone_parts = match[2:5]
                
                # Reconstruct phone number
                phone_number = ''.join(phone_parts)
                full_phone = phone_prefix + phone_number
                
                # Normalize phone (remove spaces, dashes)
                full_phone = re.sub(r'[\s-]', '', full_phone)
                
                # Convert to international format
                if full_phone.startswith('0'):
                    full_phone = '62' + full_phone[1:]
                elif full_phone.startswith('+'):
                    full_phone = full_phone[1:]
                
                # Try to extract role (text before name)
                role = None
                name_idx = text.find(name)
                if name_idx > 0:
                    before_text = text[max(0, name_idx-50):name_idx].strip()
                    # Look for role keywords
                    role_keywords = ['CP', 'Contact', 'Kontak', 'Narahubung', 'Info']
                    for keyword in role_keywords:
                        if keyword in before_text:
                            role = keyword
                            break
                
                contacts.append({
                    'name': name,
                    'phone': full_phone,
                    'role': role
                })
    
    # Remove duplicates based on phone number
    seen_phones = set()
    unique_contacts = []
    for contact in contacts:
        if contact['phone'] not in seen_phones:
            seen_phones.add(contact['phone'])
            unique_contacts.append(contact)
    
    return unique_contacts

def categorize_dates(text: str, dates: List[str]) -> dict:
    """
    Categorize extracted dates based on context keywords
    
    Args:
        text: Original caption text
        dates: List of extracted dates in ISO format
        
    Returns:
        Dictionary with categorized dates
    """
    categorized = {
        'registration_start': None,
        'registration_end': None,
        'event_start': None,
        'event_end': None,
        'announcement_date': None
    }
    
    if not dates:
        return categorized
    
    # Split text into lines for better context
    lines = text.split('\n')
    
    # Track which dates have been assigned
    assigned_dates = set()
    
    for line in lines:
        line_lower = line.lower()
        
        # Find dates mentioned in this line
        line_dates = []
        for date in dates:
            if date in assigned_dates:
                continue
            # Check if date appears in line (in various formats)
            date_parts = date.split('-')  # ['2026', '04', '01']
            # Check for patterns like "1 April", "01 April", "April 1"
            if any(part in line for part in date_parts[1:]):  # Check month and day
                line_dates.append(date)
        
        if not line_dates:
            continue
        
        # Categorize based on keywords
        if any(kw in line_lower for kw in ['pendaftaran', 'registrasi', 'daftar', 'registration']):
            if len(line_dates) == 1:
                if not categorized['registration_end']:
                    categorized['registration_end'] = line_dates[0]
                    assigned_dates.add(line_dates[0])
            elif len(line_dates) >= 2:
                if not categorized['registration_start']:
                    categorized['registration_start'] = line_dates[0]
                    assigned_dates.add(line_dates[0])
                if not categorized['registration_end']:
                    categorized['registration_end'] = line_dates[1]
                    assigned_dates.add(line_dates[1])
        
        elif any(kw in line_lower for kw in ['pelaksanaan', 'event', 'acara', 'lomba', 'competition']):
            if len(line_dates) == 1:
                if not categorized['event_start']:
                    categorized['event_start'] = line_dates[0]
                    assigned_dates.add(line_dates[0])
            elif len(line_dates) >= 2:
                if not categorized['event_start']:
                    categorized['event_start'] = line_dates[0]
                    assigned_dates.add(line_dates[0])
                if not categorized['event_end']:
                    categorized['event_end'] = line_dates[1]
                    assigned_dates.add(line_dates[1])
        
        elif any(kw in line_lower for kw in ['deadline', 'batas', 'tutup', 'terakhir']):
            if line_dates and not categorized['registration_end']:
                categorized['registration_end'] = line_dates[0]
                assigned_dates.add(line_dates[0])
        
        elif any(kw in line_lower for kw in ['pengumuman', 'announcement', 'pemenang']):
            if line_dates and not categorized['announcement_date']:
                categorized['announcement_date'] = line_dates[0]
                assigned_dates.add(line_dates[0])
    
    # If we have unassigned dates and missing categories, make educated guesses
    unassigned = [d for d in dates if d not in assigned_dates]
    if unassigned:
        # If we have dates but no registration_end, use the earliest unassigned
        if not categorized['registration_end'] and unassigned:
            categorized['registration_end'] = sorted(unassigned)[0]
    
    return categorized

def get_timestamp() -> str:
    """Generate timestamp string for filenames"""
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def sanitize_filename(filename: str) -> str:
    """Sanitize filename"""
    return re.sub(r'[^a-z0-9_-]', '_', filename.lower())
