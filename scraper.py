import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

# Import shared logger and setup function first
from core.shared_logger import logger
from core.logging_config import setup_logging

# Configure logging at the very beginning
setup_logging()

# Now import the rest of the application modules
from core.database import get_supabase_client, get_or_create_source, save_events, get_all_categories, get_all_event_types, delete_expired_events
from core.data_cleaner import clean_event_data
from scrapers.infolomba_scraper import InfolombaScraper
from scrapers.informasilomba_scraper import InformasilombaScraper
from scrapers.infolombait_scraper import InfolombaitScraper
from scrapers.himakom_scraper import HimakomScraper
from scrapers.rnd_info_center_scraper import RndInfoCenterScraper
from scrapers.hmit_its_portal_scraper import HmitItsPortalScraper
from scrapers.instagram_scraper import InstagramScraper
from scrapers.sahakara_scraper import SahakaraScraper
from scrapers.rkim_scraper import RkimScraper

# Muat environment variables dari file .env
load_dotenv()

def json_datetime_serializer(obj):
    """Serializer JSON untuk objek yang tidak dapat diserialkan secara default oleh json."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Objek dengan tipe {type(obj).__name__} tidak dapat diserialkan JSON")

def main():
    """Fungsi utama untuk menjalankan dan mengorkestrasi semua proses scraping."""
    # Set a global debug flag. Can be overridden by setting the DEBUG environment variable.
    DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
    logger.info(f"Memulai proses scraping... (Mode Debug: {DEBUG})")

    supabase = get_supabase_client()
    if not supabase:
        logger.error("Proses dihentikan karena koneksi ke Supabase gagal.")
        return

    logger.info("Memulai tahap pembersihan data event kedaluwarsa di database...")
    delete_expired_events(supabase)
    logger.info("Tahap pembersihan selesai.")

    categories = get_all_categories(supabase)
    if categories is None:
        logger.error("Tidak dapat mengambil data kategori dari database. Proses dihentikan.")
        return

    event_types_map = get_all_event_types(supabase)
    if event_types_map is None:
        logger.error("Tidak dapat mengambil tipe acara dari database. Proses dihentikan.")
        return

    sources_to_scrape = [
        {"name": "infolomba.id", "url": "https://www.infolomba.id/", "scraper_class": InfolombaScraper, "default_event_type": "Lomba"},
        {"name": "informasilomba.com", "url": "https://www.informasilomba.com/", "scraper_class": InformasilombaScraper, "default_event_type": "Lomba"},
        {"name": "infolombait.com", "url": "https://www.infolombait.com/", "scraper_class": InfolombaitScraper, "default_event_type": "Lomba"},
        {"name": "google-sheets-himakom", "url": "https://docs.google.com/spreadsheets/u/0/d/1flUcng-naIX-YpjrxmVTUMiGwsuZmFKweazifHS5pNw/htmlview", "scraper_class": HimakomScraper, "default_event_type": "Lomba"},
        {"name": "google-sheets-rnd-info-center", "url": "https://docs.google.com/spreadsheets/d/1WLZSnPJ28EFXR66ObiCmqpqk1ffDREI_t5DSGrhd35Q/edit", "scraper_class": RndInfoCenterScraper, "default_event_type": None},
        {"name": "google-sheets-hmit-its", "url": "https://docs.google.com/spreadsheets/d/1qjvZtMiW2qqeIOChAFXLS5vSzZQo53oit60XvYW6mL0/edit", "scraper_class": HmitItsPortalScraper, "default_event_type": None},
        {"name": "google-sheets-sahakara", "url": "https://docs.google.com/spreadsheets/d/13Sj2uE5w5g_2-t3E-2gqY-x-k1gC-zCg/edit#gid=1795333832", "scraper_class": SahakaraScraper, "default_event_type": "Lomba"},
        {"name": "google-sheets-rkim", "url": "https://docs.google.com/spreadsheets/d/1E1b__7-43-S_6e-A2a2-t_c-Y_t_c-Y_t_c-Y_t_c-Y_t_c-Y_t_c-Y/edit#gid=0", "scraper_class": RkimScraper, "default_event_type": "Lomba"},
        {"name": "instagram", "url": "https://www.instagram.com/", "scraper_class": InstagramScraper, "default_event_type": None}
    ]

    all_events = []
    source_counts = {}

    for source_info in sources_to_scrape:
        source_name = source_info['name']
        source_url = source_info.get('url', '')
        logger.info(f"Memulai proses untuk sumber: {source_name}")
        
        source_id = get_or_create_source(supabase, source_name, source_url)
        if not source_id:
            logger.warning(f"Gagal mendapatkan source_id untuk {source_name}. Melanjutkan ke sumber berikutnya.")
            source_counts[source_name] = 'Gagal (Source ID)'
            continue

        try:
            scraper_instance = source_info['scraper_class'](supabase, source_name, debug=DEBUG)
            scraped_events = scraper_instance.scrape()
            count = len(scraped_events)
            source_counts[source_name] = count
            logger.info(f"Selesai scrape dari {source_name}, mendapatkan {count} event mentah.")

            if not scraped_events:
                continue

            valid_events = []
            now = datetime.now(timezone.utc)

            for raw_event in scraped_events:
                # 1. Enrich data with source info before cleaning
                raw_event['source_name'] = source_name
                if not raw_event.get('source_url'):
                    raw_event['source_url'] = source_url

                # 2. Clean the event data
                event = clean_event_data(raw_event, categories)

                # 3. Validate the cleaned event
                if not event:
                    continue

                # Critical check: Ensure title is not empty after cleaning
                if not event.get('title'):
                    logger.warning(f"Skipping event from {source_name} due to missing title after cleaning.")
                    continue

                # Check for expiration: Skip if the deadline has passed
                if event.get('deadline') and event.get('deadline') < now:
                    logger.warning(f"Melewatkan event '{event.get('title')}' karena sudah kedaluwarsa.")
                    continue

                # Check for event type
                event_type_name = event.get('event_type') or source_info.get('default_event_type')
                if not event_type_name:
                    logger.warning(f"Tipe acara tidak ditemukan untuk '{event.get('title')}', melewati.")
                    continue
                
                event_type_id = event_types_map.get(event_type_name.lower())
                if not event_type_id:
                    logger.warning(f"Tipe acara '{event_type_name}' tidak valid untuk '{event.get('title')}', melewati.")
                    continue
                
                # If all checks pass, it's a valid event
                event['event_type_id'] = event_type_id
                event['source_id'] = source_id
                valid_events.append(event)

            if valid_events:
                logger.info(f"Menambahkan {len(valid_events)} event yang valid dari {source_name} untuk disimpan.")
                all_events.extend(valid_events)

        except Exception as e:
            logger.error(f"Error saat menjalankan scraper {source_name}: {e}", exc_info=True)
            source_counts[source_name] = 'Gagal (Exception)'

    if all_events:
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file_path = os.path.join(log_dir, f'scrape_log_{timestamp}.json')
        try:
            with open(log_file_path, 'w', encoding='utf-8') as f:
                json.dump(all_events, f, ensure_ascii=False, indent=4, default=json_datetime_serializer)
            logger.info(f"Log scraping telah disimpan di: {log_file_path}")
        except IOError as e:
            logger.error(f"Gagal menyimpan file log: {e}")

        save_events(supabase, all_events)
    else:
        logger.warning("Tidak ada event baru yang berhasil di-scrape dan divalidasi dari semua sumber.")

    logger.info('Proses scraping selesai.')
    logger.info('--- Ringkasan Hasil Scraping ---')
    for source, count in source_counts.items():
        logger.info(f'{source}: {count} acara')
    logger.info('--------------------------------')

if __name__ == "__main__":
    main()
