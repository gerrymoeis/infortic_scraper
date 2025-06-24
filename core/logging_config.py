# core/logging_config.py
import logging
import sys

import os
import json
from datetime import datetime

class JsonFormatter(logging.Formatter):
    """Formats log records into a JSON string."""
    def format(self, record):
        log_data = {
            'timestamp': self.formatTime(record, self.datefmt),
            'level': record.levelname,
            'message': record.getMessage(),
            'source': record.name
        }
        # If the log record has extra data, add it to the JSON output.
        if hasattr(record, 'extra_data'):
            log_data.update(record.extra_data)
        return json.dumps(log_data, ensure_ascii=False)

def setup_logging(log_level=logging.DEBUG):
    """Configures the root logger for the application."""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Get the root logger instance
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Clear existing handlers to avoid duplicate logs
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create a standard formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)-25s - %(levelname)-8s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # --- Handlers ---
    now = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    # 1. Console Handler
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except (TypeError, AttributeError):
        pass  # Proceed with default encoding if reconfigure fails
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 2. Debug File Handler (for detailed, human-readable logs)
    debug_log_file = os.path.join(log_dir, f"scrape_debug_{now}.log")
    debug_file_handler = logging.FileHandler(debug_log_file, mode='w', encoding='utf-8')
    debug_file_handler.setFormatter(formatter)
    debug_file_handler.setLevel(logging.DEBUG) # Capture everything from DEBUG upwards
    logger.addHandler(debug_file_handler)

    # 3. JSON File Handler (for structured, machine-readable logs)
    json_log_file = os.path.join(log_dir, f"scrape_log_{now}.json")
    json_file_handler = logging.FileHandler(json_log_file, mode='w', encoding='utf-8')
    json_file_handler.setFormatter(JsonFormatter())
    json_file_handler.setLevel(logging.INFO) # Only capture INFO and above for the JSON log
    logger.addHandler(json_file_handler)
