import os
import json
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from core.database import get_supabase_client, get_or_create_source, save_events
from core.data_cleaner import clean_event_data
from core.logging_config import setup_logging
from scrapers.infolomba_scraper import InfolombaScraper
from scrapers.informasilomba_scraper import InformasilombaScraper
from scrapers.infolombait_scraper import InfolombaitScraper

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
    
    # Inisialisasi Supabase client
    supabase = get_supabase_client()
    if not supabase:
        logger.error("Proses dihentikan karena koneksi ke Supabase gagal.")
        return

    # Definisikan sumber-sumber yang akan di-scrape
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
        }
        # Tambahkan sumber lain di sini di masa depan
    ]

    # List untuk menampung semua event dari berbagai sumber
    all_events = []

    for source_info in sources_to_scrape:
        logger.info(f"Memulai proses untuk sumber: {source_info['name']}")
        
        # Dapatkan atau buat ID sumber dari database
        source_id = get_or_create_source(supabase, source_info['name'], source_info['url'])
        
        if not source_id:
            logger.warning(f"Gagal mendapatkan source_id untuk {source_info['name']}. Melanjutkan ke sumber berikutnya.")
            continue

        # Inisialisasi dan panggil scraper
        scraper_instance = source_info['scraper_class'](supabase, source_info['name'])
        scraped_events = scraper_instance.scrape()
        
        if scraped_events:
            logger.info(f"Selesai scrape dari {source_info['name']}, mendapatkan {len(scraped_events)} event mentah.")
            # Tambahkan source_id ke setiap event
            for event in scraped_events:
                event['source_id'] = source_id
            # Bersihkan setiap event sebelum menambahkannya ke daftar utama
            cleaned_events = [clean_event_data(event) for event in scraped_events]
            all_events.extend(cleaned_events)

    # Simpan semua event yang terkumpul ke file log dan ke Supabase
    if all_events:
        # Buat folder logs jika belum ada
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Simpan hasil scrape ke file JSON dengan timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file_path = os.path.join(log_dir, f'scrape_log_{timestamp}.json')
        try:
            with open(log_file_path, 'w', encoding='utf-8') as f:
                json.dump(all_events, f, ensure_ascii=False, indent=4, default=json_datetime_serializer)
            logger.info(f"Log scraping telah disimpan di: {log_file_path}")
        except IOError as e:
            logger.error(f"Gagal menyimpan file log: {e}")

        # Simpan data ke Supabase
        save_events(supabase, all_events)
    else:
        logger.warning("Tidak ada event yang berhasil di-scrape dari semua sumber.")

    logger.info("Proses scraping selesai.")

if __name__ == "__main__":
    main()
