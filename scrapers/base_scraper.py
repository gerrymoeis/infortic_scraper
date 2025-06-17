import logging

class BaseScraper:
    """Kelas dasar untuk semua scraper, menyediakan antarmuka dan fungsionalitas umum."""

    def __init__(self, supabase_client, source_name):
        """Menginisialisasi scraper dengan koneksi Supabase dan nama sumber."""
        self.supabase = supabase_client
        self.source_name = source_name
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Scraper untuk {self.source_name} telah diinisialisasi.")

    def scrape(self):
        """
        Metode utama untuk melakukan scraping. Harus di-override oleh subclass.
        Metode ini harus mengembalikan daftar (list) dari kamus (dictionary),
        di mana setiap kamus mewakili satu event yang di-scrape.
        """
        raise NotImplementedError("Metode scrape() harus diimplementasikan oleh subclass.")

    def _deep_scrape(self, url):
        """
        Metode opsional untuk melakukan deep scraping pada halaman detail event.
        Dapat di-override oleh subclass jika diperlukan.
        """
        raise NotImplementedError("Metode _deep_scrape() belum diimplementasikan.")
