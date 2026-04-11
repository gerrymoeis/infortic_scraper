"""
Unit Tests for DataNormalizer

Tests data normalization logic including:
- Title and slug generation
- Audience and type mapping
- Date parsing
- Field sanitization
- Tag generation
"""
import pytest
from database.normalizer import DataNormalizer


@pytest.fixture
def normalizer(audience_mapping, type_mapping):
    """Create a DataNormalizer instance with test mappings"""
    return DataNormalizer(audience_mapping, type_mapping)


@pytest.mark.unit
class TestNormalizeOpportunity:
    """Tests for normalize_opportunity method"""
    
    def test_normalize_with_complete_data(self, normalizer, sample_extracted_data):
        """Test normalization with complete data"""
        normalized = normalizer.normalize_opportunity(sample_extracted_data)
        
        assert normalized['post_id'] == sample_extracted_data['post_id']
        assert normalized['title'] == sample_extracted_data['title']
        assert normalized['slug'] is not None
        assert normalized['description'] == sample_extracted_data['description']
        assert normalized['contact'] == sample_extracted_data['contact']
        assert normalized['registration_url'] == sample_extracted_data['registration_url']
    
    def test_normalize_with_minimal_data(self, normalizer, sample_extracted_data_minimal):
        """Test normalization with only required fields"""
        normalized = normalizer.normalize_opportunity(sample_extracted_data_minimal)
        
        assert normalized['post_id'] == sample_extracted_data_minimal['post_id']
        assert normalized['title'] == sample_extracted_data_minimal['title']
        assert normalized['slug'] is not None
        assert normalized['description'] is None
        assert normalized['contact'] is None
    
    def test_normalize_generates_all_required_fields(self, normalizer, sample_extracted_data):
        """Test that normalization generates all required database fields"""
        normalized = normalizer.normalize_opportunity(sample_extracted_data)
        
        required_fields = [
            'post_id', 'title', 'slug', 'type_id', 'audience_ids',
            'registration_url', 'contact', 'registration_date', 'dates',
            'view_count', 'is_featured', 'tags'
        ]
        
        for field in required_fields:
            assert field in normalized, f"Missing required field: {field}"
    
    def test_normalize_sets_default_values(self, normalizer, sample_extracted_data):
        """Test that normalization sets default values for frontend fields"""
        normalized = normalizer.normalize_opportunity(sample_extracted_data)
        
        assert normalized['view_count'] == 0
        assert normalized['is_featured'] is False


@pytest.mark.unit
class TestTitleNormalization:
    """Tests for title normalization"""
    
    def test_normalize_title_removes_extra_whitespace(self, normalizer):
        """Test title normalization removes excessive whitespace"""
        data = {'title': 'LOMBA    ESSAY   NASIONAL    2026'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['title'] == 'LOMBA ESSAY NASIONAL 2026'
    
    def test_normalize_title_truncates_long_title(self, normalizer):
        """Test title normalization truncates very long titles"""
        data = {'title': 'A' * 250}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert len(normalized['title']) <= 203  # 200 + "..."
        assert normalized['title'].endswith('...')
    
    def test_normalize_title_handles_empty(self, normalizer):
        """Test title normalization handles empty title"""
        data = {'title': ''}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['title'] == 'Untitled Opportunity'
    
    def test_normalize_title_handles_none(self, normalizer):
        """Test title normalization handles None"""
        data = {'title': None}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['title'] == 'Untitled Opportunity'


@pytest.mark.unit
class TestSlugGeneration:
    """Tests for slug generation"""
    
    def test_generate_slug_from_title(self, normalizer):
        """Test slug generation from title"""
        data = {'title': 'LOMBA ESSAY NASIONAL 2026'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['slug'] == 'lomba-essay-nasional-2026'
    
    def test_generate_slug_removes_special_characters(self, normalizer):
        """Test slug removes special characters"""
        data = {'title': 'LOMBA @#$% ESSAY!!! 2026'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['slug'] == 'lomba-essay-2026'
    
    def test_generate_slug_handles_consecutive_spaces(self, normalizer):
        """Test slug handles consecutive spaces"""
        data = {'title': 'LOMBA    ESSAY    2026'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['slug'] == 'lomba-essay-2026'
    
    def test_generate_slug_truncates_long_slug(self, normalizer):
        """Test slug truncation for very long titles"""
        data = {'title': 'A' * 150}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert len(normalized['slug']) <= 100
    
    def test_generate_slug_handles_empty_title(self, normalizer):
        """Test slug generation with empty title"""
        data = {'title': ''}
        
        normalized = normalizer.normalize_opportunity(data)
        
        # Should generate a fallback slug with timestamp
        assert normalized['slug'].startswith('opportunity-')
    
    def test_generate_slug_lowercase(self, normalizer):
        """Test slug is always lowercase"""
        data = {'title': 'LOMBA ESSAY NASIONAL'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['slug'].islower()


@pytest.mark.unit
class TestAudienceMapping:
    """Tests for audience code to UUID mapping"""
    
    def test_normalize_audiences_maps_codes_to_uuids(self, normalizer, audience_mapping):
        """Test audience codes are mapped to UUIDs"""
        data = {'audiences': ['sma', 'smk']}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert len(normalized['audience_ids']) == 2
        assert audience_mapping['sma'] in normalized['audience_ids']
        assert audience_mapping['smk'] in normalized['audience_ids']
    
    def test_normalize_audiences_with_new_codes(self, normalizer, audience_mapping):
        """Test new audience codes (smk, sd, d2) are mapped correctly"""
        data = {'audiences': ['sd', 'smk', 'd2']}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert len(normalized['audience_ids']) == 3
        assert audience_mapping['sd'] in normalized['audience_ids']
        assert audience_mapping['smk'] in normalized['audience_ids']
        assert audience_mapping['d2'] in normalized['audience_ids']
    
    def test_normalize_audiences_empty_list(self, normalizer):
        """Test normalization with empty audiences list"""
        data = {'audiences': []}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['audience_ids'] == []
    
    def test_normalize_audiences_missing(self, normalizer):
        """Test normalization with missing audiences field"""
        data = {}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['audience_ids'] == []
    
    def test_normalize_audiences_unknown_code(self, normalizer):
        """Test normalization skips unknown audience codes"""
        data = {'audiences': ['sma', 'unknown_code', 'smk']}
        
        normalized = normalizer.normalize_opportunity(data)
        
        # Should only include known codes
        assert len(normalized['audience_ids']) == 2


@pytest.mark.unit
class TestTypeMapping:
    """Tests for opportunity type mapping"""
    
    def test_normalize_type_maps_code_to_uuid(self, normalizer, type_mapping):
        """Test opportunity type code is mapped to UUID"""
        data = {'category': 'competition'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['type_id'] == type_mapping['competition']
    
    def test_normalize_type_all_valid_types(self, normalizer, type_mapping):
        """Test all valid opportunity types are mapped correctly"""
        for type_code in type_mapping.keys():
            data = {'category': type_code}
            normalized = normalizer.normalize_opportunity(data)
            assert normalized['type_id'] == type_mapping[type_code]
    
    def test_normalize_type_missing(self, normalizer):
        """Test normalization with missing category"""
        data = {}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['type_id'] is None
    
    def test_normalize_type_unknown_code(self, normalizer):
        """Test normalization with unknown type code"""
        data = {'category': 'unknown_type'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['type_id'] is None


@pytest.mark.unit
class TestDescriptionNormalization:
    """Tests for description normalization"""
    
    def test_normalize_description_removes_whitespace(self, normalizer):
        """Test description normalization removes excessive whitespace"""
        data = {'description': 'Lomba    essay   dengan    tema   teknologi'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['description'] == 'Lomba essay dengan tema teknologi'
    
    def test_normalize_description_truncates_long_text(self, normalizer):
        """Test description truncation"""
        data = {'description': 'A' * 600}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert len(normalized['description']) <= 503  # 500 + "..."
        assert normalized['description'].endswith('...')
    
    def test_normalize_description_empty_returns_none(self, normalizer):
        """Test empty description returns None"""
        data = {'description': ''}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['description'] is None
    
    def test_normalize_description_whitespace_only_returns_none(self, normalizer):
        """Test whitespace-only description returns None"""
        data = {'description': '   '}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['description'] is None
    
    def test_normalize_description_none(self, normalizer):
        """Test None description"""
        data = {'description': None}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['description'] is None


@pytest.mark.unit
class TestOrganizerNormalization:
    """Tests for organizer name normalization"""
    
    def test_normalize_organizer_removes_whitespace(self, normalizer):
        """Test organizer name normalization removes excessive whitespace"""
        data = {'organizer': 'Universitas    Indonesia'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['organizer_name'] == 'Universitas Indonesia'
    
    def test_normalize_organizer_truncates_long_name(self, normalizer):
        """Test organizer name truncation"""
        data = {'organizer': 'A' * 250}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert len(normalized['organizer_name']) <= 203  # 200 + "..."
    
    def test_normalize_organizer_empty_returns_none(self, normalizer):
        """Test empty organizer returns None"""
        data = {'organizer': ''}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['organizer_name'] is None
    
    def test_normalize_organizer_none(self, normalizer):
        """Test None organizer"""
        data = {'organizer': None}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['organizer_name'] is None


@pytest.mark.unit
class TestDateParsing:
    """Tests for registration date parsing"""
    
    def test_parse_single_date(self, normalizer):
        """Test parsing single date"""
        data = {'registration_date': '20 April 2026'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['dates']['start_date'] == '2026-04-20'
        assert normalized['dates']['end_date'] == '2026-04-20'
        assert normalized['dates']['deadline_date'] == '2026-04-20'
    
    def test_parse_date_range(self, normalizer):
        """Test parsing date range"""
        data = {'registration_date': '15 April 2026 - 20 April 2026'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['dates']['start_date'] == '2026-04-15'
        assert normalized['dates']['end_date'] == '2026-04-20'
        assert normalized['dates']['deadline_date'] == '2026-04-20'
    
    def test_parse_date_missing(self, normalizer):
        """Test parsing with missing date"""
        data = {}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert normalized['dates']['start_date'] is None
        assert normalized['dates']['end_date'] is None
        assert normalized['dates']['deadline_date'] is None
    
    def test_parse_date_invalid_format(self, normalizer):
        """Test parsing with invalid date format"""
        data = {'registration_date': 'invalid date'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        # Should return None for all dates when parsing fails
        assert normalized['dates']['start_date'] is None
        assert normalized['dates']['end_date'] is None
        assert normalized['dates']['deadline_date'] is None


@pytest.mark.unit
class TestTagGeneration:
    """Tests for tag generation"""
    
    def test_generate_tags_includes_category(self, normalizer):
        """Test tags include category"""
        data = {'category': 'competition'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert 'competition' in normalized['tags']
    
    def test_generate_tags_includes_audiences(self, normalizer):
        """Test tags include audience codes"""
        data = {'audiences': ['sma', 'smk']}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert 'sma' in normalized['tags']
        assert 'smk' in normalized['tags']
    
    def test_generate_tags_includes_event_type(self, normalizer):
        """Test tags include event type"""
        data = {'event_type': 'online'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert 'online' in normalized['tags']
    
    def test_generate_tags_includes_fee_type(self, normalizer):
        """Test tags include fee type"""
        data = {'fee_type': 'gratis'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert 'gratis' in normalized['tags']
    
    def test_generate_tags_includes_organizer(self, normalizer):
        """Test tags include organizer"""
        data = {'organizer': 'Universitas Indonesia'}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert 'Universitas Indonesia' in normalized['tags']
    
    def test_generate_tags_no_duplicates(self, normalizer):
        """Test tags have no duplicates"""
        data = {
            'category': 'competition',
            'audiences': ['sma'],
            'organizer': 'competition'  # Duplicate of category
        }
        
        normalized = normalizer.normalize_opportunity(data)
        
        # Should only have 'competition' once
        assert normalized['tags'].count('competition') == 1
    
    def test_generate_tags_empty_data(self, normalizer):
        """Test tag generation with empty data"""
        data = {}
        
        normalized = normalizer.normalize_opportunity(data)
        
        assert isinstance(normalized['tags'], list)
