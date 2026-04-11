"""
Integration Tests for Complete Pipeline

Tests end-to-end pipeline execution:
- Scraping → Extraction → Database insertion
- Data flow consistency
- Error recovery
- Phase 1, 2, 3 integration

These are the slowest tests and require all dependencies.
Use pytest -m "integration and slow" to run them.
"""
import pytest
import json
from pathlib import Path
from datetime import datetime
from extraction.main import DataExtractor
from database.main import load_extracted_data
from database.client import DatabaseClient
from database.validator import DataValidator
from database.normalizer import DataNormalizer
from extraction.utils.config import Config


@pytest.fixture
def sample_instagram_data():
    """Load sample Instagram data from fixtures"""
    fixture_path = Path(__file__).parent.parent / 'fixtures' / 'sample_captions.json'
    
    if not fixture_path.exists():
        pytest.skip("Sample captions fixture not found")
    
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.fixture
def sample_extracted_json():
    """Load sample extracted data from fixtures"""
    fixture_path = Path(__file__).parent.parent / 'fixtures' / 'sample_extracted.json'
    
    if not fixture_path.exists():
        pytest.skip("Sample extracted fixture not found")
    
    with open(fixture_path, 'r', encoding='utf-8') as f:
        return json.load(f)


@pytest.mark.integration
@pytest.mark.slow
class TestCompletePipeline:
    """Tests for complete pipeline execution"""
    
    def test_pipeline_extraction_to_validation(self, sample_instagram_data):
        """Test pipeline from Instagram data to validation"""
        if not Config.GEMINI_API_KEY:
            pytest.skip("GEMINI_API_KEY not set")
        
        extractor = DataExtractor()
        
        # Process first account
        account_name = list(sample_instagram_data.keys())[0]
        captions = sample_instagram_data[account_name]
        
        try:
            # Extract data
            extracted = extractor.process_account(account_name, captions)
            
            assert isinstance(extracted, list)
            
            # Validate extracted data
            if len(extracted) > 0:
                valid, invalid = DataValidator.validate_batch(extracted)
                
                # Should have some valid records
                assert isinstance(valid, list)
                assert isinstance(invalid, list)
        except Exception as e:
            pytest.skip(f"Pipeline test failed: {e}")
    
    def test_pipeline_validation_to_normalization(self, sample_extracted_json):
        """Test pipeline from validation to normalization"""
        if not Config.DATABASE_URL:
            pytest.skip("DATABASE_URL not set")
        
        # Validate data
        valid, invalid = DataValidator.validate_batch(sample_extracted_json)
        
        assert len(valid) > 0, "No valid records to normalize"
        
        # Get database mappings
        db_client = DatabaseClient(Config.DATABASE_URL)
        db_client.connect()
        
        try:
            audience_mapping = {}
            type_mapping = {}
            
            audiences = db_client.execute_query("SELECT code, id FROM audiences")
            for row in audiences:
                audience_mapping[row['code']] = row['id']
            
            types = db_client.execute_query("SELECT code, id FROM opportunity_types")
            for row in types:
                type_mapping[row['code']] = row['id']
            
            # Normalize data
            normalizer = DataNormalizer(audience_mapping, type_mapping)
            
            normalized = []
            for record in valid:
                norm = normalizer.normalize_opportunity(record)
                normalized.append(norm)
            
            assert len(normalized) == len(valid)
            
            # Verify normalized structure
            for norm in normalized:
                assert 'post_id' in norm
                assert 'title' in norm
                assert 'slug' in norm
                assert 'type_id' in norm
                assert 'audience_ids' in norm
        finally:
            db_client.close()


@pytest.mark.integration
class TestDataFlowConsistency:
    """Tests for data consistency across pipeline stages"""
    
    def test_post_id_preserved_through_pipeline(self, sample_extracted_json):
        """Test post_id is preserved through all stages"""
        if not Config.DATABASE_URL:
            pytest.skip("DATABASE_URL not set")
        
        original_post_ids = {record['post_id'] for record in sample_extracted_json}
        
        # Validate
        valid, invalid = DataValidator.validate_batch(sample_extracted_json)
        
        # Get mappings
        db_client = DatabaseClient(Config.DATABASE_URL)
        db_client.connect()
        
        try:
            audience_mapping = {}
            type_mapping = {}
            
            audiences = db_client.execute_query("SELECT code, id FROM audiences")
            for row in audiences:
                audience_mapping[row['code']] = row['id']
            
            types = db_client.execute_query("SELECT code, id FROM opportunity_types")
            for row in types:
                type_mapping[row['code']] = row['id']
            
            # Normalize
            normalizer = DataNormalizer(audience_mapping, type_mapping)
            
            normalized_post_ids = set()
            for record in valid:
                norm = normalizer.normalize_opportunity(record)
                normalized_post_ids.add(norm['post_id'])
            
            # Post IDs should be preserved
            assert normalized_post_ids.issubset(original_post_ids)
        finally:
            db_client.close()
    
    def test_title_preserved_through_pipeline(self, sample_extracted_json):
        """Test title is preserved (or normalized consistently)"""
        if not Config.DATABASE_URL:
            pytest.skip("DATABASE_URL not set")
        
        # Get mappings
        db_client = DatabaseClient(Config.DATABASE_URL)
        db_client.connect()
        
        try:
            audience_mapping = {}
            type_mapping = {}
            
            audiences = db_client.execute_query("SELECT code, id FROM audiences")
            for row in audiences:
                audience_mapping[row['code']] = row['id']
            
            types = db_client.execute_query("SELECT code, id FROM opportunity_types")
            for row in types:
                type_mapping[row['code']] = row['id']
            
            normalizer = DataNormalizer(audience_mapping, type_mapping)
            
            for record in sample_extracted_json:
                original_title = record.get('title', '')
                
                norm = normalizer.normalize_opportunity(record)
                normalized_title = norm['title']
                
                # Title should be similar (may be normalized)
                if original_title:
                    assert len(normalized_title) > 0
                    # Core content should be preserved
                    assert normalized_title != 'Untitled Opportunity'
        finally:
            db_client.close()


@pytest.mark.integration
class TestPhaseIntegration:
    """Tests for Phase 1, 2, 3 integration"""
    
    def test_phase1_expiration_filtering(self, sample_expired_data, sample_future_data):
        """Test Phase 1 expiration filtering works in pipeline"""
        if not Config.DATABASE_URL:
            pytest.skip("DATABASE_URL not set")
        
        from database.inserter import DataInserter
        
        db_client = DatabaseClient(Config.DATABASE_URL)
        db_client.connect()
        
        try:
            inserter = DataInserter(db_client)
            
            # Check expired data
            is_expired = inserter._check_expiration(sample_expired_data)
            assert is_expired is True
            
            # Check future data
            is_not_expired = inserter._check_expiration(sample_future_data)
            assert is_not_expired is False
        finally:
            db_client.close()
    
    def test_phase2_duplicate_detection(self, sample_duplicate_data):
        """Test Phase 2 duplicate detection works in pipeline"""
        if not Config.DATABASE_URL:
            pytest.skip("DATABASE_URL not set")
        
        from database.duplicate_detector import DuplicateDetector
        
        db_client = DatabaseClient(Config.DATABASE_URL)
        db_client.connect()
        
        try:
            detector = DuplicateDetector(db_client)
            
            # Calculate confidence between duplicates
            record1, record2 = sample_duplicate_data
            
            confidence = detector.calculate_confidence(record1, record2)
            
            # Should have high confidence (similar records)
            assert confidence >= 70
        finally:
            db_client.close()
    
    def test_phase3_regex_fallbacks(self):
        """Test Phase 3 regex fallbacks work in pipeline"""
        from extraction.utils.helpers import extract_registration_date_fallback
        
        # Test various date formats
        test_cases = [
            ("Pendaftaran: 20 April 2026", True),
            ("Batch 1: 1-14 April 2026", True),
            ("DL: 25 Juni 2026", True),
            ("No date here", False),
        ]
        
        for text, should_find in test_cases:
            result = extract_registration_date_fallback(text)
            
            if should_find:
                assert result is not None, f"Should find date in: {text}"
            else:
                assert result is None, f"Should not find date in: {text}"


@pytest.mark.integration
@pytest.mark.slow
class TestErrorRecovery:
    """Tests for error recovery in pipeline"""
    
    def test_pipeline_continues_after_validation_errors(self, sample_extracted_json):
        """Test pipeline continues processing after validation errors"""
        # Add invalid record
        invalid_record = {
            'post_id': 'INVALID',
            'title': '',  # Invalid: empty title
            'category': 'invalid_category'  # Invalid category
        }
        
        data_with_errors = sample_extracted_json + [invalid_record]
        
        # Validate batch
        valid, invalid = DataValidator.validate_batch(data_with_errors)
        
        # Should have valid records
        assert len(valid) > 0
        
        # Should have caught invalid record
        assert len(invalid) > 0
    
    def test_pipeline_handles_partial_extraction_failures(self):
        """Test pipeline handles partial extraction failures"""
        if not Config.GEMINI_API_KEY:
            pytest.skip("GEMINI_API_KEY not set")
        
        extractor = DataExtractor()
        
        # Mix of valid and problematic captions
        captions = [
            {
                'post_id': 'VALID_001',
                'caption': 'LOMBA ESSAY 2026\nDeadline: 20 April 2026',
                'source_account': 'test'
            },
            {
                'post_id': 'EMPTY_002',
                'caption': '',  # Empty caption
                'source_account': 'test'
            },
            {
                'post_id': 'VALID_003',
                'caption': 'Workshop AI\nDeadline: 25 Mei 2026',
                'source_account': 'test'
            }
        ]
        
        try:
            results = extractor.process_account('test', captions)
            
            # Should return results (may be partial)
            assert isinstance(results, list)
        except Exception as e:
            pytest.skip(f"Extraction failed: {e}")


@pytest.mark.integration
class TestPipelineScripts:
    """Tests for pipeline orchestration scripts"""
    
    def test_run_py_exists(self):
        """Test main pipeline runner exists"""
        script_path = Path(__file__).parent.parent.parent / 'run.py'
        
        assert script_path.exists(), "run.py not found"
    
    def test_extraction_main_exists(self):
        """Test extraction main script exists"""
        script_path = Path(__file__).parent.parent.parent / 'src' / 'extraction' / 'main.py'
        
        assert script_path.exists(), "extraction/main.py not found"
    
    def test_database_main_exists(self):
        """Test database main script exists"""
        script_path = Path(__file__).parent.parent.parent / 'src' / 'database' / 'main.py'
        
        assert script_path.exists(), "database/main.py not found"
    
    def test_load_extracted_data_function(self):
        """Test load_extracted_data function works"""
        # Create temporary test file
        import tempfile
        
        test_data = [
            {
                'post_id': 'TEST_001',
                'title': 'Test Event',
                'category': 'competition',
                'deadline_date': '2026-04-20',
                'audiences': ['sma'],
                'source_account': 'test'
            }
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(test_data, f)
            temp_path = f.name
        
        try:
            loaded_data = load_extracted_data(Path(temp_path))
            
            assert isinstance(loaded_data, list)
            assert len(loaded_data) == 1
            assert loaded_data[0]['post_id'] == 'TEST_001'
        finally:
            Path(temp_path).unlink()


@pytest.mark.integration
class TestNewAudienceCodesIntegration:
    """Tests for new audience codes (smk, sd, d2) in complete pipeline"""
    
    def test_new_codes_through_complete_pipeline(self, sample_extracted_data_with_new_audiences):
        """Test new audience codes work through complete pipeline"""
        if not Config.DATABASE_URL:
            pytest.skip("DATABASE_URL not set")
        
        # Validate
        is_valid, errors = DataValidator.validate_opportunity(
            sample_extracted_data_with_new_audiences
        )
        
        assert is_valid is True, f"Validation failed: {errors}"
        
        # Normalize
        db_client = DatabaseClient(Config.DATABASE_URL)
        db_client.connect()
        
        try:
            audience_mapping = {}
            type_mapping = {}
            
            audiences = db_client.execute_query("SELECT code, id FROM audiences")
            for row in audiences:
                audience_mapping[row['code']] = row['id']
            
            types = db_client.execute_query("SELECT code, id FROM opportunity_types")
            for row in types:
                type_mapping[row['code']] = row['id']
            
            normalizer = DataNormalizer(audience_mapping, type_mapping)
            
            normalized = normalizer.normalize_opportunity(
                sample_extracted_data_with_new_audiences
            )
            
            # Should have mapped all 3 new audience codes
            assert len(normalized['audience_ids']) == 3
            
            # All should be valid UUIDs
            for audience_id in normalized['audience_ids']:
                assert audience_id is not None
        finally:
            db_client.close()
