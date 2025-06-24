from .base_google_sheets_scraper import BaseGoogleSheetScraper

class RndInfoCenterScraper(BaseGoogleSheetScraper):
    def __init__(self, supabase_client, source_name='google-sheets-rnd-info-center', debug=False):
        super().__init__(supabase_client, source_name, debug=debug)
        self.sheet_urls = {
            'lomba': 'https://docs.google.com/spreadsheets/d/1WLZSnPJ28EFXR66ObiCmqpqk1ffDREI_t5DSGrhd35Q/htmlview?gid=803178763',
            'lainnya': 'https://docs.google.com/spreadsheets/d/1WLZSnPJ28EFXR66ObiCmqpqk1ffDREI_t5DSGrhd35Q/htmlview?gid=1523477433'
        }

    def scrape(self):
        self.logger.info(f'Starting scrape for {self.source_name}')
        all_events = []
        all_events.extend(self._scrape_lomba_sheet(self.sheet_urls['lomba']))
        all_events.extend(self._scrape_lainnya_sheet(self.sheet_urls['lainnya']))
        self.logger.info(f"Successfully scraped a total of {len(all_events)} events from {self.source_name}")
        return all_events

    def _scrape_lomba_sheet(self, url):
        self.logger.info("Scraping 'Lomba' sheet...")
        soup = self._fetch_and_parse_sheet(url, 'lomba')
        if not soup:
            return []

        events = []
        table = soup.find('table')
        if not table:
            self.logger.error("Could not find the table in the 'Lomba' sheet.")
            return events

        rows = table.find('tbody').find_all('tr')
        self.logger.info(f"Found {len(rows)} rows in the 'Lomba' table.")

        header_map, start_row_index = self.find_header(
            rows,
            name_keywords=['nama lomba', 'nama kegiatan'],
            required_keywords=['link']
        )

        if not header_map:
            self.logger.warning("Could not find a valid header row for 'Lomba' sheet. Skipping.")
            return []

        col_map = self.map_columns(header_map, {
            'title': ['nama lomba', 'nama kegiatan'],
            'organizer': ['penyelenggara'],
            'date_raw_text': ['deadline pendaftaran'],
            'registration_url': ['link pendaftaran', 'link informasi'],
            'price_raw_text': ['biaya pendaftaran'],
            'status': ['status']
        })

        if not all(k in col_map for k in ['title', 'status', 'registration_url']):
            self.logger.error(f"Could not map all required columns for 'Lomba' sheet. Mapped: {col_map.keys()}")
            return []

        for row in rows[start_row_index:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < len(header_map):
                continue

            event_data = self.extract_event_data(cells, col_map)
            if not event_data or 'open' not in event_data.get('status', '').lower():
                continue

            if not event_data.get('registration_url'):
                self.logger.warning(f"Skipping event '{event_data.get('title')}' because it has no registration URL.")
                continue

            event_data['event_type'] = 'Lomba'
            event_data['source_url'] = url
            event_data['description'] = f"Diselenggarakan oleh {event_data.get('organizer', 'N/A')}"
            events.append(event_data)

        self.logger.info(f"Found {len(events)} valid events in 'Lomba' sheet.")
        return events

    def _scrape_lainnya_sheet(self, url):
        self.logger.info("Scraping 'Lainnya' sheet...")
        soup = self._fetch_and_parse_sheet(url, 'lainnya')
        if not soup:
            return []

        events = []
        table = soup.find('table')
        if not table:
            self.logger.error("Could not find the table in the 'Lainnya' sheet.")
            return events

        rows = table.find('tbody').find_all('tr')
        self.logger.info(f"Found {len(rows)} rows in the 'Lainnya' table.")

        header_map, start_row_index = self.find_header(
            rows,
            name_keywords=['nama kegiatan'],
            required_keywords=['link']
        )

        if not header_map:
            self.logger.warning("Could not find a valid header row for 'Lainnya' sheet. Skipping.")
            return []

        col_map = self.map_columns(header_map, {
            'title': ['nama kegiatan'],
            'organizer': ['penyelenggara'],
            'date_raw_text': ['deadline pendaftaran'],
            'registration_url': ['link pendaftaran', 'link informasi'],
            'price_raw_text': ['biaya pendaftaran'],
            'status': ['status'],
            'event_type_raw': ['jenis kegiatan']
        })

        if not all(k in col_map for k in ['title', 'status', 'registration_url']):
            self.logger.error(f"Could not map all required columns for 'Lainnya' sheet. Mapped: {col_map.keys()}")
            return []

        for row in rows[start_row_index:]:
            cells = row.find_all(['td', 'th'])
            if len(cells) < len(header_map):
                continue

            event_data = self.extract_event_data(cells, col_map)
            if not event_data or 'open' not in event_data.get('status', '').lower():
                continue

            if not event_data.get('registration_url'):
                self.logger.warning(f"Skipping event '{event_data.get('title')}' because it has no registration URL.")
                continue
            
            event_type_raw = event_data.get('event_type_raw', '').lower()
            if 'bootcamp' in event_type_raw:
                event_data['event_type'] = 'Pelatihan'
            elif 'sertifikasi' in event_type_raw:
                event_data['event_type'] = 'Sertifikasi'
            elif 'magang' in event_type_raw:
                event_data['event_type'] = 'Magang'
            else:
                event_data['event_type'] = 'Lainnya'


            event_data['source_url'] = url
            event_data['description'] = f"{event_data['event_type']} diselenggarakan oleh {event_data.get('organizer', 'N/A')}"
            events.append(event_data)

        self.logger.info(f"Found {len(events)} valid events in 'Lainnya' sheet.")
        return events
