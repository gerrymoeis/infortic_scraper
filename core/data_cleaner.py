# core/data_cleaner.py
# core/data_cleaner.py
import re
import logging
from datetime import datetime, timezone
import dateparser
from dateparser.search import search_dates

logger = logging.getLogger(__name__)

def parse_price(price_text: str) -> dict[str, int | None]:
    """
    Parses a price string (e.g., "Gratis", "50k", "Rp 25.000 - 50.000")
    into a dictionary with price_min and price_max.
    """
    if not price_text or not isinstance(price_text, str):
        return {'price_min': None, 'price_max': None}

    price_text = price_text.lower()

    # Check for free
    if 'gratis' in price_text or 'free' in price_text:
        return {'price_min': 0, 'price_max': 0}

    # Find all numbers in the string (handles "10k", "50.000", etc.)
    # This regex finds numbers, optionally with dots/commas, and an optional 'k'
    numbers = re.findall(r'(\d[\d.,]*)(k)?', price_text)
    
    cleaned_numbers = []
    for num_str, k_suffix in numbers:
        # Remove thousand separators
        num_str = num_str.replace('.', '').replace(',', '')
        try:
            num = int(num_str)
            if k_suffix:
                num *= 1000
            cleaned_numbers.append(num)
        except ValueError:
            continue

    if not cleaned_numbers:
        return {'price_min': None, 'price_max': None}
    
    # Handle single price vs. price range
    if len(cleaned_numbers) == 1:
        return {'price_min': cleaned_numbers[0], 'price_max': cleaned_numbers[0]}
    else:
        # Assume the smallest is min and largest is max
        return {'price_min': min(cleaned_numbers), 'price_max': max(cleaned_numbers)}

def parse_dates(raw_date_text: str) -> dict[str, datetime | None]:
    """
    Menganalisis teks tanggal mentah untuk mengekstrak 'deadline', 'event_date_start',
    dan 'event_date_end'. Logika ini memprioritaskan tanggal terjauh yang ditemukan sebagai deadline.
    Semua datetime yang dikembalikan adalah timezone-aware (UTC).
    """
    if not raw_date_text or not isinstance(raw_date_text, str):
        return {'deadline': None, 'event_date_start': None, 'event_date_end': None}

    text_to_parse = raw_date_text.strip()
    if text_to_parse == '-':
        logger.debug("Parsing date string '-' as no deadline.")
        return {'deadline': None, 'event_date_start': None, 'event_date_end': None}

    text_lower = text_to_parse.lower()
    month_map = {
        'jan': 'january', 'feb': 'february', 'mar': 'march', 'apr': 'april',
        'mei': 'may', 'jun': 'june', 'jul': 'july', 'ags': 'august',
        'sep': 'september', 'okt': 'october', 'nov': 'november', 'des': 'december'
    }
    for indo, eng in month_map.items():
        text_lower = re.sub(r'\b' + indo + r'\b', eng, text_lower, flags=re.IGNORECASE)

    datetimes = []
    # --- Final, Robust Direct Parsing Logic for Ranges ---
    if ' - ' in text_lower:
        try:
            parts = text_lower.split(' - ')
            if len(parts) == 2:
                start_str, end_str = parts[0].strip(), parts[1].strip()
                logger.debug(f"Attempting direct parse on start='{start_str}', end='{end_str}'")

                end_date = dateparser.parse(end_str, settings={'PREFER_DATES_FROM': 'future'})
                if end_date:
                    # Handle start date: it could be just a day, or day-month
                    if start_str.isdigit(): # Case: "1 - 10 January 2025"
                        start_date = end_date.replace(day=int(start_str))
                    else: # Case: "10 Jan - 20 Feb 2025" or "December - January 2025"
                        # Add year if missing from start_str
                        if not re.search(r'\b\d{4}\b', start_str):
                            start_str_with_year = f"{start_str} {end_date.year}"
                        else:
                            start_str_with_year = start_str
                        start_date = dateparser.parse(start_str_with_year, settings={'PREFER_DATES_FROM': 'future'})
                    
                    if start_date:
                        # Crucial check for year crossover (e.g., Dec 2024 - Jan 2025)
                        if start_date > end_date:
                            start_date = start_date.replace(year=start_date.year - 1)
                        datetimes = sorted([start_date, end_date])
                        logger.debug(f"Successfully parsed range: {datetimes}")
        except Exception as e:
            logger.debug(f"Direct date range parsing failed for '{text_lower}': {e}. Falling back.")

    # --- Fallback to search_dates if direct parsing fails or isn't applicable ---
    if not datetimes:
        settings = {'PREFER_DATES_FROM': 'future', 'REQUIRE_PARTS': ['day', 'month']}
        found_dates = search_dates(text_lower, languages=['id'], settings=settings)
        if found_dates:
            datetimes = sorted([dt for _, dt in found_dates])

    if not datetimes:
        logger.warning(f"Dateparser tidak menemukan tanggal valid di: '{raw_date_text}'")
        return {'deadline': None, 'event_date_start': None, 'event_date_end': None}

    # Make datetimes timezone-aware
    aware_datetimes = [dt.replace(tzinfo=timezone.utc) for dt in datetimes]

    deadline = aware_datetimes[-1]
    event_date_start = aware_datetimes[0]
    event_date_end = aware_datetimes[-1]

    logger.debug(
        f"Parsed '{raw_date_text}' -> "
        f"Deadline: {deadline}, Start: {event_date_start}, End: {event_date_end}"
    )
    
    return {
        'deadline': deadline,
        'event_date_start': event_date_start,
        'event_date_end': event_date_end
    }

def clean_title(title: str) -> str:
    """Removes common prefixes and normalizes parts of the title."""
    if not title:
        return ''
    
    # Remove common conversational/announcement prefixes
    # e.g., "Dibuka, Pendaftaran Lomba..." -> "Lomba..."
    cleaned_title = re.sub(r'^(dibuka,?\s*)?(pendaftaran,?\s*)', '', title, flags=re.IGNORECASE)
    
    # Remove bracketed prefixes like [GRATIS], [LOMBA], etc.
    cleaned_title = re.sub(r'^\[.*?\]\s*', '', cleaned_title, flags=re.IGNORECASE)

    # Normalize year ranges like 2025/2025 to 2025
    cleaned_title = re.sub(r'(\d{4})/\1', r'\1', cleaned_title)
    
    return cleaned_title.strip()

def enhance_registration_info(event: dict) -> dict:
    """
    Enhances event data by extracting fallback registration URLs and organizers
    from the description text. It prioritizes Instagram handles and registration keywords.
    """
    description = event.get('description', '')
    if not description:
        return event

    # Fallback for registration_url if it's missing
    if not event.get('registration_url'):
        all_links = re.findall(r'https?://[\S]+', description)
        found_link = False
        # Prioritize links with registration keywords
        for link in all_links:
            # Simple check if keywords are in the text surrounding the link
            # A more robust solution might use BeautifulSoup if the description is HTML
            link_context_search = re.search(f"(daftar|registrasi|pendaftaran|register|form|bit\.ly|s\.id).{{0,50}}{re.escape(link)}", description, re.IGNORECASE)
            if link_context_search:
                event['registration_url'] = link.strip('.,')
                logger.info(f"Fallback: Found registration link via keyword: {event['registration_url']}")
                found_link = True
                break
        
        # If no keyword link, use the first non-social-media link as a fallback
        if not found_link and all_links:
            for link in all_links:
                if not any(social in link for social in ['instagram.com', 'facebook.com', 'twitter.com']):
                    event['registration_url'] = link.strip('.,')
                    logger.info(f"Fallback: Using first non-social link from description: {event['registration_url']}")
                    break

    # Fallback for organizer if it's missing
    if not event.get('organizer') or event.get('organizer') == 'N/A':
        # Try to find an Instagram handle mention
        ig_handle_match = re.search(r'(?<!\w)@([\w.]+)', description)
        if ig_handle_match:
            handle = ig_handle_match.group(1).strip('.')
            organizer_name = handle.replace('.', ' ').replace('_', ' ').title()
            event['organizer'] = organizer_name
            logger.info(f"Fallback: Found Instagram handle '@{handle}' and set '{organizer_name}' as organizer for '{event.get('title')}'.")

            
    return event


CLASSIFICATION_KEYWORDS = {
    'ui-ux-design': ['ui/ux', 'ui-ux', 'user experience', 'user interface', 'figma', 'design system', 'ux research'],
    'web-development': ['web development', 'web dev', 'frontend', 'backend', 'fullstack', 'website', 'web', 'html', 'css', 'javascript'],
    'mobile-development': ['mobile development', 'android', 'ios', 'flutter', 'react native', 'kotlin', 'swift'],
    'data-science': ['data science', 'machine learning', 'ml', 'artificial intelligence', 'ai', 'deep learning', 'data analysis', 'analitika data'],
    'competitive-programming': ['competitive programming', 'cp', 'pemrograman kompetitif', 'gemastik', 'icpc', 'olimpos', 'problem solving'],
    'business-it': ['business it', 'business plan', 'pitching', 'ide bisnis', 'business case', 'analisis bisnis', 'startup', 'wirausaha'],
    'cyber-security': ['cyber security', 'keamanan siber', 'hacking', 'ctf', 'capture the flag', 'ethical hacking'],
    'game-development': ['game development', 'game dev', 'pengembangan game', 'unity', 'unreal engine'],
    'esports': ['esports', 'e-sports', 'mobile legends', 'valorant', 'pubg', 'dota'],
    'karya-tulis-ilmiah': ['karya tulis ilmiah', 'kti', 'lkti', 'paper', 'jurnal', 'essay', 'esai', 'artikel ilmiah'],
    'desain-poster': ['desain poster', 'poster digital', 'digital poster', 'lomba poster', 'infografis', 'infographic'],
    'seminar-webinar': ['seminar', 'webinar', 'talkshow', 'workshop', 'pelatihan', 'bootcamp', 'career insight', 'tech talk'],
    'beasiswa': ['beasiswa', 'scholarship', 'djarum']
}

def classify_event(event: dict, categories: list[dict]) -> list[str]:
    """
    Menganalisis judul dan deskripsi acara untuk mengklasifikasikannya ke dalam satu atau lebih kategori.
    """
    category_ids = set()
    text_to_analyze = (event.get('title', '') + ' ' + event.get('description', '')).lower()

    if not text_to_analyze.strip():
        return []

    for category in categories:
        slug = category.get('slug')
        keywords = CLASSIFICATION_KEYWORDS.get(slug, [])
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_to_analyze):
                category_ids.add(category['id'])
                break # Pindah ke kategori selanjutnya setelah satu kata kunci ditemukan
    
    if not category_ids:
        logger.warning(f"Tidak ada kategori yang dapat ditetapkan untuk acara: '{event.get('title')}'")

    return list(category_ids)

def score_line_as_title(line: str) -> int:
    """Scores a line based on its likelihood of being an event title."""
    score = 0
    line_lower = line.lower()

    # Heavily penalize generic headlines
    shouty_patterns = [
        'we are hiring', 'open registration', 'we are open for internship', 'kesempatan emas',
        'daftar sekarang', 'link di bio', 'swipe left', 'dibuka pendaftaran', 'pendaftaran dibuka',
        'final call', 'deadline pendaftaran', 'open internship alert', 'internship opportunities',
        'dicari:', 'dibuka program', 'calling for', 'join us'
    ]
    if any(pattern in line_lower for pattern in shouty_patterns):
        score -= 100

    # Penalize lines that are just noise
    if line.startswith(('http', 'www', '#', '@', 'wa.me')):
        score -= 50
    if len(line.split()) < 3: # Too short to be a meaningful title
        score -= 20
    if len(line) > 150: # Too long
        score -= 20

    # Reward lines that look like titles
    if 15 < len(line) < 120:
        score += 30

    # Title Case is a very strong positive signal
    if line.istitle() and len(line.split()) > 2:
        score += 50

    # Presence of keywords is a good sign
    title_keywords = ['lomba', 'kompetisi', 'sayembara', 'beasiswa', 'scholarship', 'internship', 'magang', 'webinar', 'seminar', 'workshop', 'pelatihan', 'bootcamp', 'program']
    if any(keyword in line_lower for keyword in title_keywords):
        score += 40

    # Reward lines containing a proper name/organization (usually capitalized)
    if any(word.isupper() and len(word) > 3 for word in line.split()):
        score += 20

    return score

def extract_title_from_caption(caption: str) -> str:
    """
    Extracts the best possible title from a caption by scoring each line.
    """
    if not caption:
        return ""

    lines = [line.strip() for line in caption.split('\n') if line.strip()]
    if not lines:
        return ""

    # First, check for an explicit title in brackets, as it's a very strong signal
    for line in lines:
        match = re.search(r'\[(.*?)\]', line)
        if match:
            potential_title = match.group(1).strip()
            if 15 < len(potential_title) < 120 and score_line_as_title(potential_title) > 0:
                return potential_title

    # If no bracketed title, score all lines and find the best one
    scored_lines = []
    for line in lines:
        score = score_line_as_title(line)
        # Only consider lines with a positive score as potential titles
        if score > 0:
            scored_lines.append((score, line))

    if not scored_lines:
        return ""

    # Sort by score in descending order and return the line with the highest score
    scored_lines.sort(key=lambda x: x[0], reverse=True)
    
    best_title = scored_lines[0][1]
    
    # Final cleaning of the best title
    return clean_title(best_title)


def clean_competition_data(competition: dict, categories: list[dict]) -> dict:
    """Main function to clean and normalize a single competition dictionary."""
    
    # Enhance contact and registration info first, as it might affect other fields
    enhanced_competition = enhance_registration_info(competition)

    # --- Date Parsing Logic ---
    # Start with any dates provided by the scraper (e.g., post timestamp as event_date_start).
    final_dates = {
        'deadline': enhanced_competition.get('deadline'),
        'event_date_start': enhanced_competition.get('event_date_start'),
        'event_date_end': enhanced_competition.get('event_date_end'),
    }

    # Try to parse more specific dates from the text.
    parsed_dates = parse_dates(enhanced_competition.get('date_text', ''))

    # Merge the results, giving precedence to dates found in the text.
    # Only update if the parsed date is not None, preserving the fallback otherwise.
    if parsed_dates.get('deadline'):
        final_dates['deadline'] = parsed_dates['deadline']
    if parsed_dates.get('event_date_start'):
        final_dates['event_date_start'] = parsed_dates['event_date_start']
    if parsed_dates.get('event_date_end'):
        final_dates['event_date_end'] = parsed_dates['event_date_end']

    # Database requires a deadline. If no deadline was parsed, but we have a start date (from post timestamp),
    # use the start date as the deadline to satisfy the NOT NULL constraint.
    if not final_dates.get('deadline') and final_dates.get('event_date_start'):
        logger.info(f"No explicit deadline found for '{enhanced_competition.get('title', '')}'. Using event_date_start as fallback deadline.")
        final_dates['deadline'] = final_dates['event_date_start']

    # Classify the competition to get category IDs
    category_ids = classify_event(enhanced_competition, categories)

    # Build the final, clean dictionary
    clean_data = {
        'title': clean_title(enhanced_competition.get('title', '')),
        'description': enhanced_competition.get('description'),
        'organizer': enhanced_competition.get('organizer'),
        'url': enhanced_competition.get('url'),
        'registration_url': enhanced_competition.get('registration_url'),
        'poster_url': enhanced_competition.get('poster_url'),
        'source_id': enhanced_competition.get('source_id'),
        'participant': enhanced_competition.get('participant'),
        'location': enhanced_competition.get('location'),
        'date_text': enhanced_competition.get('date_text'),
        **final_dates,  # Adds deadline, event_date_start, event_date_end
        'category_ids': category_ids
    }
    
    return clean_data

