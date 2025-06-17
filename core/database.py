import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client, PostgrestAPIError

logger = logging.getLogger(__name__)

# Muat environment variables dari file .env
def load_env():
    # Tentukan path ke file .env
    # Ini mengasumsikan file .env berada di root direktori proyek (satu level di atas 'core')
    dotenv_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    load_dotenv(dotenv_path=dotenv_path)

def get_supabase_client() -> Client | None:
    """Membuat dan mengembalikan Supabase client."""
    load_env()
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_KEY")
    
    if not url or not key:
        logger.error("Error: Pastikan SUPABASE_URL dan SUPABASE_SERVICE_KEY sudah diatur di file .env")
        return None
        
    try:
        return create_client(url, key)
    except Exception as e:
        logger.critical(f"Gagal menginisialisasi Supabase client: {e}")
        return None

def get_or_create_source(supabase_client: Client, source_name: str, source_url: str) -> str | None:
    """Mencari atau membuat source dengan memanggil fungsi database get_or_create_source_id via RPC."""
    try:
        logger.info(f"Memanggil fungsi RPC 'get_or_create_source_id' untuk sumber: {source_name}")
        # Panggil fungsi di database
        response = supabase_client.rpc(
            'get_or_create_source_id',
            {'p_source_name': source_name, 'p_source_url': source_url}
        ).execute()

        # response.data akan berisi ID yang dikembalikan oleh fungsi
        if response.data:
            source_id = response.data
            logger.info(f"Berhasil mendapatkan source_id: {source_id}")
            return source_id
        else:
            # Ini seharusnya tidak terjadi jika fungsi DB bekerja dengan benar
            logger.error(f"Gagal mendapatkan source_id dari RPC call: {response.error}")
            return None
    except PostgrestAPIError as e:
        logger.error(f"Gagal memanggil RPC get_or_create_source_id untuk '{source_name}': {e.message}")
        return None
    except Exception as e:
        logger.error(f"Terjadi error tidak terduga saat memanggil RPC: {e}", exc_info=True)
        return None


def save_events(supabase_client: Client, events_data: list):
    """Menyimpan daftar event ke tabel 'events' di Supabase menggunakan upsert."""
    if not events_data:
        logger.info("Tidak ada data event untuk disimpan.")
        return

    try:
        logger.info(f"Mencoba menyimpan/memperbarui {len(events_data)} event ke Supabase...")
        
        # Konversi datetime ke string ISO 8601 dan hapus field yang tidak perlu
        for event in events_data:
            for key, value in event.items():
                if isinstance(value, datetime):
                    event[key] = value.isoformat()
            event.pop('source_name', None) # Tidak ada di tabel events
            event.pop('price', None)       # Kolom usang, digantikan price_min/max

        response = supabase_client.table('events').upsert(
            events_data, 
            on_conflict='url' # Kolom unik untuk mencegah duplikat
        ).execute()
        
        logger.info(f"Sukses! {len(response.data)} baris berhasil di-upsert ke tabel 'events'.")

    except PostgrestAPIError as e:
        logger.error(f"DATABASE ERROR: Gagal menyimpan data ke Supabase. Pesan: {e.message}")
    except Exception as e:
        logger.error(f"Terjadi error tidak terduga saat menyimpan data: {e}", exc_info=True)
