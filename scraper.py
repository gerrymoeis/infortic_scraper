import os
import json
import logging
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from core.database import get_supabase_client, get_or_create_source, save_events, get_all_categories, get_event_type_id_by_name, delete_expired_events
from core.data_cleaner import clean_event_data
from core.logging_config import setup_logging
from scrapers.infolomba_scraper import InfolombaScraper
from scrapers.informasilomba_scraper import InformasilombaScraper
from scrapers.infolombait_scraper import InfolombaitScraper
from scrapers.google_sheets_scraper import GoogleSheetsScraper

# Muat environment variables dari file .env
load_dotenv()

def json_datetime_serializer(obj):
    """Serializer JSON untuk objek yang tidak dapat diserialkan secara default oleh json."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Objek dengan tipe {type(obj).__name__} tidak dapat diserialkan JSON")

def main():
    """Fungsi utama untuk menjalankan dan mengorkestrasi semua proses scraping."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Memulai proses scraping...")
    
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Proses dihentikan karena koneksi ke Supabase gagal.")
        return

    # 1. Hapus event yang sudah kedaluwarsa dari database sebelum memulai
    logger.info("Memulai tahap pembersihan data event kedaluwarsa di database...")
    delete_expired_events(supabase)
    logger.info("Tahap pembersihan selesai.")

    categories = get_all_categories(supabase)
    if categories is None:
        logger.error("Tidak dapat mengambil data kategori dari database. Proses dihentikan.")
        return
    if not categories:
        logger.warning("Tabel kategori di database kosong. Klasifikasi tidak akan berjalan.")

    lomba_type_id = get_event_type_id_by_name(supabase, 'Lomba')
    if not lomba_type_id:
        logger.error("Tidak dapat menemukan ID untuk tipe acara 'Lomba'. Proses tidak dapat dilanjutkan.")
        return

    sources_to_scrape = [
        {
            "name": "infolomba.id",
            "url": "https://www.infolomba.id/",
            "scraper_class": InfolombaScraper
        },
        {
            "name": "informasilomba.com",
            "url": "https://www.informasilomba.com/",
            "scraper_class": InformasilombaScraper
        },
        {
            "name": "infolombait.com",
            "url": "https://www.infolombait.com/",
            "scraper_class": InfolombaitScraper
        },
        {
            "name": "google-sheets-himakom",
            "url": "https://docs.google.com/spreadsheets/u/0/d/1flUcng-naIX-YpjrxmVTUMiGwsuZmFKweazifHS5pNw/htmlview",
            "scraper_class": GoogleSheetsScraper
        }
    ]

    all_events = []

    for source_info in sources_to_scrape:
        logger.info(f"Memulai proses untuk sumber: {source_info['name']}")
        
        source_id = get_or_create_source(supabase, source_info['name'], source_info['url'])
        
        if not source_id:
            logger.warning(f"Gagal mendapatkan source_id untuk {source_info['name']}. Melanjutkan ke sumber berikutnya.")
            continue

        scraper_instance = source_info['scraper_class'](supabase, source_info['name'])
        scraped_events = scraper_instance.scrape()
        
        if scraped_events:
            logger.info(f"Selesai scrape dari {source_info['name']}, mendapatkan {len(scraped_events)} event mentah.")
            for event in scraped_events:
                event['source_id'] = source_id
            
            cleaned_events = [clean_event_data(event, categories) for event in scraped_events]
            
            # 2. Filter event yang sudah kedaluwarsa SEBELUM ditambahkan ke list utama
            valid_events = []
            now = datetime.now(timezone.utc)
            
            for event in cleaned_events:
                deadline = event.get('deadline')
                if deadline and deadline > now:
                    event['event_type_id'] = lomba_type_id
                    valid_events.append(event)
                else:
                    logger.warning(f"Melewatkan event '{event.get('title', 'N/A')}' karena sudah kedaluwarsa (Deadline: {deadline}).")

            if valid_events:
                logger.info(f"Menambahkan {len(valid_events)} event yang valid dari {source_info['name']} untuk disimpan.")
                all_events.extend(valid_events)
            else:
                logger.info(f"Tidak ada event baru yang valid dari {source_info['name']}.")

    if all_events:
        deduplicated_events = []
        seen_urls = set()
        for event in all_events:
            url = event.get('registration_url')
            if url not in seen_urls:
                deduplicated_events.append(event)
                seen_urls.add(url)
        
        if len(all_events) > len(deduplicated_events):
            logger.info(f"Mendeteksi dan menghapus {len(all_events) - len(deduplicated_events)} event duplikat dari batch.")

        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file_path = os.path.join(log_dir, f'scrape_log_{timestamp}.json')
        try:
            with open(log_file_path, 'w', encoding='utf-8') as f:
                json.dump(deduplicated_events, f, ensure_ascii=False, indent=4, default=json_datetime_serializer)
            logger.info(f"Log scraping telah disimpan di: {log_file_path}")
        except IOError as e:
            logger.error(f"Gagal menyimpan file log: {e}")

        save_events(supabase, deduplicated_events)
    else:
        logger.warning("Tidak ada event yang berhasil di-scrape dari semua sumber.")

    logger.info("Proses scraping selesai.")

if __name__ == "__main__":
    main()
