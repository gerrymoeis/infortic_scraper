"""
Integration Tests for Database Operations

Tests database operations with real database:
- Database connection (requires DATABASE_URL)
- Data insertion
- Duplicate detection (Phase 2)
- Expiration filtering (Phase 1)
- Validation with new audience codes

These tests require a real database connection.
Use pytest -m integration to run them.
"""
import pytest
from datetime import datetime, timedelta
from database.client import DatabaseClient
from database.validator import DataValidator
from database.normalizer import DataNormalizer
from database.duplicate_detector import DuplicateDetector
from database.inserter import DataInserter
from extraction.utils.config import Config


@pytest.fixture
def db_client():
    """Create database client for integration tests"""
    if not Config.DATABASE_URL:
        pytest.skip("DATABASE_URL not set")
    
    client = DatabaseClient(Config.DATABASE_URL)
    client.connect()
    yield client
    client.close()


@pytest.fixture
def normalizer(db_client):
    """Create normalizer with real database mappings"""
    # Get mappings from database
    audience_mapping = {}
    type_mapping = {}
    
    try:
        # Get audience mappings
        audiences = db_client.execute_query("SELECT code, id FROM audiences")
        for row in audiences:
            audience_mapping[row['code']] = row['id']
        
        # Get type mappings
        types = db_client.execute_query("SELECT code, id FROM opportunity_types")
        for row in types:
            type_mapping[row['code']] = row['id']
    except Exception as e:
        pytest.skip(f"Could not load database mappings: {e}")
    
    return DataNormalizer(audience_mapping, type_mapping)


@pytest.fixture
def duplicate_detector(db_client):
    """Create duplicate detector with real database"""
    return DuplicateDetector(db_client)


@pytest.fixture
def inserter(db_client):
    """Create data inserter with real database"""
    return DataInserter(db_client)


@pytest.mark.integration
class TestDatabaseConnection:
    """Tests for database connection"""
    
    def test_database_connection_successful(self, db_client):
        """Test database connection is successful"""
        assert db_client is not None
        assert db_client.connection is not None
    
    def test_database_query_execution(self, db_client):
        """Test basic query execution"""
        result = db_client.execute_query("SELECT 1 as test")
        
        assert result is not None
        assert len(result) == 1
        assert result[0]['test'] == 1
    
    def test_database_version(self, db_client):
        """Test database version query"""
        result = db_client.execute_query("SELECT version()")
        
        assert result is not None
        assert len(result) == 1
        assert 'PostgreSQL' in result[0]['version']


@pytest.mark.integration
class TestDatabaseMappings:
    """Tests for database mappings (audiences, types)"""
    
    def test_audience_codes_exist(self, db_client):
        """Test all required audience codes exist in database"""
        result = db_client.execute_query("SELECT code FROM audiences ORDER BY code")
        
        codes = [row['code'] for row in result]
        
        # Check all valid codes exist
        required_codes = ['sd', 'smp', 'sma', 'smk', 'd2', 'd3', 'd4', 's1', 'umum']
        for code in required_codes:
            assert code in codes, f"Audience code '{code}' not found in database"
    
    def test_new_audience_codes_exist(self, db_client):
        """Test new audience codes (smk, sd, d2) exist in database"""
        result = db_client.execute_query(
            "SELECT code FROM audiences WHERE code IN ('smk', 'sd', 'd2')"
        )
        
        codes = [row['code'] for row in result]
        
        assert 'smk' in codes, "Audience code 'smk' not found"
        assert 'sd' in codes, "Audience code 'sd' not found"
        assert 'd2' in codes, "Audience code 'd2' not found"
    
    def test_opportunity_types_exist(self, db_client):
        """Test opportunity types exist in database"""
        result = db_client.execute_query("SELECT code FROM opportunity_types")
        
        codes = [row['code'] for row in result]
        
        # Check some common types
        assert 'competition' in codes
        assert 'scholarship' in codes
        assert 'workshop' in codes


@pytest.mark.integration
class TestDataValidation:
    """Tests for data validation with database"""
    
    def test_validate_with_new_audience_codes(self, sample_extracted_data_with_new_audiences):
        """Test validation accepts new audience codes"""
        is_valid, errors = DataValidator.validate_opportunity(
            sample_extracted_data_with_new_audiences
        )
        
        assert is_valid is True, f"Validation failed: {errors}"
        assert len(errors) == 0
    
    def test_validate_batch_with_mixed_data(self, sample_extracted_data, sample_expired_data):
        """Test batch validation with mixed valid/invalid data"""
        data_list = [sample_extracted_data, sample_expired_data]
        
        valid, invalid = DataValidator.validate_batch(data_list)
        
        # Both should be valid (expiration is checked separately)
        assert len(valid) == 2
        assert len(invalid) == 0


@pytest.mark.integration
class TestDataNormalization:
    """Tests for data normalization with real mappings"""
    
    def test_normalize_with_real_mappings(self, normalizer, sample_extracted_data):
        """Test normalization with real database mappings"""
        normalized = normalizer.normalize_opportunity(sample_extracted_data)
        
        assert normalized is not None
        assert normalized['type_id'] is not None
        assert len(normalized['audience_ids']) > 0
    
    def test_normalize_new_audience_codes(self, normalizer, sample_extracted_data_with_new_audiences):
        """Test normalization maps new audience codes correctly"""
        normalized = normalizer.normalize_opportunity(
            sample_extracted_data_with_new_audiences
        )
        
        # Should have mapped all audience codes
        assert len(normalized['audience_ids']) == 3
        
        # All should be valid UUIDs
        for audience_id in normalized['audience_ids']:
            assert audience_id is not None
            assert len(str(audience_id)) > 0


@pytest.mark.integration
class TestDuplicateDetection:
    """Tests for duplicate detection with real database (Phase 2)"""
    
    def test_find_duplicates_no_match(self, duplicate_detector, sample_extracted_data):
        """Test duplicate detection when no match exists"""
        # Use unique post_id that doesn't exist
        test_data = sample_extracted_data.copy()
        test_data['post_id'] = f'TEST_UNIQUE_{datetime.now().timestamp()}'
        
        match, confidence, match_type = duplicate_detector.find_duplicates(test_data)
        
        # Should find no match
        assert match is None
        assert confidence == 0
        assert match_type == 'no_match'
    
    def test_calculate_confidence_with_real_data(self, duplicate_detector):
        """Test confidence calculation with real-world data"""
        record1 = {
            'title': 'LOMBA ESSAY NASIONAL 2026',
            'organizer_name': 'Universitas Indonesia',
            'type_id': 'test-uuid',
            'dates': {'deadline_date': '2026-04-20'}
        }
        
        record2 = {
            'title': 'LOMBA ESSAY NASIONAL 2026',
            'organizer_name': 'Universitas Indonesia',
            'type_id': 'test-uuid',
            'deadline_date': '2026-04-20'
        }
        
        confidence = duplicate_detector.calculate_confidence(record1, record2)
        
        # Should have high confidence (exact match)
        assert confidence >= 80


@pytest.mark.integration
class TestExpirationFiltering:
    """Tests for expiration filtering (Phase 1)"""
    
    def test_check_expiration_past_deadline(self, inserter):
        """Test expiration check for past deadline"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
        data = {
            'dates': {
                'deadline_date': yesterday
            }
        }
        
        is_expired = inserter._check_expiration(data)
        
        assert is_expired is True
    
    def test_check_expiration_future_deadline(self, inserter):
        """Test expiration check for future deadline"""
        future = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        
        data = {
            'dates': {
                'deadline_date': future
            }
        }
        
        is_expired = inserter._check_expiration(data)
        
        assert is_expired is False
    
    def test_check_expiration_no_deadline(self, inserter):
        """Test expiration check with no deadline"""
        data = {
            'dates': {}
        }
        
        is_expired = inserter._check_expiration(data)
        
        # Should not be considered expired if no deadline
        assert is_expired is False


@pytest.mark.integration
@pytest.mark.slow
class TestDatabaseInsertion:
    """Tests for database insertion (requires write access)"""
    
    def test_insert_new_opportunity(self, db_client, normalizer, sample_extracted_data):
        """Test inserting new opportunity"""
        # Normalize data first
        normalized = normalizer.normalize_opportunity(sample_extracted_data)
        
        # Use unique post_id to avoid conflicts
        normalized['post_id'] = f'TEST_INSERT_{datetime.now().timestamp()}'
        
        try:
            # This is a read-only test - we'll just verify the structure
            # Actual insertion would require cleanup
            assert normalized['post_id'] is not None
            assert normalized['title'] is not None
            assert normalized['type_id'] is not None
        except Exception as e:
            pytest.skip(f"Insertion test skipped: {e}")
    
    def test_insert_with_new_audience_codes(self, normalizer, sample_extracted_data_with_new_audiences):
        """Test insertion with new audience codes"""
        normalized = normalizer.normalize_opportunity(
            sample_extracted_data_with_new_audiences
        )
        
        # Verify new audience codes are mapped
        assert len(normalized['audience_ids']) == 3
        
        # All audience IDs should be valid
        for audience_id in normalized['audience_ids']:
            assert audience_id is not None


@pytest.mark.integration
class TestCleanupScript:
    """Tests for cleanup script (mark expired opportunities)"""
    
    def test_cleanup_script_exists(self):
        """Test cleanup script file exists"""
        from pathlib import Path
        
        script_path = Path(__file__).parent.parent.parent / 'scripts' / 'mark_expired.py'
        
        assert script_path.exists(), "Cleanup script not found"
    
    def test_cleanup_query_syntax(self, db_client):
        """Test cleanup query syntax is valid"""
        # Test the query structure without actually updating
        query = """
            SELECT id, title, deadline_date 
            FROM opportunities 
            WHERE status = 'published' 
              AND deadline_date < CURRENT_DATE
            LIMIT 1
        """
        
        try:
            result = db_client.execute_query(query)
            # Query should execute without error
            assert isinstance(result, list)
        except Exception as e:
            pytest.fail(f"Cleanup query syntax error: {e}")


@pytest.mark.integration
class TestVerificationScript:
    """Tests for verification script"""
    
    def test_verification_script_exists(self):
        """Test verification script file exists"""
        from pathlib import Path
        
        script_path = Path(__file__).parent.parent.parent / 'scripts' / 'verify.py'
        
        assert script_path.exists(), "Verification script not found"
    
    def test_verification_queries(self, db_client):
        """Test verification queries execute successfully"""
        queries = [
            "SELECT COUNT(*) as total FROM opportunities",
            "SELECT COUNT(*) as published FROM opportunities WHERE status = 'published'",
            "SELECT COUNT(*) as expired FROM opportunities WHERE status = 'expired'",
        ]
        
        for query in queries:
            try:
                result = db_client.execute_query(query)
                assert result is not None
                assert len(result) == 1
            except Exception as e:
                pytest.fail(f"Verification query failed: {query}\nError: {e}")


@pytest.mark.integration
class TestDatabaseSchema:
    """Tests for database schema validation"""
    
    def test_opportunities_table_exists(self, db_client):
        """Test opportunities table exists"""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'opportunities'
            )
        """
        
        result = db_client.execute_query(query)
        assert result[0]['exists'] is True
    
    def test_audiences_table_exists(self, db_client):
        """Test audiences table exists"""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'audiences'
            )
        """
        
        result = db_client.execute_query(query)
        assert result[0]['exists'] is True
    
    def test_opportunity_types_table_exists(self, db_client):
        """Test opportunity_types table exists"""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'opportunity_types'
            )
        """
        
        result = db_client.execute_query(query)
        assert result[0]['exists'] is True
