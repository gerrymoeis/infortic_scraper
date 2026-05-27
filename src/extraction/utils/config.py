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
    # GEMINI_API_KEY can contain comma-separated keys for rotation
    _api_keys_str = os.getenv('GEMINI_API_KEY', '')
    GEMINI_API_KEYS = [key.strip() for key in _api_keys_str.split(',') if key.strip()]
    GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else None  # Default to first key
    CURRENT_KEY_INDEX = 0  # Track which key we're using
    
    # OpenRouter API - Support multiple keys for rotation (FALLBACK)
    _openrouter_keys_str = os.getenv('OPENROUTER_API_KEYS', '')
    OPENROUTER_API_KEYS = [key.strip() for key in _openrouter_keys_str.split(',') if key.strip()]
    OPENROUTER_API_KEY = OPENROUTER_API_KEYS[0] if OPENROUTER_API_KEYS else None
    CURRENT_OPENROUTER_KEY_INDEX = 0
    
    # Primary service selection
    PRIMARY_SERVICE = os.getenv('PRIMARY_SERVICE', 'gemini')  # 'gemini' or 'openrouter'
    
    # Fallback settings
    USE_OPENROUTER_FALLBACK = os.getenv('USE_OPENROUTER_FALLBACK', 'true').lower() == 'true'
    
    # Model configuration - Use GA version (no -preview suffix)
    # GA version: gemini-3.1-flash-lite (Preview discontinued May 25, 2026)
    # BEST free tier limits: 15 RPM, 500 RPD, 250K TPM
    GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-3.1-flash-lite')
    FALLBACK_MODELS = [
        'gemini-3.1-flash-lite',  # GA version - best free tier limits
    ]
    CURRENT_MODEL_INDEX = 0  # Track which model we're using
    
    # Extractor settings
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', json_config.get('batchSize', 25)))
    DELAY_BETWEEN_REQUESTS = int(os.getenv('DELAY_BETWEEN_REQUESTS', json_config.get('delayBetweenRequests', 4)))
    TEMPERATURE = 0.1
    MAX_RETRIES = 3
    
    # Retry optimization (NEW: Reduced from 10 to 3 attempts, faster backoff)
    MAX_RETRY_ATTEMPTS = int(os.getenv('MAX_RETRY_ATTEMPTS', '3'))  # Reduced from 10
    MAX_BACKOFF_SECONDS = int(os.getenv('MAX_BACKOFF_SECONDS', '10'))  # Reduced from 30
    
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
    def get_next_openrouter_key(cls):
        """Rotate to next OpenRouter API key"""
        if len(cls.OPENROUTER_API_KEYS) <= 1:
            return cls.OPENROUTER_API_KEY
        
        cls.CURRENT_OPENROUTER_KEY_INDEX = (cls.CURRENT_OPENROUTER_KEY_INDEX + 1) % len(cls.OPENROUTER_API_KEYS)
        cls.OPENROUTER_API_KEY = cls.OPENROUTER_API_KEYS[cls.CURRENT_OPENROUTER_KEY_INDEX]
        return cls.OPENROUTER_API_KEY
    
    @classmethod
    def get_next_model(cls):
        """Rotate to next fallback model"""
        if len(cls.FALLBACK_MODELS) <= 1:
            return cls.GEMINI_MODEL
        
        cls.CURRENT_MODEL_INDEX = (cls.CURRENT_MODEL_INDEX + 1) % len(cls.FALLBACK_MODELS)
        cls.GEMINI_MODEL = cls.FALLBACK_MODELS[cls.CURRENT_MODEL_INDEX]
        return cls.GEMINI_MODEL
    
    @classmethod
    def reset_model(cls):
        """Reset to primary model"""
        cls.CURRENT_MODEL_INDEX = 0
        cls.GEMINI_MODEL = cls.FALLBACK_MODELS[0]
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        if not cls.GEMINI_API_KEYS or not cls.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEYS not set in environment")
        
        # Ensure directories exist
        cls.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        cls.FAILED_DIR.mkdir(parents=True, exist_ok=True)

config = Config()
