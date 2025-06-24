import os
import json
from datetime import datetime, timezone
from pydantic import HttpUrl
from dotenv import load_dotenv
# Import shared logger and setup function first
import logging
from core.shared_logger import logger, setup_logging

# Configure logging at the very beginning
# Configure logging at the very beginning
setup_logging()

# Now import the rest of the application modules
from core.database import get_supabase_client, get_or_create_source, save_competitions, get_all_categories, delete_expired_competitions
from core.data_cleaner import clean_competition_data
from scrapers.base_web_scraper import BaseWebScraper
from scrapers.infolomba_scraper import InfolombaScraper
from scrapers.informasilomba_scraper import InformasilombaScraper
from scrapers.infolombait_scraper import InfolombaitScraper

from scrapers.instagram_scraper import InstagramScraper
from scrapers.instagram_playwright_scraper import InstagramPlaywrightScraper

# Muat environment variables dari file .env
load_dotenv()

def json_datetime_serializer(obj):
    """Serializer JSON untuk objek yang tidak dapat diserialkan secara default oleh json."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, HttpUrl):
        return str(obj)
    raise TypeError(f"Objek dengan tipe {type(obj).__name__} tidak dapat diserialkan JSON")

def main():
    """Fungsi utama untuk menjalankan dan mengorkestrasi semua proses scraping."""
    # Set a global debug flag. Can be overridden by setting the DEBUG environment variable.
    DEBUG = True
    logger.info(f"Memulai proses scraping... (Mode Debug: {DEBUG})")

    supabase = get_supabase_client()
    if not supabase:
        logger.error("Proses dihentikan karena koneksi ke Supabase gagal.")
        return

    logger.info("Memulai tahap pembersihan data kompetisi kedaluwarsa di database...")
    delete_expired_competitions(supabase)
    logger.info("Tahap pembersihan selesai.")

    categories = get_all_categories(supabase)
    if categories is None:
        logger.error("Tidak dapat mengambil data kategori dari database. Proses dihentikan.")
        return



    sources_to_scrape = [
        # {"name": "infolomba.id", "url": "https://www.infolomba.id/", "scraper_class": InfolombaScraper, "default_event_type": "Lomba"},
        # Pausing development on this scraper due to persistent timeout issues.
        # {"name": "informasilomba.com", "url": "https://www.informasilomba.com/", "scraper_class": InformasilombaScraper, "default_event_type": "Lomba"},
        # {"name": "infolombait.com", "url": "https://www.infolombait.com/", "scraper_class": InfolombaitScraper, "default_event_type": "Lomba"}, # Paused: Site is offline (net::ERR_CONNECTION_TIMED_OUT)

        # The Instagram scraper will be re-integrated later when we add tables for other event types.
        # {"name": "instagram.com", "scraper_class": InstagramScraper, "default_event_type": "Lomba"},
        {"name": "instagram.com", "scraper_class": InstagramPlaywrightScraper, "default_event_type": "Lomba"},
    ]

    all_competitions = []
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
            scraper_class = source_info['scraper_class']
            
            # Use a context manager for web scrapers to handle browser lifecycle
            # Pass the correct arguments to the scraper constructor.
            # Note: The BaseWebScraper might need its own refactoring if it
            # doesn't follow the new BaseScraper constructor signature.
            if issubclass(scraper_class, BaseWebScraper):
                # This part might need adjustment if BaseWebScraper is refactored.
                with scraper_class(source_id=source_id, source_name=source_name, debug=DEBUG) as scraper_instance:
                    scraped_competitions = scraper_instance.scrape()
            else:
                scraper_instance = scraper_class(source_id=source_id, source_name=source_name, debug=DEBUG)
                scraped_competitions = scraper_instance.scrape()
            count = len(scraped_competitions)
            source_counts[source_name] = count
            logger.info(f"Selesai scrape dari {source_name}, mendapatkan {count} kompetisi mentah.")

            if not scraped_competitions:
                continue

            valid_competitions = []
            now = datetime.now(timezone.utc)

            for raw_competition in scraped_competitions:
                # 1. Enrich data with source info before cleaning
                raw_competition['source_id'] = source_id
                if not raw_competition.get('url'): # some scrapers might not provide it
                    raw_competition['url'] = source_info.get('url')

                # 2. Clean the competition data
                competition = clean_competition_data(raw_competition, categories)

                # 3. Validate the cleaned competition
                if not competition or not competition.get('title'):
                    logger.warning(f"Skipping competition from {source_name} due to missing title after cleaning.")
                    continue

                # Check for expiration: Skip if the deadline has passed
                if competition.get('deadline') and competition.get('deadline') < now:
                    logger.warning(f"Melewatkan kompetisi '{competition.get('title')}' karena sudah kedaluwarsa.")
                    continue
                
                # Final check for mandatory fields required by the database
                if not all(competition.get(key) for key in ['registration_url', 'poster_url', 'deadline']):
                    logger.warning(f"FINAL CHECK: Filtering competition '{competition.get('title')}' due to missing one or more mandatory fields (registration_url, poster_url, deadline).")
                    continue

                # If all checks pass, it's a valid competition
                valid_competitions.append(competition)

            if valid_competitions:
                logger.info(f"Menambahkan {len(valid_competitions)} kompetisi yang valid dari {source_name} untuk disimpan.")
                all_competitions.extend(valid_competitions)

        except Exception as e:
            logger.error(f"Caught an exception while running scraper: {source_name}")
            logger.error(f"Exception details for {source_name}:", exc_info=True)
            source_counts[source_name] = 'Gagal (Exception)'

    if all_competitions:
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file_path = os.path.join(log_dir, f'scrape_log_{timestamp}.json')
        try:
            # Convert HttpUrl to string for JSON serialization
            serializable_competitions = []
            for comp in all_competitions:
                comp_copy = comp.copy()
                for key, value in comp_copy.items():
                    if isinstance(value, HttpUrl):
                        comp_copy[key] = str(value)
                serializable_competitions.append(comp_copy)

            with open(log_file_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_competitions, f, ensure_ascii=False, indent=4, default=json_datetime_serializer)
            logger.info(f"Log scraping telah disimpan di: {log_file_path}")
        except (IOError, TypeError) as e:
            logger.error(f"Gagal menyimpan file log: {e}")

        logger.info(f"Saving {len(all_competitions)} validated competitions to the database...")
        save_competitions(supabase, all_competitions)
    else:
        logger.warning("Tidak ada kompetisi baru yang berhasil di-scrape dan divalidasi dari semua sumber.")

    logger.info('Proses scraping selesai.')
    logger.info('--- Ringkasan Hasil Scraping ---')
    for source, count in source_counts.items():
        logger.info(f'{source}: {count} acara')
    logger.info('--------------------------------')

if __name__ == "__main__":
    main()
