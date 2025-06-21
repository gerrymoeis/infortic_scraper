# core/logging_config.py
import logging
import sys

def setup_logging():
    """Configures the shared 'infortic_scraper' logger for the application."""
    # Get the shared logger instance
    logger = logging.getLogger('infortic_scraper')
    logger.setLevel(logging.INFO)

    # Clear existing handlers to avoid duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create a formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)-25s - %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Create and add the file handler
    file_handler = logging.FileHandler("scraper.log", mode='w', encoding='utf-8')
    file_handler.setFormatter(formatter)
    # Add the handlers to the shared logger
    logger.addHandler(file_handler)

    # Create and add the console handler
    # This attempts to set the console encoding to UTF-8 to prevent UnicodeEncodeError on Windows.
    try:
        # This is the modern way for Python 3.7+
        sys.stdout.reconfigure(encoding='utf-8')
    except (TypeError, AttributeError):
        # This can happen in some environments (like non-console outputs).
        # In this case, we proceed with the default encoding.
        pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
