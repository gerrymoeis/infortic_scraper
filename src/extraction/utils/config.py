"""
Configuration loader for extractor
"""

import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent.parent.parent / 'config' / '.env'
load_dotenv(env_path, override=True)

# Load JSON config
config_path = Path(__file__).parent.parent.parent.parent / 'config' / 'scraper.config.json'
with open(config_path, 'r') as f:
    json_config = json.load(f)

class Config:
    # Gemini API - Support multiple keys for rotation
    _api_keys_str = os.getenv('GEMINI_API_KEYS', os.getenv('GEMINI_API_KEY', ''))
    GEMINI_API_KEYS = [key.strip() for key in _api_keys_str.split(',') if key.strip()]
    GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else None  # Default to first key
    CURRENT_KEY_INDEX = 0  # Track which key we're using
    
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
    
    # Extractor settings
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', json_config.get('batchSize', 25)))
    DELAY_BETWEEN_REQUESTS = int(os.getenv('DELAY_BETWEEN_REQUESTS', json_config.get('delayBetweenRequests', 4)))
    TEMPERATURE = 0.1
    MAX_RETRIES = 3
    
    # Paths
    OUTPUT_DIR = Path(os.getenv('OUTPUT_DIR', 'data/raw'))
    PROCESSED_DIR = Path(os.getenv('PROCESSED_DIR', 'data/processed'))
    FAILED_DIR = Path(os.getenv('FAILED_DIR', 'data/failed'))
    
    # Database
    DATABASE_URL = os.getenv('DATABASE_URL')
    
    @classmethod
    def get_next_api_key(cls):
        """Rotate to next API key"""
        if len(cls.GEMINI_API_KEYS) <= 1:
            return cls.GEMINI_API_KEY
        
        cls.CURRENT_KEY_INDEX = (cls.CURRENT_KEY_INDEX + 1) % len(cls.GEMINI_API_KEYS)
        cls.GEMINI_API_KEY = cls.GEMINI_API_KEYS[cls.CURRENT_KEY_INDEX]
        return cls.GEMINI_API_KEY
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.GEMINI_API_KEYS or not cls.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEYS not set in environment")
        
        # Ensure directories exist
        cls.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        cls.FAILED_DIR.mkdir(parents=True, exist_ok=True)

config = Config()
