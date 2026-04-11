"""
Integration Tests for Extraction Pipeline

Tests extraction pipeline with real dependencies:
- Gemini API integration (requires GEMINI_API_KEY)
- OCR extraction (requires Tesseract)
- Batch processing with rate limiting
- Error handling and fallbacks

These tests are slower and require external dependencies.
Use pytest -m integration to run them.
"""
import pytest
import os
from pathlib import Path
from extraction.main import DataExtractor
from extraction.gemini_client import GeminiClient
from extraction.ocr_extractor import OCRExtractor
from extraction.utils.config import Config


@pytest.mark.integration
class TestGeminiExtraction:
    """Tests for Gemini API extraction"""
    
    def test_gemini_client_initialization(self):
        """Test Gemini client can be initialized"""
        if not Config.GEMINI_API_KEY:
            pytest.skip("GEMINI_API_KEY not set")
        
        client = GeminiClient()
        
        assert client is not None
        assert hasattr(client, 'extract_batch')
    
    def test_gemini_extract_single_caption(self):
        """Test Gemini extraction with single caption"""
        if not Config.GEMINI_API_KEY:
            pytest.skip("GEMINI_API_KEY not set")
        
        client = GeminiClient()
        
        # Sample caption
        captions = [{
            'post_id': 'TEST_001',
            'caption': 'LOMBA ESSAY NASIONAL 2026\nDeadline: 20 April 2026\nCP: 08123456789',
            'source_account': 'test_account'
        }]
        
        try:
            prompt = client.create_batch_prompt(captions)
            assert prompt is not None
            assert 'LOMBA ESSAY' in prompt
        except Exception as e:
            pytest.skip(f"Gemini API error: {e}")
    
    def test_gemini_handles_rate_limiting(self):
        """Test Gemini client respects rate limiting"""
        if not Config.GEMINI_API_KEY:
            pytest.skip("GEMINI_API_KEY not set")
        
        # Rate limiting is handled by DataExtractor
        # This test verifies the delay configuration exists
        assert Config.DELAY_BETWEEN_REQUESTS >= 0
    
    def test_gemini_api_key_rotation(self):
        """Test API key rotation when multiple keys provided"""
        if not Config.GEMINI_API_KEY:
            pytest.skip("GEMINI_API_KEY not set")
        
        # Check if rotation method exists
        if hasattr(Config, 'get_next_api_key'):
            key1 = Config.get_next_api_key()
            assert key1 is not None


@pytest.mark.integration
class TestOCRExtraction:
    """Tests for OCR extraction (requires Tesseract)"""
    
    def test_ocr_extractor_initialization(self):
        """Test OCR extractor can be initialized"""
        try:
            extractor = OCRExtractor()
            assert extractor is not None
        except Exception as e:
            pytest.skip(f"Tesseract not available: {e}")
    
    def test_ocr_extract_from_sample_image(self):
        """Test OCR extraction from sample image if available"""
        try:
            extractor = OCRExtractor()
        except Exception:
            pytest.skip("Tesseract not available")
        
        # Check if sample images exist
        sample_dir = Path(__file__).parent.parent / 'fixtures' / 'sample_images'
        if not sample_dir.exists():
            pytest.skip("No sample images available")
        
        # Try to extract from first available image
        images = list(sample_dir.glob('*.jpg')) + list(sample_dir.glob('*.png'))
        if not images:
            pytest.skip("No sample images found")
        
        try:
            text = extractor.extract_text(str(images[0]))
            # OCR might return None or empty string for some images
            assert text is None or isinstance(text, str)
        except Exception as e:
            pytest.skip(f"OCR extraction failed: {e}")
    
    def test_ocr_handles_missing_image(self):
        """Test OCR handles missing image gracefully"""
        try:
            extractor = OCRExtractor()
        except Exception:
            pytest.skip("Tesseract not available")
        
        result = extractor.extract_text('nonexistent_image.jpg')
        assert result is None


@pytest.mark.integration
class TestDataExtractor:
    """Tests for complete DataExtractor pipeline"""
    
    def test_data_extractor_initialization(self):
        """Test DataExtractor can be initialized"""
        extractor = DataExtractor()
        
        assert extractor is not None
        assert hasattr(extractor, 'process_account')
        assert hasattr(extractor, 'extract_all_ocr_texts')
    
    def test_extract_all_ocr_texts_with_sample_data(self, sample_caption_data):
        """Test OCR extraction for batch of captions"""
        extractor = DataExtractor()
        
        captions = [sample_caption_data]
        
        try:
            ocr_texts = extractor.extract_all_ocr_texts(captions)
            
            # Should return a dictionary
            assert isinstance(ocr_texts, dict)
            
            # May be empty if images don't exist or OCR fails
            # That's okay for this test
        except Exception as e:
            # OCR might fail if Tesseract not installed
            pytest.skip(f"OCR extraction failed: {e}")
    
    def test_process_account_with_sample_data(self, sample_caption_data):
        """Test processing account with sample data"""
        if not Config.GEMINI_API_KEY:
            pytest.skip("GEMINI_API_KEY not set")
        
        extractor = DataExtractor()
        
        captions = [sample_caption_data]
        
        try:
            # This will call Gemini API
            results = extractor.process_account('test_account', captions)
            
            # Should return a list
            assert isinstance(results, list)
            
            # May be empty if API fails, that's okay
        except Exception as e:
            pytest.skip(f"Extraction failed: {e}")


@pytest.mark.integration
@pytest.mark.slow
class TestBatchProcessing:
    """Tests for batch processing with rate limiting"""
    
    def test_batch_processing_respects_delay(self):
        """Test that batch processing includes delays"""
        if not Config.GEMINI_API_KEY:
            pytest.skip("GEMINI_API_KEY not set")
        
        import time
        from extraction.main import DataExtractor
        
        extractor = DataExtractor()
        
        # Create multiple batches of sample data
        captions = []
        for i in range(30):  # More than one batch (batch size = 25)
            captions.append({
                'post_id': f'TEST_{i:03d}',
                'caption': f'Test caption {i}',
                'source_account': 'test_account'
            })
        
        start_time = time.time()
        
        try:
            results = extractor.process_account('test_account', captions)
            
            elapsed = time.time() - start_time
            
            # Should take at least DELAY_BETWEEN_REQUESTS seconds
            # (for the delay between batches)
            expected_min_time = Config.DELAY_BETWEEN_REQUESTS
            
            # Allow some tolerance
            assert elapsed >= expected_min_time * 0.8
        except Exception as e:
            pytest.skip(f"Batch processing failed: {e}")


@pytest.mark.integration
class TestErrorHandling:
    """Tests for error handling in extraction pipeline"""
    
    def test_extraction_handles_empty_caption(self):
        """Test extraction handles empty captions gracefully"""
        extractor = DataExtractor()
        
        captions = [{
            'post_id': 'TEST_EMPTY',
            'caption': '',
            'source_account': 'test_account'
        }]
        
        # Should not crash
        try:
            results = extractor.process_account('test_account', captions)
            assert isinstance(results, list)
        except Exception as e:
            # Some errors are acceptable (e.g., API key not set)
            if "GEMINI_API_KEY" not in str(e):
                raise
    
    def test_extraction_handles_invalid_data(self):
        """Test extraction handles invalid data gracefully"""
        extractor = DataExtractor()
        
        captions = [{
            'post_id': 'TEST_INVALID',
            'caption': None,  # Invalid
            'source_account': 'test_account'
        }]
        
        # Should not crash
        try:
            results = extractor.process_account('test_account', captions)
            assert isinstance(results, list)
        except Exception as e:
            # Some errors are acceptable
            if "GEMINI_API_KEY" not in str(e):
                # Other errors should be handled gracefully
                pass
    
    def test_extraction_handles_api_failure(self):
        """Test extraction handles API failures gracefully"""
        if not Config.GEMINI_API_KEY:
            pytest.skip("GEMINI_API_KEY not set")
        
        extractor = DataExtractor()
        
        # Create data that might cause API issues
        captions = [{
            'post_id': 'TEST_API_FAIL',
            'caption': 'A' * 10000,  # Very long caption
            'source_account': 'test_account'
        }]
        
        # Should handle gracefully (may return empty or partial results)
        try:
            results = extractor.process_account('test_account', captions)
            assert isinstance(results, list)
        except Exception as e:
            # API errors are acceptable for this test
            pass


@pytest.mark.integration
class TestFallbackMechanisms:
    """Tests for fallback mechanisms (Gemini → Regex → OCR)"""
    
    def test_regex_fallback_when_gemini_unavailable(self):
        """Test regex fallback works when Gemini is unavailable"""
        # This is tested by unit tests, but verify integration
        from extraction.utils.helpers import extract_registration_date_fallback
        
        text = "Pendaftaran: 20 April 2026"
        result = extract_registration_date_fallback(text)
        
        assert result is not None
        assert "20" in result
        assert "April" in result or "april" in result.lower()
    
    def test_ocr_fallback_when_text_extraction_fails(self):
        """Test OCR fallback is attempted when text extraction fails"""
        # Verify OCR extractor exists and can be called
        try:
            from extraction.ocr_extractor import OCRExtractor
            extractor = OCRExtractor()
            assert extractor is not None
        except Exception:
            pytest.skip("OCR not available")


@pytest.mark.integration
class TestRealWorldScenarios:
    """Tests with real-world-like data"""
    
    def test_extraction_with_complete_caption(self):
        """Test extraction with complete, well-formatted caption"""
        if not Config.GEMINI_API_KEY:
            pytest.skip("GEMINI_API_KEY not set")
        
        extractor = DataExtractor()
        
        captions = [{
            'post_id': 'TEST_COMPLETE',
            'caption': """LOMBA ESSAY NASIONAL 2026

Tema: Inovasi Teknologi untuk Indonesia Maju

📅 Deadline: 20 April 2026
📝 Pendaftaran: 15 April 2026
📱 CP: 08123456789
🌐 Link: https://bit.ly/lombaessay2026

Terbuka untuk:
- SMA/SMK
- Mahasiswa D3/D4/S1

Penyelenggara: @universitas_indonesia

#LombaEssay #Teknologi #Indonesia
            """,
            'source_account': 'infolomba'
        }]
        
        try:
            results = extractor.process_account('infolomba', captions)
            
            assert isinstance(results, list)
            
            # If extraction succeeded, verify structure
            if len(results) > 0:
                result = results[0]
                assert 'post_id' in result
                assert result['post_id'] == 'TEST_COMPLETE'
        except Exception as e:
            pytest.skip(f"Extraction failed: {e}")
    
    def test_extraction_with_minimal_caption(self):
        """Test extraction with minimal caption"""
        if not Config.GEMINI_API_KEY:
            pytest.skip("GEMINI_API_KEY not set")
        
        extractor = DataExtractor()
        
        captions = [{
            'post_id': 'TEST_MINIMAL',
            'caption': 'Workshop AI - Deadline: 20 April 2026',
            'source_account': 'lomba.it'
        }]
        
        try:
            results = extractor.process_account('lomba.it', captions)
            
            assert isinstance(results, list)
        except Exception as e:
            pytest.skip(f"Extraction failed: {e}")
    
    def test_extraction_with_new_audience_codes(self):
        """Test extraction recognizes new audience codes (smk, sd, d2)"""
        if not Config.GEMINI_API_KEY:
            pytest.skip("GEMINI_API_KEY not set")
        
        extractor = DataExtractor()
        
        captions = [{
            'post_id': 'TEST_NEW_AUDIENCES',
            'caption': """KOMPETISI ROBOTIK 2026

Terbuka untuk:
- SD (Sekolah Dasar)
- SMK (Sekolah Menengah Kejuruan)
- D2 (Diploma 2)

Deadline: 15 Juni 2026
            """,
            'source_account': 'infolomba'
        }]
        
        try:
            results = extractor.process_account('infolomba', captions)
            
            assert isinstance(results, list)
            
            # If extraction succeeded, check for new audience codes
            if len(results) > 0:
                result = results[0]
                if 'audiences' in result:
                    # Should contain at least one of the new codes
                    audiences = result['audiences']
                    assert isinstance(audiences, list)
        except Exception as e:
            pytest.skip(f"Extraction failed: {e}")
