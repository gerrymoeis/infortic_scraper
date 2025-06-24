import logging
import os

class BaseScraper:
    """A base class for all scrapers, providing a common interface and functionality."""

    def __init__(self, source_id, source_name, debug=False, log_dir="logs"):
        """Initializes the scraper with a source ID and name."""
        self.source_id = source_id
        self.source_name = source_name
        self.debug = debug
        self.log_dir = log_dir
        self.logger = logging.getLogger(f"scrapers.{self.source_name}")

        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir)

        if self.debug:
            self.logger.setLevel(logging.INFO)
        else:
            self.logger.setLevel(logging.WARNING)

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
