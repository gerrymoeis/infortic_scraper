# core/logging_config.py
import logging
import sys
from logging.handlers import RotatingFileHandler
import os
from datetime import datetime

# Define the root logger for the application
APP_LOGGER_NAME = 'infortic_scraper'

def setup_logging(debug=False):
    """
    Configures the application's logging setup.
    This function should be called only once, at the application's entry point.
    """
    log_level = logging.DEBUG if debug else logging.INFO
    
    # Get the application's root logger
    logger = logging.getLogger(APP_LOGGER_NAME)
    logger.setLevel(log_level)

    # Prevent log messages from being propagated to the root logger
    logger.propagate = False

    # Clear existing handlers to prevent duplicates if this function is ever called more than once
    if logger.hasHandlers():
        logger.handlers.clear()

    # --- Formatter ---
    formatter = logging.Formatter(
        '%(asctime)s - %(name)-25s - %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # --- Handlers ---
    # 1. Console Handler
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (TypeError, AttributeError):
        pass  # Proceed with default encoding
    
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. Rotating File Handler for debug logs
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_filename = os.path.join(log_dir, "scraper_debug.log")
    # Rotating file handler: 5MB per file, keeps backup of last 5 logs
    file_handler = RotatingFileHandler(log_filename, maxBytes=5*1024*1024, backupCount=5, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.info("Logging configured.")
    logger.debug(f"Log level set to {'DEBUG' if debug else 'INFO'}.")

def get_logger(name):
    """Helper function to get a logger instance with the correct parent."""
    return logging.getLogger(f"{APP_LOGGER_NAME}.{name}")
