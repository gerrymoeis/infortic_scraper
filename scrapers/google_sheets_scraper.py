import requests
import os
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from .base_scraper import BaseScraper

class GoogleSheetsScraper(BaseScraper):
    def __init__(self, supabase_client, source_name='google-sheets-himakom'):
        super().__init__(supabase_client, source_name)
        self.base_url = "https://docs.google.com/spreadsheets/u/0/d/1flUcng-naIX-YpjrxmVTUMiGwsuZmFKweazifHS5pNw/htmlview"

    def _get_real_url(self, google_url):
        """Extracts the real destination URL from a Google redirect URL."""
        try:
            parsed_url = urlparse(google_url)
            # The real URL is in the 'q' query parameter
            return parse_qs(parsed_url.query)['q'][0]
        except (KeyError, IndexError, Exception) as e:
            self.logger.warning(f"Could not parse Google redirect URL: {google_url}. Error: {e}")
            return google_url # Fallback to the original URL

    def scrape(self):
        self.logger.info(f'Starting scrape for {self.source_name}')
        events = []
        try:
            response = requests.get(self.base_url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch the spreadsheet URL: {e}")
            return events

        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find the table body containing the data
        table_body = soup.find('tbody')
        if not table_body:
            self.logger.error("Could not find the table body (tbody) in the spreadsheet HTML.")
            return events

        rows = table_body.find_all('tr')
        self.logger.info(f"Found {len(rows)} rows in the table.")

        # Skip header rows (assuming first 5 are headers/empty)
        for row in rows[5:]:
            cells = row.find_all('td')
            # Adjusted length check to account for the row header cell
            if len(cells) < 9:
                continue # Skip malformed rows

            try:
                # Indexes are shifted by +1 because cells[0] is the row header
                status = cells[8].text.strip()
                if status.upper() != 'OPEN':
                    continue

                competition_name = cells[1].text.strip()
                field = cells[2].text.strip()
                start_date = cells[3].text.strip()
                end_date = cells[4].text.strip()
                link_cell = cells[6].find('a')
                registration_url = self._get_real_url(link_cell['href']) if link_cell else None
                fee = cells[7].text.strip()

                if not registration_url:
                    self.logger.warning(f"Skipping '{competition_name}' because it has no registration link.")
                    continue

                event_data = {
                    'title': competition_name,
                    'description': f"{competition_name} dalam bidang {field}.",
                    'url': registration_url, # Use registration link as the primary URL for this source
                    'registration_url': registration_url,
                    'event_date_start': start_date,
                    'event_date_end': end_date,
                    'deadline': end_date, # Assume deadline is the same as end date
                    'price_raw_text': fee,
                    'organizer': 'HIMAKOM',
                    'poster_url': None, # No poster URL available in sheets
                    'source_name': self.source_name,
                    'date_raw_text': f"Start: {start_date}, End: {end_date}"
                }
                events.append(event_data)

            except (IndexError, AttributeError) as e:
                self.logger.warning(f"Skipping a row due to parsing error: {e}")
                continue

        self.logger.info(f"Successfully scraped {len(events)} OPEN events from {self.source_name}")
        return events
