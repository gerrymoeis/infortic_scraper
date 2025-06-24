import logging
import os
from datetime import datetime

# Create a single, shared logger instance for the entire application.
logger = logging.getLogger('infortic_scraper')

def setup_logging():
    """Configures the root logger for the application robustly."""
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_filename = f"scrape_debug_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"
    log_filepath = os.path.join(log_dir, log_filename)

    # Get the root logger and clear its handlers to avoid duplicate logs
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Set level for the root logger to INFO to avoid overly verbose logs from libraries
    root_logger.setLevel(logging.INFO)

    # Set the level for the application-specific logger to DEBUG
    logging.getLogger('infortic_scraper').setLevel(logging.DEBUG)

    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)-25s - %(levelname)-8s - %(message)s')

    # Create and configure file handler
    file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
    file_handler.setFormatter(formatter)

    # Create and configure stream handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)

    # Add handlers to the root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    # Use the root logger to confirm setup
    logging.getLogger().info(f"Debug log will be saved to {log_filepath}")
