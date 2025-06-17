# core/logging_config.py
import logging
import sys

def setup_logging():
    """Configures the root logger for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)-25s - %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
            # Jika ingin menyimpan log ke file juga, uncomment baris di bawah
            # logging.FileHandler("scraper.log", mode='a')
        ]
    )
