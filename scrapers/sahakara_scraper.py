from .base_google_sheets_scraper import BaseGoogleSheetScraper

class SahakaraScraper(BaseGoogleSheetScraper):
    def __init__(self, supabase_client, source_name='google-sheets-sahakara', debug=False):
        super().__init__(supabase_client, source_name, debug=debug)
        self.sheet_url = "https://docs.google.com/spreadsheets/d/1L3bhyDR-1sPw28IZM9UQFWItbC_OFvFmmEr12kQCtIM/htmlview#gid=1975790205"

    def scrape(self):
        self.logger.info(f'Starting scrape for {self.source_name}')
        soup = self._fetch_and_parse_sheet(self.sheet_url, 'sahakara')
        if not soup:
            return []

        events = []
        table = soup.find('table')
        if not table:
            self.logger.error("Could not find the table in the spreadsheet HTML.")
            return events

        rows = table.find('tbody').find_all('tr')
        self.logger.info(f"Found {len(rows)} rows in the table.")

        header_map, start_row_index = self.find_header(
            rows,
            name_keywords=['nama', 'lomba', 'kompetisi', 'event'],
            required_keywords=['link']
        )

        if not header_map:
            self.logger.warning(f"Could not find a valid header row for {self.source_name}. Skipping.")
            return []

        col_map = self.map_columns(header_map, {
            'title': ['nama', 'lomba', 'kompetisi', 'event'],
            'organizer': ['penyelenggara'],
            'date_raw_text': ['deadline', 'tanggal', 'waktu'],
            'registration_url': ['link', 'pendaftaran', 'guidebook', 'web/link'],
            'price_info': ['biaya', 'htm', 'harga', 'fee'],
            'description': ['deskripsi', 'keterangan', 'tingkat']
        })

        if not all(k in col_map for k in ['title', 'registration_url', 'date_raw_text']):
            self.logger.error(f"Could not map all required columns for {self.source_name}. Mapped: {col_map.keys()}")
            return []

        for row in rows[start_row_index:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < len(header_map):
                continue
            
            event_data = self.extract_event_data(cells, col_map)
            if not event_data:
                continue

            if not event_data.get('registration_url'):
                self.logger.warning(f"Skipping event '{event_data.get('title')}' because it has no registration URL.")
                continue
            
            event_data['event_type'] = 'Lomba'
            event_data['source_url'] = self.sheet_url
            events.append(event_data)

        self.logger.info(f"Successfully scraped {len(events)} events from {self.source_name}")
        return events
