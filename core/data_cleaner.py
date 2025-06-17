# core/data_cleaner.py
# core/data_cleaner.py
import re
import logging
from datetime import datetime
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
    dan 'event_date_end' dengan analisis kontekstual.
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
    
    all_found_dates = []
    contextual_dates = []

    # 1. Pencarian Berdasarkan Konteks
    for clause in clauses:
        if not clause.strip():
            continue

        found_in_clause = search_dates(clause, languages=['id'], settings={'PREFER_DATES_FROM': 'future'})
        if not found_in_clause:
            continue
        
        # Ambil semua tanggal yang ditemukan dalam klausa
        clause_datetimes = [dt for _, dt in found_in_clause]
        contextual_dates.extend(clause_datetimes)

        is_deadline_clause = any(keyword in clause for keyword in deadline_keywords)
        is_event_clause = any(keyword in clause for keyword in event_keywords)

        if is_deadline_clause:
            if not dates['deadline']:
                dates['deadline'] = max(clause_datetimes) # Ambil tanggal terakhir jika ada rentang
        
        elif is_event_clause:
            if not dates['event_date_start']:
                dates['event_date_start'] = min(clause_datetimes)
            if len(clause_datetimes) > 1:
                if not dates['event_date_end']:
                    dates['event_date_end'] = max(clause_datetimes)

    # 2. Logika Fallback jika pencarian kontekstual tidak lengkap
    all_found_dates = sorted(list(set([dt for _, dt in search_dates(text_lower, languages=['id'], settings={'PREFER_DATES_FROM': 'future'}) or []])))

    if not all_found_dates:
        return {'deadline': None, 'event_date_start': None, 'event_date_end': None}

    # Jika deadline masih kosong, gunakan tanggal terakhir dari semua yang ditemukan
    if not dates['deadline']:
        dates['deadline'] = all_found_dates[-1]

    # Jika tanggal acara masih kosong, coba tentukan dari sisa tanggal
    if not dates['event_date_start']:
        potential_event_dates = [d for d in all_found_dates if d != dates['deadline']]
        if not potential_event_dates:
            potential_event_dates = all_found_dates # Jika hanya ada 1 tanggal, bisa jadi itu juga tanggal acara

        if potential_event_dates:
            dates['event_date_start'] = min(potential_event_dates)
            if len(potential_event_dates) > 1:
                dates['event_date_end'] = max(potential_event_dates)

    # 3. Koreksi Tahun
    current_year = datetime.now().year
    for key, value in dates.items():
        if value and value.year > current_year:
            try:
                corrected_date = value.replace(year=current_year)
                dates[key] = corrected_date
                logger.debug(f"Mengoreksi tahun untuk '{key}' dari {value.year} ke {current_year}")
            except ValueError:
                pass

    # 4. Final Cleanup
    if dates['event_date_start'] and dates['event_date_end'] and dates['event_date_end'] < dates['event_date_start']:
        dates['event_date_end'] = None

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

def clean_event_data(event: dict) -> dict:
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

    # Remove old raw fields
    event.pop('price_info', None)
    event.pop('date_raw_text', None)

    return event

