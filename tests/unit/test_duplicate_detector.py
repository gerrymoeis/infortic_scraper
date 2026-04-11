"""
Unit Tests for DuplicateDetector (Phase 2)

Tests duplicate detection logic including:
- Exact post_id matching
- Fuzzy title matching
- Confidence scoring
- Date overlap detection
"""
import pytest
from datetime import datetime, timedelta
from database.duplicate_detector import DuplicateDetector


@pytest.fixture
def duplicate_detector(mock_db_client):
    """Create a DuplicateDetector instance with mock database"""
    return DuplicateDetector(mock_db_client)


@pytest.mark.unit
class TestFindDuplicates:
    """Tests for find_duplicates method"""
    
    def test_find_exact_post_id_match(self, duplicate_detector, mock_db_client, sample_extracted_data):
        """Test exact duplicate detection by post_id (100% confidence)"""
        # Mock database to return existing record with same post_id
        existing_record = sample_extracted_data.copy()
        mock_db_client.execute_query.return_value = [existing_record]
        
        new_record = sample_extracted_data.copy()
        
        match, confidence, match_type = duplicate_detector.find_duplicates(new_record)
        
        assert match is not None
        assert confidence == 100
        assert match_type == 'exact_post_id'
    
    def test_find_no_match(self, duplicate_detector, mock_db_client, sample_extracted_data):
        """Test no duplicate found"""
        # Mock database to return no results
        mock_db_client.execute_query.return_value = []
        
        new_record = sample_extracted_data.copy()
        
        match, confidence, match_type = duplicate_detector.find_duplicates(new_record)
        
        assert match is None
        assert confidence == 0
        assert match_type == 'no_match'
    
    def test_find_fuzzy_match_high_confidence(self, duplicate_detector, mock_db_client, sample_duplicate_data):
        """Test fuzzy match with high confidence (>70%)"""
        # Mock database to return no exact post_id match, but return candidate
        def mock_query(query, params=None):
            if 'post_id' in query:
                return []  # No exact match
            else:
                return [sample_duplicate_data[1]]  # Return similar record
        
        mock_db_client.execute_query.side_effect = mock_query
        
        new_record = sample_duplicate_data[0]
        
        match, confidence, match_type = duplicate_detector.find_duplicates(new_record)
        
        assert match is not None
        assert confidence >= 70
        assert match_type == 'fuzzy_match'
    
    def test_find_fuzzy_match_low_confidence(self, duplicate_detector, mock_db_client, sample_extracted_data):
        """Test fuzzy match with low confidence (<70%) returns no match"""
        # Mock database to return a very different record
        different_record = {
            'title': 'Completely Different Event',
            'organizer_name': 'Different Organizer',
            'type_id': 'different-type',
            'deadline_date': '2026-12-31'
        }
        
        def mock_query(query, params=None):
            if 'post_id' in query:
                return []
            else:
                return [different_record]
        
        mock_db_client.execute_query.side_effect = mock_query
        
        new_record = sample_extracted_data.copy()
        
        match, confidence, match_type = duplicate_detector.find_duplicates(new_record)
        
        assert match is None
        assert confidence == 0
        assert match_type == 'no_match'


@pytest.mark.unit
class TestCalculateConfidence:
    """Tests for confidence scoring algorithm"""
    
    def test_calculate_confidence_identical_records(self, duplicate_detector):
        """Test confidence calculation for identical records (100%)"""
        record = {
            'title': 'KAHFI 2 FESTIVAL 2026',
            'organizer_name': 'KAHFI',
            'type_id': 'festival-uuid',
            'dates': {'deadline_date': '2026-04-25'}
        }
        
        score = duplicate_detector.calculate_confidence(record, record)
        
        # Exact title (40) + Same organizer (30) + Same dates (20) + Same category (10) = 100
        assert score == 100
    
    def test_calculate_confidence_exact_title_match(self, duplicate_detector):
        """Test exact title match gives 40 points"""
        record1 = {'title': 'LOMBA ESSAY NASIONAL 2026'}
        record2 = {'title': 'LOMBA ESSAY NASIONAL 2026'}
        
        score = duplicate_detector.calculate_confidence(record1, record2)
        
        assert score >= 40
    
    def test_calculate_confidence_fuzzy_title_match(self, duplicate_detector):
        """Test fuzzy title match (>85% similarity) gives 30 points"""
        record1 = {'title': 'KAHFI 2 FESTIVAL 2026'}
        record2 = {'title': 'KAHFI 2 Festival 2026'}  # Slightly different case
        
        score = duplicate_detector.calculate_confidence(record1, record2)
        
        # Should get fuzzy match points (30 or 40)
        assert score >= 30
    
    def test_calculate_confidence_same_organizer(self, duplicate_detector):
        """Test same organizer gives 30 points"""
        record1 = {
            'title': 'Event A',
            'organizer_name': 'Universitas Indonesia'
        }
        record2 = {
            'title': 'Event B',
            'organizer_name': 'Universitas Indonesia'
        }
        
        score = duplicate_detector.calculate_confidence(record1, record2)
        
        assert score >= 30
    
    def test_calculate_confidence_overlapping_dates(self, duplicate_detector):
        """Test overlapping dates give 20 points"""
        record1 = {
            'title': 'Event A',
            'dates': {'deadline_date': '2026-04-20'}
        }
        record2 = {
            'title': 'Event B',
            'deadline_date': '2026-04-20'
        }
        
        score = duplicate_detector.calculate_confidence(record1, record2)
        
        assert score >= 20
    
    def test_calculate_confidence_same_category(self, duplicate_detector):
        """Test same category gives 10 points"""
        record1 = {
            'title': 'Event A',
            'type_id': 'competition-uuid'
        }
        record2 = {
            'title': 'Event B',
            'type_id': 'competition-uuid'
        }
        
        score = duplicate_detector.calculate_confidence(record1, record2)
        
        assert score >= 10
    
    def test_calculate_confidence_completely_different(self, duplicate_detector):
        """Test completely different records give low score"""
        record1 = {
            'title': 'LOMBA ESSAY NASIONAL 2026',
            'organizer_name': 'Universitas A',
            'type_id': 'competition-uuid',
            'dates': {'deadline_date': '2026-04-20'}
        }
        record2 = {
            'title': 'BEASISWA S1 LUAR NEGERI',
            'organizer_name': 'Universitas B',
            'type_id': 'scholarship-uuid',
            'deadline_date': '2026-12-31'
        }
        
        score = duplicate_detector.calculate_confidence(record1, record2)
        
        assert score < 70  # Should not be considered a duplicate


@pytest.mark.unit
class TestDateOverlap:
    """Tests for date overlap detection"""
    
    def test_dates_overlap_same_date(self, duplicate_detector):
        """Test dates overlap when they are the same"""
        record1 = {'dates': {'deadline_date': '2026-04-20'}}
        record2 = {'deadline_date': '2026-04-20'}
        
        overlap = duplicate_detector._dates_overlap(record1, record2)
        
        assert overlap is True
    
    def test_dates_overlap_within_30_days(self, duplicate_detector):
        """Test dates overlap when within 30 days"""
        record1 = {'dates': {'deadline_date': '2026-04-20'}}
        record2 = {'deadline_date': '2026-04-25'}  # 5 days difference
        
        overlap = duplicate_detector._dates_overlap(record1, record2)
        
        assert overlap is True
    
    def test_dates_no_overlap_beyond_30_days(self, duplicate_detector):
        """Test dates don't overlap when >30 days apart"""
        record1 = {'dates': {'deadline_date': '2026-04-20'}}
        record2 = {'deadline_date': '2026-06-01'}  # 42 days difference
        
        overlap = duplicate_detector._dates_overlap(record1, record2)
        
        assert overlap is False
    
    def test_dates_overlap_missing_date(self, duplicate_detector):
        """Test dates don't overlap when one date is missing"""
        record1 = {'dates': {'deadline_date': '2026-04-20'}}
        record2 = {}  # No deadline
        
        overlap = duplicate_detector._dates_overlap(record1, record2)
        
        assert overlap is False
    
    def test_dates_overlap_invalid_date_format(self, duplicate_detector):
        """Test dates don't overlap with invalid date format"""
        record1 = {'dates': {'deadline_date': 'invalid-date'}}
        record2 = {'deadline_date': '2026-04-20'}
        
        overlap = duplicate_detector._dates_overlap(record1, record2)
        
        assert overlap is False
    
    def test_dates_overlap_datetime_objects(self, duplicate_detector):
        """Test dates overlap with datetime objects"""
        date1 = datetime(2026, 4, 20)
        date2 = datetime(2026, 4, 25)
        
        record1 = {'dates': {'deadline_date': date1}}
        record2 = {'deadline_date': date2}
        
        overlap = duplicate_detector._dates_overlap(record1, record2)
        
        assert overlap is True


@pytest.mark.unit
class TestFindCandidates:
    """Tests for candidate finding logic"""
    
    def test_find_candidates_by_title(self, duplicate_detector, mock_db_client):
        """Test finding candidates by title"""
        mock_db_client.execute_query.return_value = [
            {'title': 'LOMBA ESSAY', 'organizer_name': 'Org A'}
        ]
        
        new_record = {'title': 'LOMBA ESSAY'}
        
        candidates = duplicate_detector._find_candidates(new_record)
        
        assert len(candidates) == 1
        assert candidates[0]['title'] == 'LOMBA ESSAY'
    
    def test_find_candidates_by_organizer(self, duplicate_detector, mock_db_client):
        """Test finding candidates by organizer"""
        mock_db_client.execute_query.return_value = [
            {'title': 'Event A', 'organizer_name': 'Universitas Indonesia'},
            {'title': 'Event B', 'organizer_name': 'Universitas Indonesia'}
        ]
        
        new_record = {
            'title': 'Event C',
            'organizer_name': 'Universitas Indonesia'
        }
        
        candidates = duplicate_detector._find_candidates(new_record)
        
        assert len(candidates) == 2
    
    def test_find_candidates_empty_title(self, duplicate_detector):
        """Test finding candidates with empty title returns empty list"""
        new_record = {'title': ''}
        
        candidates = duplicate_detector._find_candidates(new_record)
        
        assert len(candidates) == 0
    
    def test_find_candidates_no_title(self, duplicate_detector):
        """Test finding candidates with no title returns empty list"""
        new_record = {}
        
        candidates = duplicate_detector._find_candidates(new_record)
        
        assert len(candidates) == 0


@pytest.mark.unit
class TestGetByPostId:
    """Tests for post_id lookup"""
    
    def test_get_by_post_id_found(self, duplicate_detector, mock_db_client, sample_extracted_data):
        """Test getting opportunity by post_id when it exists"""
        mock_db_client.execute_query.return_value = [sample_extracted_data]
        
        result = duplicate_detector._get_by_post_id('TEST_POST_123')
        
        assert result is not None
        assert result['post_id'] == 'TEST_POST_123'
    
    def test_get_by_post_id_not_found(self, duplicate_detector, mock_db_client):
        """Test getting opportunity by post_id when it doesn't exist"""
        mock_db_client.execute_query.return_value = []
        
        result = duplicate_detector._get_by_post_id('NONEXISTENT')
        
        assert result is None
