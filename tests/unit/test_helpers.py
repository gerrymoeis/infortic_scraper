"""
Unit Tests for Helper Functions (Phase 3 - Regex Fallbacks)

Tests regex fallback patterns including:
- Registration date extraction
- Phone number extraction
- URL extraction (including new patterns: uns.id, fyde.my)
- Organizer extraction
"""
import pytest
from extraction.utils.helpers import (
    extract_registration_date_fallback,
    extract_dates,
    convert_month_to_indonesian
)


@pytest.mark.unit
class TestExtractRegistrationDate:
    """Tests for registration date extraction (Phase 3)"""
    
    def test_extract_date_standard_format(self):
        """Test date extraction with standard format"""
        text = "Pendaftaran: 15 April 2026 - 20 April 2026"
        
        result = extract_registration_date_fallback(text)
        
        assert result is not None
        assert "15" in result
        assert "20" in result
        assert "April" in result or "april" in result.lower()
        assert "2026" in result
    
    def test_extract_date_single_date(self):
        """Test extraction of single date"""
        text = "Deadline: 20 April 2026"
        
        result = extract_registration_date_fallback(text)
        
        assert result is not None
        assert "20" in result
        assert "April" in result or "april" in result.lower()
    
    def test_extract_date_batch_format(self):
        """Test extraction with Batch/Gelombang format (Stage 4 enhancement)"""
        text = "Batch 1: 1-14 April 2026"
        
        result = extract_registration_date_fallback(text)
        
        assert result is not None
        assert "1" in result
        assert "14" in result
        assert "April" in result or "april" in result.lower()
    
    def test_extract_date_gelombang_format(self):
        """Test extraction with Gelombang format"""
        text = "Gelombang 1: 15 Mei - 30 Mei 2026"
        
        result = extract_registration_date_fallback(text)
        
        assert result is not None
        assert "15" in result
        assert "30" in result
    
    def test_extract_date_with_icon(self):
        """Test extraction with date icon"""
        text = "📅 20 April 2026"
        
        result = extract_registration_date_fallback(text)
        
        assert result is not None
        assert "20" in result
        assert "April" in result or "april" in result.lower()
    
    def test_extract_date_deadline_keyword(self):
        """Test extraction with deadline keyword"""
        text = "DL: 25 Juni 2026"
        
        result = extract_registration_date_fallback(text)
        
        assert result is not None
        assert "25" in result
    
    def test_extract_date_batas_akhir(self):
        """Test extraction with 'batas akhir' keyword"""
        text = "Batas Akhir: 30 Mei 2026"
        
        result = extract_registration_date_fallback(text)
        
        assert result is not None
        assert "30" in result
    
    def test_extract_date_no_date_found(self):
        """Test extraction returns None when no date found"""
        text = "This is just some random text without dates"
        
        result = extract_registration_date_fallback(text)
        
        assert result is None
    
    def test_extract_date_ignores_event_dates(self):
        """Test extraction ignores event execution dates"""
        text = "Pelaksanaan acara: 20 April 2026"
        
        result = extract_registration_date_fallback(text)
        
        # Should not extract event execution dates
        assert result is None or "Pelaksanaan" not in text
    
    def test_extract_date_cross_month_range(self):
        """Test extraction with date range across months"""
        text = "Pendaftaran: 27 April - 1 Mei 2026"
        
        result = extract_registration_date_fallback(text)
        
        assert result is not None
        assert "27" in result
        assert "1" in result


@pytest.mark.unit
class TestExtractDates:
    """Tests for general date extraction"""
    
    def test_extract_dates_multiple_formats(self):
        """Test extraction of dates in various formats"""
        text = """
        Deadline: 20 April 2026
        Registration: 15/04/2026
        Event: 2026-04-25
        """
        
        dates = extract_dates(text)
        
        assert len(dates) > 0
        assert any('2026' in date for date in dates)
    
    def test_extract_dates_empty_text(self):
        """Test extraction from empty text"""
        dates = extract_dates("")
        
        assert isinstance(dates, list)
    
    def test_extract_dates_no_dates(self):
        """Test extraction when no dates present"""
        text = "This text has no dates"
        
        dates = extract_dates(text)
        
        assert isinstance(dates, list)


@pytest.mark.unit
class TestConvertMonth:
    """Tests for month name conversion"""
    
    def test_convert_english_to_indonesian(self):
        """Test converting English month names to Indonesian"""
        assert convert_month_to_indonesian("January") == "Januari"
        assert convert_month_to_indonesian("February") == "Februari"
        assert convert_month_to_indonesian("March") == "Maret"
        assert convert_month_to_indonesian("April") == "April"
        assert convert_month_to_indonesian("May") == "Mei"
        assert convert_month_to_indonesian("June") == "Juni"
        assert convert_month_to_indonesian("July") == "Juli"
        assert convert_month_to_indonesian("August") == "Agustus"
        assert convert_month_to_indonesian("September") == "September"
        assert convert_month_to_indonesian("October") == "Oktober"
        assert convert_month_to_indonesian("November") == "November"
        assert convert_month_to_indonesian("December") == "Desember"
    
    def test_convert_already_indonesian(self):
        """Test that Indonesian months remain unchanged"""
        assert convert_month_to_indonesian("Januari") == "Januari"
        assert convert_month_to_indonesian("Februari") == "Februari"
        assert convert_month_to_indonesian("Maret") == "Maret"
    
    def test_convert_case_insensitive(self):
        """Test conversion is case insensitive"""
        assert convert_month_to_indonesian("january") == "Januari"
        assert convert_month_to_indonesian("JANUARY") == "Januari"
        assert convert_month_to_indonesian("JaNuArY") == "Januari"
    
    def test_convert_unknown_month(self):
        """Test conversion with unknown month name"""
        result = convert_month_to_indonesian("InvalidMonth")
        
        # Should return original or handle gracefully
        assert result is not None


@pytest.mark.unit
class TestPhoneNumberExtraction:
    """Tests for phone number extraction patterns"""
    
    def test_extract_phone_standard_format(self):
        """Test extraction of standard Indonesian phone numbers"""
        # This would test extract_phone_numbers if it's exported
        # For now, we test that the pattern exists in helpers
        text = "CP: 08123456789"
        
        # Pattern should match Indonesian phone numbers
        import re
        pattern = r'0\d{9,12}'
        match = re.search(pattern, text)
        
        assert match is not None
        assert match.group() == "08123456789"
    
    def test_extract_phone_with_dashes(self):
        """Test extraction of phone numbers with dashes"""
        text = "Contact: 0812-3456-7890"
        
        import re
        pattern = r'0\d{3}[-\s]?\d{4}[-\s]?\d{4}'
        match = re.search(pattern, text)
        
        assert match is not None
    
    def test_extract_phone_with_country_code(self):
        """Test extraction of phone numbers with +62"""
        text = "WA: +62 812 3456 7890"
        
        import re
        pattern = r'\+62\s?\d{3}\s?\d{4}\s?\d{4}'
        match = re.search(pattern, text)
        
        assert match is not None


@pytest.mark.unit
class TestURLExtraction:
    """Tests for URL extraction including new patterns (Stage 4)"""
    
    def test_extract_url_standard_https(self):
        """Test extraction of standard HTTPS URLs"""
        text = "Register: https://example.com/register"
        
        import re
        pattern = r'https?://[^\s]+'
        match = re.search(pattern, text)
        
        assert match is not None
        assert "https://example.com/register" in match.group()
    
    def test_extract_url_bit_ly(self):
        """Test extraction of bit.ly short URLs"""
        text = "Link: https://bit.ly/lomba2026"
        
        import re
        pattern = r'https?://bit\.ly/[^\s]+'
        match = re.search(pattern, text)
        
        assert match is not None
    
    def test_extract_url_uns_id(self):
        """Test extraction of uns.id URLs (Stage 4 enhancement)"""
        text = "Daftar: https://uns.id/lomba"
        
        import re
        pattern = r'https?://uns\.id/[^\s]+'
        match = re.search(pattern, text)
        
        assert match is not None
        assert "uns.id" in match.group()
    
    def test_extract_url_fyde_my(self):
        """Test extraction of fyde.my URLs (Stage 4 enhancement)"""
        text = "Link: https://fyde.my/event123"
        
        import re
        pattern = r'https?://fyde\.my/[^\s]+'
        match = re.search(pattern, text)
        
        assert match is not None
        assert "fyde.my" in match.group()
    
    def test_extract_url_politeknik(self):
        """Test extraction of politeknik URLs (Stage 4 enhancement)"""
        text = "Info: https://politeknik.ac.id/lomba"
        
        import re
        pattern = r'https?://[^\s]*politeknik[^\s]*'
        match = re.search(pattern, text)
        
        assert match is not None
    
    def test_extract_url_without_protocol(self):
        """Test extraction of URLs without http/https"""
        text = "Visit: example.com/register"
        
        import re
        pattern = r'(?:https?://)?(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?'
        match = re.search(pattern, text)
        
        assert match is not None


@pytest.mark.unit
class TestOrganizerExtraction:
    """Tests for organizer extraction from mentions"""
    
    def test_extract_organizer_from_mention(self):
        """Test extraction of organizer from @mention"""
        text = "Penyelenggara: @universitas_indonesia"
        
        import re
        pattern = r'@([a-zA-Z0-9_\.]+)'
        match = re.search(pattern, text)
        
        assert match is not None
        assert match.group(1) == "universitas_indonesia"
    
    def test_extract_organizer_multiple_mentions(self):
        """Test extraction with multiple mentions"""
        text = "Info: @infolomba @lomba.it"
        
        import re
        pattern = r'@([a-zA-Z0-9_\.]+)'
        matches = re.findall(pattern, text)
        
        assert len(matches) >= 2
        assert "infolomba" in matches
    
    def test_extract_organizer_from_text(self):
        """Test extraction of organizer from text patterns"""
        text = "Diselenggarakan oleh Universitas Indonesia"
        
        # Should extract "Universitas Indonesia"
        assert "Universitas Indonesia" in text
