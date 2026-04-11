"""
Pytest Configuration and Shared Fixtures

This file contains pytest configuration and fixtures that are shared
across all test files.
"""
import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path so tests can import modules
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))


# ============================================================================
# Sample Data Fixtures
# ============================================================================

@pytest.fixture
def sample_caption_data():
    """Sample Instagram caption data for testing extraction"""
    return {
        "post_id": "TEST_POST_123",
        "caption": """LOMBA ESSAY NASIONAL 2026

Tema: Inovasi Teknologi untuk Indonesia Maju

📅 Deadline: 20 April 2026
📝 Pendaftaran: 15 April 2026
📱 CP: 08123456789
🌐 Link: https://bit.ly/lombaessay2026

Terbuka untuk:
- SMA/SMK
- Mahasiswa D3/D4/S1

Penyelenggara: @universitas_indonesia
        """,
        "image_path": "data/images/TEST_POST_123.jpg",
        "source_account": "infolomba"
    }


@pytest.fixture
def sample_extracted_data():
    """Sample extracted opportunity data (after AI extraction)"""
    return {
        "post_id": "TEST_POST_123",
        "title": "LOMBA ESSAY NASIONAL 2026",
        "category": "competition",
        "deadline_date": "2026-04-20",
        "registration_date": "2026-04-15",
        "contact": "08123456789",
        "registration_url": "https://bit.ly/lombaessay2026",
        "audiences": ["sma", "smk", "d3", "d4", "s1"],
        "organizer": "Universitas Indonesia",
        "description": "Lomba essay dengan tema Inovasi Teknologi untuk Indonesia Maju",
        "source_account": "infolomba",
        "image_path": "data/images/TEST_POST_123.jpg"
    }


@pytest.fixture
def sample_extracted_data_minimal():
    """Sample extracted data with only required fields"""
    return {
        "post_id": "TEST_POST_MIN",
        "title": "Workshop AI 2026",
        "category": "workshop",
        "deadline_date": "2026-05-01",
        "audiences": ["umum"],
        "source_account": "lomba.it"
    }


@pytest.fixture
def sample_extracted_data_with_new_audiences():
    """Sample data with newly added audience codes (smk, sd, d2)"""
    return {
        "post_id": "TEST_POST_NEW_AUD",
        "title": "Kompetisi Robotik SD 2026",
        "category": "competition",
        "deadline_date": "2026-06-15",
        "registration_date": "2026-06-01",
        "audiences": ["sd", "smk", "d2"],  # New audience codes
        "organizer": "Kementerian Pendidikan",
        "source_account": "infolomba"
    }


@pytest.fixture
def sample_expired_data():
    """Sample data with expired deadline (for Phase 1 testing)"""
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    return {
        "post_id": "TEST_POST_EXPIRED",
        "title": "Lomba Expired 2026",
        "category": "competition",
        "deadline_date": yesterday,
        "audiences": ["sma"],
        "source_account": "infolomba"
    }


@pytest.fixture
def sample_future_data():
    """Sample data with future deadline (active)"""
    future_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    return {
        "post_id": "TEST_POST_FUTURE",
        "title": "Lomba Future 2026",
        "category": "competition",
        "deadline_date": future_date,
        "audiences": ["sma"],
        "source_account": "infolomba"
    }


@pytest.fixture
def sample_duplicate_data():
    """Sample data for duplicate detection testing"""
    return [
        {
            "post_id": "POST_A",
            "title": "KAHFI 2 FESTIVAL 2026",
            "category": "festival",
            "deadline_date": "2026-04-25",
            "organizer": "KAHFI",
            "audiences": ["sma"],
            "source_account": "infolomba"
        },
        {
            "post_id": "POST_B",
            "title": "KAHFI 2 Festival 2026",  # Similar title
            "category": "festival",
            "deadline_date": "2026-04-25",
            "organizer": "KAHFI",
            "audiences": ["sma"],
            "source_account": "lomba.it"  # Different source
        }
    ]


# ============================================================================
# Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_db_client(mocker):
    """Mock database client for unit tests"""
    mock = mocker.Mock()
    mock.connect.return_value = None
    mock.close.return_value = None
    mock.execute_query.return_value = []
    mock.get_cursor.return_value = mocker.Mock()
    return mock


@pytest.fixture
def mock_gemini_client(mocker):
    """Mock Gemini API client for unit tests"""
    mock = mocker.Mock()
    mock.extract_batch.return_value = {
        "items": [
            {
                "post_id": "TEST_POST_123",
                "title": "Test Event",
                "category": "competition",
                "deadline_date": "2026-04-20"
            }
        ]
    }
    return mock


@pytest.fixture
def mock_ocr_extractor(mocker):
    """Mock OCR extractor for unit tests"""
    mock = mocker.Mock()
    mock.extract_text.return_value = "Deadline: 20 April 2026"
    mock.extract_with_confidence.return_value = ("Deadline: 20 April 2026", 85)
    return mock


# ============================================================================
# Database Fixtures (for integration tests)
# ============================================================================

@pytest.fixture
def audience_mapping():
    """Standard audience code mapping"""
    return {
        "smp": "SMP",
        "sma": "SMA / SMK",
        "smk": "SMK",  # New
        "sd": "SD",    # New
        "d2": "D2",    # New
        "d3": "D3",
        "d4": "D4",
        "s1": "S1",
        "umum": "Umum"
    }


@pytest.fixture
def type_mapping():
    """Standard opportunity type mapping"""
    return {
        "competition": "Kompetisi",
        "scholarship": "Beasiswa",
        "internship": "Magang",
        "job": "Lowongan Kerja",
        "freelance": "Freelance",
        "training": "Pelatihan",
        "tryout": "Try Out",
        "workshop": "Workshop",
        "festival": "Festival",
        "hackathon": "Hackathon"
    }


# ============================================================================
# Helper Functions
# ============================================================================

@pytest.fixture
def assert_valid_iso_date():
    """Helper to assert a string is a valid ISO date"""
    def _assert(date_string):
        try:
            datetime.fromisoformat(date_string)
            return True
        except (ValueError, TypeError):
            return False
    return _assert
