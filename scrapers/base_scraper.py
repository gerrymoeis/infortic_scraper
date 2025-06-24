from core.logging_config import get_logger

class BaseScraper:
    """A base class for all scrapers, providing a common interface and functionality."""

    def __init__(self, debug=False):
        """Initializes the base scraper."""
        self.debug = debug
        # Get a logger specific to the concrete scraper's module name
        self.logger = get_logger(self.__class__.__module__)

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
