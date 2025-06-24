import os
import time
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from .base_web_scraper import BaseWebScraper

class InfolombaScraper(BaseWebScraper):
    def __init__(self, supabase_client, source_name='infolomba.id', debug=False):
        super().__init__(supabase_client, source_name, debug=debug)
        self.base_url = "https://www.infolomba.id/"

    def scrape(self):
        """Scraper untuk mengambil data dari infolomba.id dan mengembalikannya sebagai list."""
        self.logger.info(f"Memulai scrape untuk {self.source_name} menggunakan Playwright.")
        
        page = self.get_page(self.base_url)
        if not page:
            return []

        html_content = ""
        try:
            self.logger.info("Halaman utama berhasil dimuat.")

            # Klik tombol 'Muat lebih banyak event' sebanyak 15 kali
            for i in range(15):
                try:
                    load_more_button = page.query_selector('#btnLoadMore')
                    if load_more_button and load_more_button.is_visible():
                        self.logger.info(f"Mencoba klik tombol 'Muat lebih banyak event' ke-{i+1}/15")
                        load_more_button.click()
                        time.sleep(2) # Menunggu 2 detik setelah setiap klik
                    else:
                        self.logger.info("Tombol 'Muat lebih banyak event' tidak ditemukan atau tidak terlihat. Berhenti.")
                        break
                except Exception as e:
                    self.logger.warning(f"Gagal mengklik tombol 'Muat lebih banyak event': {e}")
                    break
            
            html_content = page.content()
            if self.debug:
                self.save_debug_page(page, "infolomba_main_page")

        except Exception as e:
            self.logger.error(f"Gagal mengambil halaman dengan Playwright: {e}")
            return []
        finally:
            page.close()

        if not html_content:
            self.logger.error(f"Gagal mendapatkan konten HTML untuk {self.source_name}.")
            return []

        soup = BeautifulSoup(html_content, 'html.parser')
        
        event_list_container = soup.find('div', class_='event-list')
        if not event_list_container:
            self.logger.warning("Container utama event ('div.event-list') tidak ditemukan.")
            return []

        # Find all event title links directly, which might be more stable
        event_links = event_list_container.select('h4.event-title a')
        self.logger.info(f"Ditemukan {len(event_links)} link event di infolomba.id.")

        if not event_links:
            self.logger.warning("Tidak ada link event yang ditemukan dengan selector 'h4.event-title a'.")
            return []

        scraped_events = []
        for link_element in event_links:
            # The container is likely the parent of the parent of the link (a -> h4 -> div)
            event_div = link_element.find_parent('h4').parent
            if not event_div:
                self.logger.warning(f"Tidak bisa menemukan container induk untuk link: {link_element.get('href', 'N/A')}. Skipping.")
                continue

            if not link_element.has_attr('href'):
                self.logger.warning(f"Tidak bisa menemukan link detail untuk sebuah event. Skipping.")
                continue
                
            detail_page_path = link_element['href']

            date_element = event_div.find('div', class_='tanggal')
            date_raw_text = date_element.text.strip() if date_element else 'Tidak ada tanggal'

            price_element = event_div.find('div', class_='biaya')
            price_raw_text = price_element.text.strip() if price_element else 'Gratis'
            
            detail_url = urljoin(self.base_url, detail_page_path)
            self.logger.info(f"Scraping detail dari: {detail_url}")
            
            detail_data = self._deep_scrape(detail_url)
            
            if detail_data:
                # 'url' sekarang adalah halaman detail, 'registration_url' adalah link pendaftaran
                full_event_data = {
                    'date_text': date_raw_text,
                    'price_raw_text': price_raw_text,
                    'url': detail_url, # Menyimpan URL halaman detail
                    **detail_data
                }
                scraped_events.append(full_event_data)
                self.logger.info(f"Successfully scraped: {full_event_data['title']}")
            else:
                self.logger.warning(f"Failed to process details for: {detail_url}")

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
            registration_url = registration_link_element['href'] if registration_link_element else None

            # Scraping data tambahan
            participant_element = detail_container.select_one('div.target')
            participant = participant_element.text.strip().replace('SMA / Sederajat, Mahasiswa', 'SMA, Mahasiswa').replace('\n', '').strip() if participant_element else 'Umum'

            location_element = detail_container.select_one('div.lokasi')
            location = location_element.text.strip().replace('\n', '').strip() if location_element else 'Online'

            self.logger.debug(f"Deep scrape check for {detail_url}: title='{title}', poster_url='{poster_url}', registration_url='{registration_url}'")

            # --- Validation for Required Fields ---
            if not all([title, poster_url, registration_url]):
                self.logger.warning(f"Skipping detail page {detail_url} due to missing required fields (title, poster, or registration URL).")
                return None
            # --- End Validation ---

            return {
                'title': title,
                'description': description,
                'organizer': organizer,
                'poster_url': poster_url,
                'registration_url': registration_url,
                'participant': participant,
                'location': location
            }

        except Exception as e:
            self.logger.error(f"Gagal mem-parsing halaman detail {detail_url}: {e}", exc_info=True)
            return None
