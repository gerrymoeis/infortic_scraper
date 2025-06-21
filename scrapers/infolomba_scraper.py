from urllib.parse import urljoin
from .base_web_scraper import BaseWebScraper

class InfolombaScraper(BaseWebScraper):
    def __init__(self, supabase_client, source_name='infolomba.id', debug=False):
        super().__init__(supabase_client, source_name, debug=debug)
        self.base_url = "https://www.infolomba.id/"

    def scrape(self):
        """Scraper untuk mengambil data dari infolomba.id dan mengembalikannya sebagai list."""
        self.logger.info(f"Mengambil data dari {self.base_url}")
        
        soup = self._fetch_static_page(self.base_url)
        if not soup:
            return []
        
        event_list_container = soup.find('div', id='eventsContainer')
        if not event_list_container:
            self.logger.warning("Container utama event ('eventsContainer') tidak ditemukan.")
            return []

        events_html = event_list_container.find_all('div', class_='event-container')
        
        if not events_html:
            self.logger.warning("Tidak ada event yang ditemukan dengan selector 'div.event-container'.")
            return []

        scraped_events = []
        for event_div in events_html:
            link_element = event_div.select_one('h4.event-title a')
            if not link_element or not link_element.has_attr('href'):
                self.logger.warning(f"Tidak bisa menemukan link detail untuk sebuah event. Skipping.")
                continue
                
            detail_page_path = link_element['href']

            date_element = event_div.find('div', class_='tanggal')
            date_raw_text = date_element.text.strip() if date_element else 'Tidak ada tanggal'

            price_element = event_div.find('div', class_='biaya')
            price_info = price_element.text.strip() if price_element else 'Gratis'
            
            detail_url = urljoin(self.base_url, detail_page_path)
            self.logger.info(f"Scraping detail dari: {detail_url}")
            
            detail_data = self._deep_scrape(detail_url)
            
            if detail_data and detail_data['title']:
                # Gabungkan data dari halaman list dan halaman detail
                full_event_data = {
                    'date_raw_text': date_raw_text,
                    'price_info': price_info,
                    'source_url': detail_url, # Menyimpan URL unik dari halaman detail
                    **detail_data
                }
                scraped_events.append(full_event_data)
                self.logger.info(f"Berhasil scrape: {full_event_data['title']}")
            else:
                self.logger.warning(f"Gagal memproses detail untuk: {detail_url}")

        return scraped_events

    def _deep_scrape(self, detail_url):
        """Scrapes a single event detail page for more information."""
        soup = self._fetch_static_page(detail_url)
        if not soup:
            return None

        try:

            detail_container = soup.select_one('div.event-details-container')
            if not detail_container:
                self.logger.warning(f"Tidak dapat menemukan container detail utama di {detail_url}")
                return None

            title = detail_container.select_one('h4.event-title').text.strip() if detail_container.select_one('h4.event-title') else None
            
            description_element = detail_container.select_one('div.event-description-container')
            description = description_element.get_text(separator='\n', strip=True) if description_element else None

            organizer_element = detail_container.select_one('div.penyelenggara div span:last-of-type')
            organizer = organizer_element.text.strip() if organizer_element else 'Tidak disebutkan'

            poster_link_element = detail_container.select_one('a.image-link')
            poster_url_relative = poster_link_element['href'] if poster_link_element else None
            poster_url = urljoin(self.base_url, poster_url_relative) if poster_url_relative else None

            registration_link_element = detail_container.select_one('a.btn.btn-primary[target="_blank"]')
            registration_link = registration_link_element['href'] if registration_link_element else None

            return {
                'title': title,
                'description': description,
                'organizer': organizer,
                'poster_url': poster_url,
                'registration_url': registration_link,
            }

        except Exception as e:
            self.logger.error(f"Gagal mem-parsing halaman detail {detail_url}: {e}", exc_info=True)
            return None
