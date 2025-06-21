# core/data_cleaner.py
# core/data_cleaner.py
import re
import logging
from datetime import datetime, timezone
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
        # Gunakan fungsi pengganti untuk memastikan kecocokan kata utuh dan case-insensitive
        text_lower = re.sub(r'\b' + indo + r'\b', eng, text_lower, flags=re.IGNORECASE)

    # Pengaturan untuk dateparser
    # REQUIRE_PARTS memastikan kita tidak mengambil tanggal parsial seperti 'juni' saja
    settings = {'PREFER_DATES_FROM': 'future', 'REQUIRE_PARTS': ['day', 'month']}
    
    found_dates = search_dates(text_lower, languages=['id'], settings=settings)

    if not found_dates:
        logger.warning(f"Dateparser tidak menemukan tanggal valid di: '{raw_date_text}'")
        return {'deadline': None, 'event_date_start': None, 'event_date_end': None}

    # Konversi semua tanggal yang ditemukan ke UTC
    datetimes = [dt.replace(tzinfo=timezone.utc) for _, dt in found_dates]

    # Logika dasar:
    # - Deadline adalah tanggal terjauh.
    # - Jika ada lebih dari satu tanggal, tanggal paling awal adalah awal acara, terjauh adalah akhir acara.
    
    deadline = max(datetimes)
    event_date_start = min(datetimes) if len(datetimes) > 1 else None
    event_date_end = max(datetimes) if len(datetimes) > 1 else None
    
    # Jika hanya ada satu tanggal, itu bisa jadi deadline dan juga tanggal acara.
    if len(datetimes) == 1:
        event_date_start = datetimes[0]
        event_date_end = datetimes[0]

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
    'ui-ux-design': ['ui/ux', 'ui-ux', 'user experience', 'user interface', 'figma', 'design system'],
    'web-development': ['webinar', 'workshop', 'seminar', 'talkshow', 'pelatihan', 'bootcamp', 'web development', 'frontend', 'backend', 'fullstack'],
    'mobile-development': ['mobile development', 'android', 'ios', 'flutter', 'react native'],
    'software-development': ['software development', 'software engineering', 'pemrograman', 'coding'],
    'data-science': ['data science', 'machine learning', 'deep learning', 'ai', 'artificial intelligence', 'analisis data', 'data analytics', 'analitika data'],
    'cyber-security': ['cyber security', 'keamanan siber', 'ctf', 'capture the flag', 'ethical hacker', 'hacking'],
    'game-development': ['game development', 'pengembangan game', 'unity', 'unreal engine'],
    'cloud-computing': ['cloud', 'cloud computing', 'aws', 'azure', 'gcp'],
    'internet-of-things': ['iot', 'internet of things'],
    'business-it-case': ['business case', 'studi kasus', 'business plan', 'ide bisnis', 'inovasi bisnis'],
    'esai-ilmiah': ['esai', 'essay', 'esai ilmiah'],
    'karya-tulis-ilmiah': ['karya tulis ilmiah', 'kti', 'lkti', 'paper', 'jurnal'],
    'desain-poster': ['desain poster', 'poster digital', 'digital poster', 'lomba poster'],
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


def clean_event_data(event: dict, categories: list[dict]) -> dict:
    """Main function to clean and normalize a single event dictionary."""
    # Clean title
    event['title'] = clean_title(event.get('title', ''))

    # Parse price and add new keys
    price_data = parse_price(event.get('price_info', ''))
    event['price_min'] = price_data['price_min']
    event['price_max'] = price_data['price_max']

    # Parse dates and add new keys
    date_data = parse_dates(event.get('date_raw_text', ''))
    event.update(date_data)

    # Enhance contact and registration info from description
    event = enhance_registration_info(event)

    # Ensure the 'url' field is set from the (potentially enhanced) registration_url
    event['url'] = event.get('registration_url')

    # Classify event into categories
    event['category_ids'] = classify_event(event, categories)

    # Remove old raw fields
    event.pop('price_info', None)
    event.pop('date_raw_text', None)

    return event

