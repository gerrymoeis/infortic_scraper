import requests
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from .base_scraper import BaseScraper
import os
from datetime import datetime

class BaseGoogleSheetScraper(BaseScraper):
    """A base class for scraping data from Google Sheets published as HTML."""

    def __init__(self, supabase_client, source_name, debug=False):
        super().__init__(supabase_client, source_name)
        self.sheet_url = None # This should be set by the child class
        self.debug = debug
        self.debug_dir = 'debug_output'
        if self.debug:
            os.makedirs(self.debug_dir, exist_ok=True)
        self.logger.info(f'Scraper untuk {source_name} telah diinisialisasi (Debug: {self.debug}).')

    def _get_real_url(self, google_url):
        """Extracts the real destination URL from a Google redirect URL."""
        if not google_url or 'google.com/url?q=' not in google_url:
            return google_url
        try:
            parsed_url = urlparse(google_url)
            return parse_qs(parsed_url.query)['q'][0]
        except (KeyError, IndexError):
            self.logger.warning(f"Could not parse Google redirect URL: {google_url}")
            return google_url

    def _save_debug_html(self, content, sheet_name):
        if not self.debug:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.source_name}_{sheet_name}_{timestamp}.html"
        filepath = os.path.join(self.debug_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.info(f"Debug HTML disimpan di {filepath}")
        except Exception as e:
            self.logger.error(f"Gagal menyimpan debug HTML ke {filepath}: {e}")

    def _fetch_and_parse_sheet(self, url, sheet_name="sheet"):
        self.logger.info(f"Fetching data from {url}")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            self._save_debug_html(response.text, sheet_name)
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch the spreadsheet URL {url}: {e}")
            return None

    def scrape(self):
        """Main scraping method to be implemented by child classes."""
        raise NotImplementedError("The 'scrape' method must be implemented by a child class.")

    def find_header(self, rows, name_keywords: list, required_keywords: list) -> tuple[dict, int]:
        for i, row in enumerate(rows):
            cells = row.find_all(['td', 'th'])
            cell_texts = [cell.get_text().lower().strip() for cell in cells]
            
            has_name = any(kw in ' '.join(cell_texts) for kw in name_keywords)
            has_required = all(any(req_kw in text for text in cell_texts) for req_kw in required_keywords)

            if len(cell_texts) > 3 and has_name and has_required:
                self.logger.info(f"Header row found at index {i} for {self.source_name}.")
                header_map = {text: idx for idx, text in enumerate(cell_texts) if text}
                return header_map, i + 1
        
        return {}, -1

    def map_columns(self, header_map: dict, column_definitions: dict) -> dict:
        col_map = {}
        for col_name, keywords in column_definitions.items():
            try:
                col_map[col_name] = next(idx for key, idx in header_map.items() if any(kw in key for kw in keywords))
            except StopIteration:
                self.logger.warning(f"Column '{col_name}' could not be mapped for {self.source_name}.")
        return col_map

    def create_dynamic_column_map(self, header_map: dict, column_mapping: dict) -> dict:
        """
        Creates a column map by finding the index of a header that contains the text defined in column_mapping.
        Example: header_map = {'nama lengkap': 0, 'tanggal pendaftaran': 1}, column_mapping = {'title': 'nama', 'deadline': 'tanggal'}
        Returns: {'title': 0, 'deadline': 1}
        """
        col_map = {}
        for field, keyword in column_mapping.items():
            keyword = keyword.lower().strip()
            found = False
            for header_text, index in header_map.items():
                if keyword in header_text:
                    col_map[field] = index
                    found = True
                    break
            if not found:
                self.logger.warning(f"Dynamic column for '{field}' with keyword '{keyword}' not found in headers.")
        return col_map

    def extract_event_data(self, cells: list, col_map: dict) -> dict | None:
        try:
            data = {}
            # Extract text from each required cell using the map
            for key, index in col_map.items():
                if index < len(cells):
                    if key == 'registration_url':
                        link_cell = cells[index].find('a')
                        data[key] = self._get_real_url(link_cell['href']) if link_cell else None
                    else:
                        data[key] = cells[index].get_text(strip=True)
                else:
                    data[key] = None

            # Basic validation
            if not data.get('title') or not data.get('registration_url'):
                return None
            
            return data
        except (IndexError, AttributeError, KeyError) as e:
            self.logger.warning(f"Skipping a row for {self.source_name} due to data extraction error: {e}")
            return None
