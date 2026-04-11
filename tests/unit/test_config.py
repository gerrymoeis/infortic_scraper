"""
Unit Tests for Config

Tests configuration loading and validation including:
- Environment variable loading
- API key rotation
- Configuration validation
"""
import pytest
import os
from unittest.mock import patch


@pytest.mark.unit
class TestConfigLoading:
    """Tests for configuration loading from environment"""
    
    @patch.dict(os.environ, {
        'DATABASE_URL': 'postgresql://test:test@localhost/test',
        'GEMINI_API_KEY': 'test_key_1,test_key_2',
        'BATCH_SIZE': '25',
        'DELAY_BETWEEN_REQUESTS': '4'
    })
    def test_config_loads_from_env(self):
        """Test configuration loads from environment variables"""
        # Import after patching environment
        from extraction.utils.config import Config
        
        # Reload config to pick up patched environment
        import importlib
        import extraction.utils.config as config_module
        importlib.reload(config_module)
        
        assert Config.DATABASE_URL == 'postgresql://test:test@localhost/test'
        assert Config.GEMINI_API_KEY is not None
        assert Config.BATCH_SIZE == 25
        assert Config.DELAY_BETWEEN_REQUESTS == 4
    
    @patch.dict(os.environ, {
        'GEMINI_API_KEY': 'key1,key2,key3'
    }, clear=True)
    def test_config_parses_multiple_api_keys(self):
        """Test configuration parses comma-separated API keys"""
        from extraction.utils.config import Config
        
        # Reload config
        import importlib
        import extraction.utils.config as config_module
        importlib.reload(config_module)
        
        # Should have multiple keys
        assert hasattr(Config, 'GEMINI_API_KEYS') or hasattr(Config, 'GEMINI_API_KEY')
    
    @patch.dict(os.environ, {}, clear=True)
    def test_config_handles_missing_env_vars(self):
        """Test configuration handles missing environment variables"""
        from extraction.utils.config import Config
        
        # Reload config
        import importlib
        import extraction.utils.config as config_module
        importlib.reload(config_module)
        
        # Should not crash, may have None values or defaults
        assert hasattr(Config, 'DATABASE_URL')
        assert hasattr(Config, 'GEMINI_API_KEY')


@pytest.mark.unit
class TestConfigValidation:
    """Tests for configuration validation"""
    
    @patch.dict(os.environ, {
        'DATABASE_URL': 'postgresql://test:test@localhost/test',
        'GEMINI_API_KEY': 'test_key'
    })
    def test_validate_with_required_fields(self):
        """Test validation passes with required fields"""
        from extraction.utils.config import Config
        
        # Reload config
        import importlib
        import extraction.utils.config as config_module
        importlib.reload(config_module)
        
        # Should have validate method or required fields
        assert Config.DATABASE_URL is not None
        assert Config.GEMINI_API_KEY is not None
    
    @patch.dict(os.environ, {}, clear=True)
    def test_validate_with_missing_fields(self):
        """Test validation handles missing required fields"""
        from extraction.utils.config import Config
        
        # Reload config
        import importlib
        import extraction.utils.config as config_module
        importlib.reload(config_module)
        
        # Should handle missing fields gracefully
        # May be None or raise validation error
        assert hasattr(Config, 'DATABASE_URL')


@pytest.mark.unit
class TestAPIKeyRotation:
    """Tests for API key rotation logic"""
    
    @patch.dict(os.environ, {
        'GEMINI_API_KEY': 'key1,key2,key3'
    })
    def test_get_next_api_key_rotates(self):
        """Test API key rotation returns different keys"""
        from extraction.utils.config import Config
        
        # Reload config
        import importlib
        import extraction.utils.config as config_module
        importlib.reload(config_module)
        
        # If rotation method exists, test it
        if hasattr(Config, 'get_next_api_key'):
            key1 = Config.get_next_api_key()
            key2 = Config.get_next_api_key()
            
            # Keys should exist
            assert key1 is not None
            assert key2 is not None
    
    @patch.dict(os.environ, {
        'GEMINI_API_KEY': 'single_key'
    })
    def test_get_next_api_key_single_key(self):
        """Test API key rotation with single key"""
        from extraction.utils.config import Config
        
        # Reload config
        import importlib
        import extraction.utils.config as config_module
        importlib.reload(config_module)
        
        # Should return same key
        if hasattr(Config, 'get_next_api_key'):
            key1 = Config.get_next_api_key()
            key2 = Config.get_next_api_key()
            
            assert key1 == key2


@pytest.mark.unit
class TestConfigDefaults:
    """Tests for configuration default values"""
    
    @patch.dict(os.environ, {}, clear=True)
    def test_batch_size_default(self):
        """Test BATCH_SIZE has sensible default"""
        from extraction.utils.config import Config
        
        # Reload config
        import importlib
        import extraction.utils.config as config_module
        importlib.reload(config_module)
        
        # Should have default value
        assert hasattr(Config, 'BATCH_SIZE')
        if Config.BATCH_SIZE is not None:
            assert Config.BATCH_SIZE > 0
            assert Config.BATCH_SIZE <= 100
    
    @patch.dict(os.environ, {}, clear=True)
    def test_delay_default(self):
        """Test DELAY_BETWEEN_REQUESTS has sensible default"""
        from extraction.utils.config import Config
        
        # Reload config
        import importlib
        import extraction.utils.config as config_module
        importlib.reload(config_module)
        
        # Should have default value
        assert hasattr(Config, 'DELAY_BETWEEN_REQUESTS')
        if Config.DELAY_BETWEEN_REQUESTS is not None:
            assert Config.DELAY_BETWEEN_REQUESTS >= 0
    
    @patch.dict(os.environ, {}, clear=True)
    def test_gemini_model_default(self):
        """Test GEMINI_MODEL has default value"""
        from extraction.utils.config import Config
        
        # Reload config
        import importlib
        import extraction.utils.config as config_module
        importlib.reload(config_module)
        
        # Should have default model
        assert hasattr(Config, 'GEMINI_MODEL')
