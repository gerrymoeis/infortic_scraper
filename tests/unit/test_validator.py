"""
Unit Tests for DataValidator

Tests data validation logic including:
- Required field validation
- Audience code validation (including new codes: smk, sd, d2)
- Category validation
- Field type validation
- Sanitization functions
"""
import pytest
from database.validator import DataValidator


@pytest.mark.unit
class TestValidateOpportunity:
    """Tests for validate_opportunity method"""
    
    def test_validate_with_complete_valid_data(self, sample_extracted_data):
        """Test validation passes with complete valid data"""
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_with_minimal_valid_data(self, sample_extracted_data_minimal):
        """Test validation passes with only required fields"""
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data_minimal)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_missing_post_id(self, sample_extracted_data):
        """Test validation fails when post_id is missing"""
        del sample_extracted_data['post_id']
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is False
        assert any('post_id' in error for error in errors)
    
    def test_validate_missing_title(self, sample_extracted_data):
        """Test validation fails when title is missing"""
        del sample_extracted_data['title']
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is False
        assert any('title' in error for error in errors)
    
    def test_validate_empty_title(self, sample_extracted_data):
        """Test validation fails when title is empty or whitespace"""
        sample_extracted_data['title'] = "   "
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is False
        assert any('title' in error for error in errors)
    
    def test_validate_missing_category(self, sample_extracted_data):
        """Test validation fails when category is missing"""
        del sample_extracted_data['category']
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is False
        assert any('category' in error for error in errors)
    
    def test_validate_invalid_category(self, sample_extracted_data):
        """Test validation fails with invalid category"""
        sample_extracted_data['category'] = 'invalid_category'
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is False
        assert any('Invalid category' in error for error in errors)
    
    def test_validate_all_valid_categories(self, sample_extracted_data):
        """Test all valid categories are accepted"""
        valid_categories = ['competition', 'scholarship', 'internship', 'job', 
                          'freelance', 'training', 'tryout', 'workshop', 
                          'festival', 'hackathon']
        
        for category in valid_categories:
            sample_extracted_data['category'] = category
            is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
            assert is_valid is True, f"Category '{category}' should be valid"


@pytest.mark.unit
class TestAudienceValidation:
    """Tests for audience code validation (CRITICAL - tests the fix)"""
    
    def test_validate_with_new_audience_codes(self, sample_extracted_data_with_new_audiences):
        """Test validation accepts new audience codes: smk, sd, d2"""
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data_with_new_audiences)
        
        assert is_valid is True, f"Should accept new audience codes, got errors: {errors}"
        assert len(errors) == 0
    
    def test_validate_smk_audience_code(self, sample_extracted_data):
        """Test 'smk' audience code is accepted"""
        sample_extracted_data['audiences'] = ['smk']
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_sd_audience_code(self, sample_extracted_data):
        """Test 'sd' audience code is accepted"""
        sample_extracted_data['audiences'] = ['sd']
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_d2_audience_code(self, sample_extracted_data):
        """Test 'd2' audience code is accepted"""
        sample_extracted_data['audiences'] = ['d2']
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_all_valid_audience_codes(self, sample_extracted_data):
        """Test all valid audience codes are accepted"""
        valid_audiences = ['sd', 'smp', 'sma', 'smk', 'd2', 'd3', 'd4', 's1', 'umum']
        
        for audience in valid_audiences:
            sample_extracted_data['audiences'] = [audience]
            is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
            assert is_valid is True, f"Audience '{audience}' should be valid, got errors: {errors}"
    
    def test_validate_multiple_audience_codes(self, sample_extracted_data):
        """Test multiple audience codes including new ones"""
        sample_extracted_data['audiences'] = ['sd', 'smp', 'sma', 'smk', 'd2']
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is True
        assert len(errors) == 0
    
    def test_validate_invalid_audience_code(self, sample_extracted_data):
        """Test validation fails with invalid audience code"""
        sample_extracted_data['audiences'] = ['invalid_audience']
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is False
        assert any('Invalid audience codes' in error for error in errors)
    
    def test_validate_mixed_valid_invalid_audiences(self, sample_extracted_data):
        """Test validation fails when some audience codes are invalid"""
        sample_extracted_data['audiences'] = ['sma', 'invalid', 'smk']
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is False
        assert any('invalid' in error for error in errors)
    
    def test_validate_audiences_not_list(self, sample_extracted_data):
        """Test validation fails when audiences is not a list"""
        sample_extracted_data['audiences'] = 'sma'  # String instead of list
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is False
        assert any('must be a list' in error for error in errors)
    
    def test_validate_empty_audiences_list(self, sample_extracted_data):
        """Test validation passes with empty audiences list"""
        sample_extracted_data['audiences'] = []
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is True
        assert len(errors) == 0


@pytest.mark.unit
class TestFieldTypeValidation:
    """Tests for field type validation"""
    
    def test_validate_registration_date_as_string(self, sample_extracted_data):
        """Test registration_date must be a string"""
        sample_extracted_data['registration_date'] = "2026-04-15"
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is True
    
    def test_validate_registration_date_wrong_type(self, sample_extracted_data):
        """Test validation fails when registration_date is not a string"""
        sample_extracted_data['registration_date'] = 20260415  # Integer
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is False
        assert any('registration_date must be a string' in error for error in errors)
    
    def test_validate_contact_as_string(self, sample_extracted_data):
        """Test contact must be a string"""
        sample_extracted_data['contact'] = "08123456789"
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is True
    
    def test_validate_contact_wrong_type(self, sample_extracted_data):
        """Test validation fails when contact is not a string"""
        sample_extracted_data['contact'] = 8123456789  # Integer
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is False
        assert any('contact must be a string' in error for error in errors)
    
    def test_validate_registration_url_as_string(self, sample_extracted_data):
        """Test registration_url must be a string"""
        sample_extracted_data['registration_url'] = "https://example.com"
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is True
    
    def test_validate_registration_url_wrong_type(self, sample_extracted_data):
        """Test validation fails when registration_url is not a string"""
        sample_extracted_data['registration_url'] = ['https://example.com']  # List
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is False
        assert any('registration_url must be a string' in error for error in errors)


@pytest.mark.unit
class TestOptionalFieldValidation:
    """Tests for optional field validation"""
    
    def test_validate_valid_event_type(self, sample_extracted_data):
        """Test valid event_type values are accepted"""
        for event_type in ['online', 'offline', 'hybrid']:
            sample_extracted_data['event_type'] = event_type
            is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
            assert is_valid is True, f"event_type '{event_type}' should be valid"
    
    def test_validate_invalid_event_type(self, sample_extracted_data):
        """Test invalid event_type is rejected"""
        sample_extracted_data['event_type'] = 'invalid'
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is False
        assert any('Invalid event_type' in error for error in errors)
    
    def test_validate_valid_fee_type(self, sample_extracted_data):
        """Test valid fee_type values are accepted"""
        for fee_type in ['gratis', 'berbayar']:
            sample_extracted_data['fee_type'] = fee_type
            is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
            assert is_valid is True, f"fee_type '{fee_type}' should be valid"
    
    def test_validate_invalid_fee_type(self, sample_extracted_data):
        """Test invalid fee_type is rejected"""
        sample_extracted_data['fee_type'] = 'invalid'
        
        is_valid, errors = DataValidator.validate_opportunity(sample_extracted_data)
        
        assert is_valid is False
        assert any('Invalid fee_type' in error for error in errors)


@pytest.mark.unit
class TestValidateBatch:
    """Tests for validate_batch method"""
    
    def test_validate_batch_all_valid(self, sample_extracted_data, sample_extracted_data_minimal):
        """Test batch validation with all valid records"""
        data_list = [sample_extracted_data, sample_extracted_data_minimal]
        
        valid, invalid = DataValidator.validate_batch(data_list)
        
        assert len(valid) == 2
        assert len(invalid) == 0
    
    def test_validate_batch_all_invalid(self, sample_extracted_data):
        """Test batch validation with all invalid records"""
        invalid_data1 = sample_extracted_data.copy()
        del invalid_data1['title']
        
        invalid_data2 = sample_extracted_data.copy()
        invalid_data2['category'] = 'invalid'
        
        data_list = [invalid_data1, invalid_data2]
        
        valid, invalid = DataValidator.validate_batch(data_list)
        
        assert len(valid) == 0
        assert len(invalid) == 2
        assert all('errors' in item for item in invalid)
    
    def test_validate_batch_mixed(self, sample_extracted_data, sample_extracted_data_minimal):
        """Test batch validation with mixed valid/invalid records"""
        invalid_data = sample_extracted_data.copy()
        del invalid_data['post_id']
        
        data_list = [sample_extracted_data_minimal, invalid_data]
        
        valid, invalid = DataValidator.validate_batch(data_list)
        
        assert len(valid) == 1
        assert len(invalid) == 1
        assert valid[0]['post_id'] == 'TEST_POST_MIN'


@pytest.mark.unit
class TestSanitization:
    """Tests for sanitization functions"""
    
    def test_sanitize_title_removes_extra_whitespace(self):
        """Test title sanitization removes excessive whitespace"""
        title = "LOMBA    ESSAY   NASIONAL    2026"
        
        sanitized = DataValidator.sanitize_title(title)
        
        assert sanitized == "LOMBA ESSAY NASIONAL 2026"
    
    def test_sanitize_title_removes_leading_trailing_whitespace(self):
        """Test title sanitization removes leading/trailing whitespace"""
        title = "   LOMBA ESSAY NASIONAL 2026   "
        
        sanitized = DataValidator.sanitize_title(title)
        
        assert sanitized == "LOMBA ESSAY NASIONAL 2026"
    
    def test_sanitize_title_truncates_long_title(self):
        """Test title sanitization truncates very long titles"""
        title = "A" * 250  # 250 characters
        
        sanitized = DataValidator.sanitize_title(title)
        
        assert len(sanitized) <= 203  # 200 + "..."
        assert sanitized.endswith("...")
    
    def test_sanitize_title_empty_string(self):
        """Test title sanitization handles empty string"""
        sanitized = DataValidator.sanitize_title("")
        
        assert sanitized == ""
    
    def test_sanitize_title_none(self):
        """Test title sanitization handles None"""
        sanitized = DataValidator.sanitize_title(None)
        
        assert sanitized == ""
    
    def test_sanitize_description_removes_extra_whitespace(self):
        """Test description sanitization removes excessive whitespace"""
        description = "Lomba    essay   dengan    tema   teknologi"
        
        sanitized = DataValidator.sanitize_description(description)
        
        assert sanitized == "Lomba essay dengan tema teknologi"
    
    def test_sanitize_description_truncates_long_description(self):
        """Test description sanitization truncates very long descriptions"""
        description = "A" * 600  # 600 characters
        
        sanitized = DataValidator.sanitize_description(description)
        
        assert len(sanitized) <= 503  # 500 + "..."
        assert sanitized.endswith("...")
    
    def test_sanitize_description_empty_string(self):
        """Test description sanitization returns None for empty string"""
        sanitized = DataValidator.sanitize_description("")
        
        assert sanitized is None
    
    def test_sanitize_description_whitespace_only(self):
        """Test description sanitization returns None for whitespace-only string"""
        sanitized = DataValidator.sanitize_description("   ")
        
        assert sanitized is None
    
    def test_sanitize_description_none(self):
        """Test description sanitization handles None"""
        sanitized = DataValidator.sanitize_description(None)
        
        assert sanitized is None
