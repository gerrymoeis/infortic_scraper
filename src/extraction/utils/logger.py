"""
Logging utility for Python extractor
"""

import logging
import sys
from pathlib import Path
from datetime import datetime

class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors"""
    
    COLORS = {
        'DEBUG': '\033[90m',    # Gray
        'INFO': '\033[36m',     # Cyan
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)

def setup_logger(name='extractor'):
    """Setup logger with file and console handlers with proper Unicode support"""
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Console handler with UTF-8 encoding for cross-platform Unicode support
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    
    # Configure UTF-8 encoding with graceful fallback for Windows
    # This prevents UnicodeEncodeError on Windows consoles that don't support UTF-8
    if hasattr(console_handler.stream, 'reconfigure'):
        try:
            # Try to reconfigure stream to UTF-8 with 'replace' error handling
            # 'replace' will substitute unsupported characters with '?' instead of crashing
            console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            # If reconfigure fails, wrap the stream with a UTF-8 writer
            try:
                import codecs
                console_handler.stream = codecs.getwriter('utf-8')(
                    console_handler.stream.buffer, errors='replace'
                )
            except Exception:
                # Last resort: continue with default encoding
                pass
    
    console_formatter = ColoredFormatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    
    # File handler with UTF-8 encoding
    log_dir = Path(__file__).parent.parent.parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"{name}_{datetime.now().strftime('%Y-%m-%d')}.log"
    file_handler = logging.FileHandler(log_file, encoding='utf-8', errors='replace')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
