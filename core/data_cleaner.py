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
    dan 'event_date_end' dengan analisis kontekstual. Semua datetime yang dikembalikan adalah timezone-aware (UTC).
    """
    if not raw_date_text or not isinstance(raw_date_text, str):
        return {'deadline': None, 'event_date_start': None, 'event_date_end': None}

    # Definisikan kata kunci untuk setiap peran tanggal
    deadline_keywords = ['deadline', 'pendaftaran', 'batas akhir', 'ditutup', 'terakhir']
    event_keywords = ['pelaksanaan', 'acara', 'berlangsung', 'tanggal acara', 'digelar pada', 'dimulai']

    # Inisialisasi hasil
    dates = {'deadline': None, 'event_date_start': None, 'event_date_end': None}
    
    # Normalisasi teks
    text_lower = raw_date_text.lower()

    # Pisahkan teks menjadi kalimat atau klausa untuk analisis terisolasi
    clauses = re.split(r'[.,;\n]', text_lower)
    
    # 1. Pencarian Berdasarkan Konteks
    for clause in clauses:
        if not clause.strip():
            continue

        found_in_clause = search_dates(clause, languages=['id'], settings={'PREFER_DATES_FROM': 'future'})
        if not found_in_clause:
            continue
        
        # Ambil semua tanggal yang ditemukan dalam klausa dan buat timezone-aware (UTC)
        clause_datetimes = [dt.replace(tzinfo=timezone.utc) for _, dt in found_in_clause]

        is_deadline_clause = any(keyword in clause for keyword in deadline_keywords)
        is_event_clause = any(keyword in clause for keyword in event_keywords)

        if is_deadline_clause:
            if not dates['deadline']:
                dates['deadline'] = max(clause_datetimes) # Ambil tanggal terakhir jika ada rentang
        
        elif is_event_clause:
            if not dates['event_date_start']:
                dates['event_date_start'] = min(clause_datetimes)
            if len(clause_datetimes) > 1 and not dates['event_date_end']:
                dates['event_date_end'] = max(clause_datetimes)

    # 2. Logika Fallback jika pencarian kontekstual tidak lengkap
    all_found_dates = sorted(list(set([dt.replace(tzinfo=timezone.utc) for _, dt in search_dates(text_lower, languages=['id'], settings={'PREFER_DATES_FROM': 'future'}) or []])))

    if not all_found_dates:
        return {'deadline': None, 'event_date_start': None, 'event_date_end': None}

    # Jika hanya satu tanggal ditemukan, asumsikan itu adalah deadline
    if len(all_found_dates) == 1:
        if not dates['deadline'] and not dates['event_date_start']:
            dates['deadline'] = all_found_dates[0]

    # Jika dua tanggal ditemukan
    elif len(all_found_dates) == 2:
        if not dates['deadline']:
            dates['deadline'] = all_found_dates[0]
        if not dates['event_date_start']:
            dates['event_date_start'] = all_found_dates[1]

    # Jika lebih dari dua tanggal ditemukan
    elif len(all_found_dates) > 2:
        if not dates['deadline']:
            dates['deadline'] = all_found_dates[0] # Asumsi tanggal pertama adalah deadline
        if not dates['event_date_start']:
            dates['event_date_start'] = all_found_dates[1] # Asumsi tanggal kedua adalah awal acara
        if not dates['event_date_end']:
            dates['event_date_end'] = all_found_dates[-1] # Asumsi tanggal terakhir adalah akhir acara

    # 3. Validasi dan Penyesuaian Akhir
    # Pastikan deadline tidak lebih lambat dari tanggal mulai acara
    if dates['deadline'] and dates['event_date_start'] and dates['deadline'] > dates['event_date_start']:
        logger.warning(f"Logika Peringatan: Deadline terdeteksi ({dates['deadline']}) lebih lambat dari tanggal mulai acara ({dates['event_date_start']}). Nilai akan ditukar.")
        dates['deadline'], dates['event_date_start'] = dates['event_date_start'], dates['deadline']

    # Pastikan event_date_end tidak lebih awal dari event_date_start
    if dates['event_date_start'] and dates['event_date_end'] and dates['event_date_end'] < dates['event_date_start']:
        dates['event_date_end'] = None
    
    # Jika event_date_end tidak ada tapi start ada, set end sama dengan start
    if dates['event_date_start'] and not dates['event_date_end']:
        dates['event_date_end'] = dates['event_date_start']

    # Pastikan deadline adalah tanggal yang paling akhir jika tidak masuk akal
    if dates['deadline'] and dates['event_date_start'] and dates['deadline'] < dates['event_date_start']:
        # Tukar jika deadline lebih awal dari acara (tidak umum, tapi bisa terjadi)
        logger.warning(f"Deadline {dates['deadline']} lebih awal dari tanggal mulai acara {dates['event_date_start']}. Menukar nilai.")
        dates['deadline'], dates['event_date_start'] = dates['event_date_start'], dates['deadline']

    return dates

def clean_title(title: str) -> str:
    """Removes common prefixes like [GRATIS] from the title."""
    if not title:
        return ''
    # Hapus kurung siku dan isinya (misal: [GRATIS], [ONLINE])
    cleaned_title = re.sub(r'\[.*?\]\s*', '', title).strip()
    return cleaned_title

def enhance_registration_info(event: dict) -> dict:
    """
    Enhances event data by extracting fallback registration URLs and organizers
    from the description text. It prioritizes Instagram handles.
    """
    description = event.get('description', '')
    if not description or not isinstance(description, str):
        return event

    # Proceed if registration_url is missing, empty, or just a copy of the source URL
    is_low_quality_fallback = event.get('registration_url') == event.get('url')
    if not event.get('registration_url') or is_low_quality_fallback:
        # 1. Prioritize Instagram handles
        # Regex to find handles like @username, avoiding email addresses
        ig_handle_match = re.search(r'(?<!\w)@([\w.]+)', description)
        if ig_handle_match:
            handle = ig_handle_match.group(1).strip('.') # Remove trailing dots
            event['registration_url'] = f"https://www.instagram.com/{handle}/"
            logger.info(f"Fallback: Found Instagram handle '@{handle}' and set it as registration_url for '{event.get('title')}'.")

    # Enhance organizer info separately
    if not event.get('organizer') or event.get('organizer') == 'N/A':
        ig_handle_match = re.search(r'(?<!\w)@([\w.]+)', description)
        if ig_handle_match:
            handle = ig_handle_match.group(1).strip('.')
            organizer_name = handle.replace('.', ' ').replace('_', ' ').title()
            event['organizer'] = organizer_name
            logger.info(f"Fallback: Found Instagram handle '@{handle}' and set '{organizer_name}' as organizer for '{event.get('title')}'.")
            
    return event


CATEGORY_KEYWORDS = {
    'web-development': ['web', 'website', 'frontend', 'backend', 'fullstack', 'react', 'vue', 'angular', 'laravel', 'php', 'node.js', 'django', 'flask'],
    'mobile-development': ['mobile', 'android', 'ios', 'flutter', 'react native', 'swift', 'kotlin'],
    'ui-ux-design': ['ui/ux', 'ui-ux', 'user interface', 'user experience', 'figma', 'sketch', 'adobe xd', 'wireframe', 'prototyping'],
    'desain-grafis': ['desain grafis', 'graphic design', 'photoshop', 'illustrator', 'coreldraw', 'poster', 'logo', 'branding'],
    'data-science': ['data science', 'data scientist', 'machine learning', 'analis data', 'pandas', 'numpy', 'scikit-learn'],
    'artificial-intelligence': ['artificial intelligence', 'ai', 'kecerdasan buatan', 'deep learning', 'tensorflow', 'pytorch'],
    'competitive-programming': ['competitive programming', 'cp', 'pemrograman kompetitif', 'icpc', 'gemastik', 'osn', 'problem solving'],
    'cyber-security': ['cyber security', 'keamanan siber', 'hacking', 'ethical hacking', 'penetration testing', 'ctf', 'capture the flag'],
    'game-development': ['game dev', 'game development', 'pengembangan game', 'unity', 'unreal engine'],
    'business-it-case': ['business case', 'studi kasus', 'business plan', 'ide bisnis', 'inovasi bisnis'],
    'esai-ilmiah': ['esai', 'essay', 'esai ilmiah'],
    'karya-tulis-ilmiah': ['karya tulis ilmiah', 'kti', 'lkti', 'paper', 'jurnal'],
    'desain-poster': ['desain poster', 'poster digital', 'lomba poster']
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
        keywords = CATEGORY_KEYWORDS.get(slug, [])
        for keyword in keywords:
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_to_analyze):
                category_ids.add(category['id'])
                break # Pindah ke kategori selanjutnya setelah satu kata kunci ditemukan
    
    if not category_ids:
        logger.warning(f"Tidak ada kategori yang dapat ditetapkan untuk acara: '{event.get('title')}'")

    return list(category_ids)

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

    # Classify event into categories
    event['category_ids'] = classify_event(event, categories)

    # Remove old raw fields
    event.pop('price_info', None)
    event.pop('date_raw_text', None)

    return event

