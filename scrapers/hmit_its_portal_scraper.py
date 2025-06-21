import logging
from .base_google_sheets_scraper import BaseGoogleSheetScraper

class HmitItsPortalScraper(BaseGoogleSheetScraper):
    """
    Scraper for the HMIT-ITS Lomba dan Sertifikasi Portal.
    This scraper fetches a single HTML page that contains multiple tables for different
    event types (Lomba, Sertifikasi) and scrapes them all.
    """

    def __init__(self, supabase_client, source_name, debug=False):
        super().__init__(supabase_client, source_name, debug=debug)
        self.dashboard_url = "https://docs.google.com/spreadsheets/d/1qjvZtMiW2qqeIOChAFXLS5vSzZQo53oit60XvYW6mL0/htmlview"
        
        # Configuration for different event types found in the sheet
        self.table_configs = {
            'lomba': {
                'name_keywords': ['lomba'],
                'required_keywords': ['nama', 'penyelenggara', 'tanggal'],
                'column_mapping': {
                    'title': 'nama lomba',
                    'organizer': 'penyelenggara',
                    'registration_deadline': 'tanggal pendaftaran',
                    'event_date': 'tanggal lomba',
                    'price': 'biaya registrasi',
                    'registration_url': 'informasi lebih lanjut',
                    'status': 'status pendaftaran'
                },
                'event_type': 'Lomba'
            },
            'sertifikasi': {
                'name_keywords': ['sertifikasi'],
                'required_keywords': ['nama', 'penyelenggara', 'tanggal'],
                'column_mapping': {
                    'title': 'nama sertifikasi',
                    'organizer': 'penyelenggara',
                    'registration_deadline': 'tanggal pendaftaran',
                    'price': 'biaya pendaftaran',
                    'registration_url': 'informasi lebih lanjut',
                    'status': 'status pendaftaran'
                },
                'event_type': 'Sertifikasi'
            }
        }

    def scrape(self):
        self.logger.info(f"Starting scrape for {self.source_name}")
        soup = self._fetch_and_parse_sheet(self.dashboard_url, "main_page")
        if not soup:
            return []

        all_events = []
        all_tables = soup.find_all('table')
        self.logger.info(f"Found {len(all_tables)} tables in the document. Analyzing each...")

        for i, table in enumerate(all_tables):
            events = self.process_table(table, i)
            if events:
                all_events.extend(events)

        self.logger.info(f"Successfully scraped a total of {len(all_events)} events from {self.source_name}")
        return all_events

    def process_table(self, table, table_index):
        rows = table.find('tbody').find_all('tr') if table.find('tbody') else table.find_all('tr')
        if len(rows) < 2: # Must have at least a header and one data row
            return []

        for config_name, config in self.table_configs.items():
            header_map, header_row_index = self.find_header(
                rows, config['name_keywords'], config['required_keywords']
            )

            if header_map:
                self.logger.info(f"Table {table_index} identified as '{config_name}'. Header found at row {header_row_index}.")
                column_map = self.create_dynamic_column_map(header_map, config['column_mapping'])
                
                if not column_map.get('title') or not column_map.get('registration_url'):
                    self.logger.warning(f"Skipping table {table_index} ('{config_name}') due to missing critical columns 'title' or 'registration_url'.")
                    continue

                events = []
                for i, row in enumerate(rows[header_row_index:]):
                    cells = row.find_all(['td', 'th'])
                    if not any(cell.get_text(strip=True) for cell in cells):
                        continue

                    event_data = self.extract_event_data(cells, column_map)
                    if event_data and event_data.get('status', '').lower() == 'buka':
                        if not event_data.get('registration_url'):
                            self.logger.warning(f"Skipping event '{event_data.get('title')}' because it has no registration URL.")
                            continue
                        event_data['event_type'] = config['event_type']
                        event_data['source_url'] = self.dashboard_url
                        events.append(event_data)
                
                self.logger.info(f"Found {len(events)} valid events in table {table_index} ('{config_name}').")
                return events
        return []
