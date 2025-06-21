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


def get_all_categories(supabase_client: Client) -> list[dict] | None:
    """Mengambil semua kategori dari tabel 'categories'."""
    try:
        logger.info("Mengambil daftar kategori dari Supabase...")
        response = supabase_client.table('categories').select('id, name, slug').execute()
        if response.data:
            logger.info(f"Berhasil mengambil {len(response.data)} kategori.")
            return response.data
        return []
    except PostgrestAPIError as e:
        logger.error(f"DATABASE ERROR: Gagal mengambil kategori. Pesan: {e.message}")
        return None
    except Exception as e:
        logger.error(f"Terjadi error tidak terduga saat mengambil kategori: {e}", exc_info=True)
        return None

def delete_expired_events(supabase_client: Client) -> int:
    """Menghapus event yang sudah kedaluwarsa dengan memanggil RPC delete_expired_events."""
    try:
        logger.info("Memanggil RPC untuk menghapus event yang sudah kedaluwarsa...")
        response = supabase_client.rpc('delete_expired_events', {}).execute()

        if response.data is not None:
            deleted_count = response.data
            if deleted_count > 0:
                logger.info(f"Berhasil menghapus {deleted_count} event yang sudah kedaluwarsa.")
            else:
                logger.info("Tidak ada event kedaluwarsa yang perlu dihapus.")
            return deleted_count
        else:
            logger.error(f"Gagal memanggil RPC delete_expired_events: {response.error}")
            return 0
            
    except PostgrestAPIError as e:
        logger.error(f"DATABASE ERROR saat memanggil RPC delete_expired_events: {e.message}")
        return 0
    except Exception as e:
        logger.error(f"Terjadi error tidak terduga saat menghapus event kedaluwarsa: {e}", exc_info=True)
        return 0

def get_event_type_id_by_name(supabase_client: Client, type_name: str) -> str | None:
    """Mengambil UUID dari event_type berdasarkan namanya."""
    try:
        logger.info(f"Mencari event_type_id untuk '{type_name}'...")
        response = supabase_client.table('event_types').select('id').eq('name', type_name).limit(1).execute()
        if response.data:
            type_id = response.data[0]['id']
            logger.info(f"Ditemukan event_type_id: {type_id}")
            return type_id
        else:
            logger.warning(f"Event type dengan nama '{type_name}' tidak ditemukan.")
            return None
    except PostgrestAPIError as e:
        logger.error(f"DATABASE ERROR: Gagal mengambil event_type_id untuk '{type_name}'. Pesan: {e.message}")
        return None
    except Exception as e:
        logger.error(f"Terjadi error tidak terduga saat mengambil event_type_id: {e}", exc_info=True)
        return None

def get_all_event_types(client: Client) -> dict | None:
    """Mengambil semua tipe acara dan mengembalikannya sebagai kamus nama:id."""
    try:
        response = client.table('event_types').select('id, name').execute()
        if response.data:
            # Konversi nama tipe menjadi huruf kecil untuk pencocokan yang tidak peka huruf besar-kecil
            return {item['name'].lower(): item['id'] for item in response.data}
        return {}
    except PostgrestAPIError as e:
        logger.error(f"DATABASE ERROR: Gagal mengambil tipe acara. Pesan: {e.message}")
        return None
    except Exception as e:
        logger.error(f"Terjadi error tidak terduga saat mengambil tipe acara: {e}", exc_info=True)
        return None

def save_events(supabase_client: Client, events_data: list):
    """Menyimpan daftar event ke Supabase dengan memanggil RPC upsert_event_with_categories."""
    if not events_data:
        logger.info("Tidak ada data event untuk disimpan.")
        return

    success_count = 0
    fail_count = 0
    logger.info(f"Mencoba menyimpan/memperbarui {len(events_data)} event ke Supabase melalui RPC...")

    for event in events_data:
        # Pisahkan category_ids dan event_type_id dari data utama event
        category_ids = event.pop('category_ids', [])
        event_type_id = event.pop('event_type_id', None)

        if not event_type_id:
            logger.warning(f"Event '{event.get('title', 'N/A')}' tidak memiliki event_type_id. Melewatkan...")
            fail_count += 1
            continue
        
        # Konversi datetime ke string ISO 8601
        for key, value in event.items():
            if isinstance(value, datetime):
                event[key] = value.isoformat()
        
        # Hapus field yang tidak relevan untuk tabel 'events'
        event.pop('source_name', None)
        event.pop('price', None)

        try:
            response = supabase_client.rpc(
                'upsert_event_with_categories',
                {
                    'p_event_data': event, 
                    'p_category_ids': category_ids,
                    'p_event_type_id': event_type_id
                }
            ).execute()

            if response.data:
                success_count += 1
            else:
                # Cek error dari Postgrest
                if hasattr(response, 'error') and response.error:
                    logger.error(f"Gagal menyimpan event '{event.get('title', 'N/A')}': {response.error.message}")
                else:
                    logger.error(f"Gagal menyimpan event '{event.get('title', 'N/A')}' tanpa pesan error spesifik.")
                fail_count += 1

        except PostgrestAPIError as e:
            logger.error(f"DATABASE ERROR saat RPC call untuk event '{event.get('title', 'N/A')}': {e.message}")
            fail_count += 1
        except Exception as e:
            logger.error(f"Terjadi error tidak terduga saat RPC call: {e}", exc_info=True)
            fail_count += 1
            
    logger.info(f"Proses penyimpanan selesai. Berhasil: {success_count}, Gagal: {fail_count}")
