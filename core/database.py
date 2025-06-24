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

def delete_expired_competitions(supabase_client: Client) -> int:
    """Menghapus kompetisi yang sudah kedaluwarsa langsung dari tabel."""
    try:
        logger.info("Menghapus kompetisi yang sudah kedaluwarsa dari database...")
        response = supabase_client.table('competitions').delete().lt('deadline', datetime.now().isoformat()).execute()

        if response.data is not None:
            deleted_count = len(response.data)
            if deleted_count > 0:
                logger.info(f"Berhasil menghapus {deleted_count} kompetisi yang sudah kedaluwarsa.")
            else:
                logger.info("Tidak ada kompetisi kedaluwarsa yang perlu dihapus.")
            return deleted_count
        else:
            logger.error(f"Gagal menghapus kompetisi kedaluwarsa. Respons: {response}")
            return 0
            
    except PostgrestAPIError as e:
        logger.error(f"DATABASE ERROR saat menghapus kompetisi kedaluwarsa: {e.message}")
        return 0
    except Exception as e:
        logger.error(f"Terjadi error tidak terduga saat menghapus kompetisi kedaluwarsa: {e}", exc_info=True)
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

def save_competitions(supabase_client: Client, competitions_data: list):
    """Menyimpan daftar event ke Supabase dengan memanggil RPC upsert_event_with_categories."""
    if not competitions_data:
        logger.info("Tidak ada data kompetisi untuk disimpan.")
        return

    success_count = 0
    fail_count = 0
    logger.info(f"Mencoba menyimpan/memperbarui {len(competitions_data)} kompetisi ke Supabase melalui RPC...")

    for competition in competitions_data:
        # Pisahkan category_ids dari data utama kompetisi
        category_ids = competition.pop('category_ids', [])

        # Konversi datetime ke string ISO 8601
        for key, value in competition.items():
            if isinstance(value, datetime):
                competition[key] = value.isoformat()

        # Hapus field yang tidak relevan untuk payload RPC
        competition.pop('source_name', None)
        competition.pop('event_type_id', None) # No longer needed

        # Payload sudah bersih karena data cleaner, kita bisa langsung kirim
        try:
            response = supabase_client.rpc(
                'upsert_competition_with_categories',
                {
                    'p_competition_data': competition, 
                    'p_category_ids': category_ids
                }
            ).execute()

            if response.data:
                success_count += 1
            else:
                # Cek error dari Postgrest
                if hasattr(response, 'error') and response.error:
                    logger.error(f"Gagal menyimpan kompetisi '{competition.get('title', 'N/A')}': {response.error.message}")
                else:
                    logger.error(f"Gagal menyimpan kompetisi '{competition.get('title', 'N/A')}' tanpa pesan error spesifik.")
                fail_count += 1

        except PostgrestAPIError as e:
            logger.error(f"DATABASE ERROR saat RPC call untuk kompetisi '{competition.get('title', 'N/A')}': {e.message}")
            fail_count += 1
        except Exception as e:
            logger.error(f"Terjadi error tidak terduga saat RPC call: {e}", exc_info=True)
            fail_count += 1
            
    logger.info(f"Proses penyimpanan selesai. Berhasil: {success_count}, Gagal: {fail_count}")
