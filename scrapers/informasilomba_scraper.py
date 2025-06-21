import re
from urllib.parse import urljoin
from .base_web_scraper import BaseWebScraper

class InformasilombaScraper(BaseWebScraper):
    def __init__(self, supabase_client, source_name='informasilomba.com', debug=False):
        super().__init__(supabase_client, source_name, debug=debug)
        self.base_url = "https://www.informasilomba.com/"

    def scrape(self):
        """Scrapes event data from informasilomba.com."""
        self.logger.info(f"Mengambil data dari {self.base_url}")
        scraped_events = []

        soup = self._fetch_static_page(self.base_url)
        if not soup:
            return scraped_events
        event_links = soup.select('h2.post-title a')
        self.logger.info(f"Menemukan {len(event_links)} potensi event di halaman utama.")

        for link_element in event_links:
            detail_url = urljoin(self.base_url, link_element['href'])
            title_preview = link_element.text.strip()
            
            self.logger.info(f"Memulai deep scrape untuk: {title_preview[:50]}...")
            event_data = self._deep_scrape_detail(detail_url)

            if event_data:
                scraped_events.append(event_data)
            else:
                self.logger.warning(f"Gagal mendapatkan detail untuk {title_preview}, melewati.")

        if not scraped_events:
            self.logger.warning("Tidak ada event yang berhasil di-scrape dari halaman utama.")

        return scraped_events

    def _find_organizer(self, post_body):
        """Finds the event organizer, now simplified as complex fallbacks are in data_cleaner."""
        try:
            search_text = post_body.get_text(separator='\n').lower()
            for line in search_text.split('\n'):
                if 'penyelenggara' in line:
                    potential_organizer = line.split('penyelenggara', 1)[1].strip(' :').strip()
                    if potential_organizer and len(potential_organizer) < 70:
                        return potential_organizer
        except Exception:
            pass
        return ''

    def _find_date_raw_text(self, post_body):
        """
        Mencari teks tanggal yang relevan dengan lebih cerdas.
        Fokus pada kalimat pendek yang mengandung kata kunci tanggal.
        """
        date_keywords = ['deadline', 'batas akhir', 'pendaftaran', 'tanggal', 'pelaksanaan']
        text_nodes = post_body.find_all(string=True)
        potential_dates = []

        for node in text_nodes:
            text = node.strip().lower()
            if not text:
                continue

            if any(keyword in text for keyword in date_keywords) and any(char.isdigit() for char in text) and len(text) < 250:
                cleaned_text = ' '.join(node.strip().split())
                potential_dates.append(cleaned_text)

        if not potential_dates:
            self.logger.warning("Tidak dapat menemukan teks tanggal yang spesifik.")
            return ""
        
        return " \n ".join(potential_dates)

    def _find_price_info(self, title, post_body):
        """
        Mencari informasi harga dengan lebih akurat.
        Cek judul dan seluruh isi body untuk kata kunci harga.
        """
        # Jika 'gratis' ada di judul, langsung kembalikan 'Gratis'
        if 'gratis' in title.lower():
            return 'Gratis'
        
        # Kata kunci untuk deteksi harga
        price_keywords = ['gratis', 'free', 'rp', 'idr', 'biaya', 'htj']
        
        text_content = post_body.get_text().lower()
        
        # Jika ada kata kunci harga di body, kembalikan 'Lihat poster'
        # karena detail harga (misal, jumlahnya) perlu dilihat manual.
        if any(keyword in text_content for keyword in price_keywords):
            # Jika kata kuncinya 'gratis', kembalikan 'Gratis'
            if 'gratis' in text_content or 'free' in text_content:
                return 'Gratis'
            return 'Lihat poster'
        
        # Default jika tidak ada kata kunci yang ditemukan
        return 'Lihat poster'

    def _deep_scrape_detail(self, url):
        """Helper function to scrape detailed information from an event page with robust fallback logic."""
        self.logger.info(f"[DEEP SCRAPE] Memproses {url}")
        
        soup = self._fetch_static_page(url)
        if not soup:
            return None

        try:

            post_body = soup.select_one('div.post-body')
            if not post_body:
                self.logger.error(f"[DEEP SCRAPE] Tidak dapat menemukan 'div.post-body' di {url}")
                return None

            title_element = soup.select_one('h1.post-title')
            title = title_element.text.strip() if title_element else 'Tanpa Judul'

            description = post_body.get_text(separator='\n', strip=True)

            poster_img = post_body.select_one('img')
            poster_url = poster_img.get('src') if poster_img else None

            organizer = self._find_organizer(post_body)
            date_raw_text = self._find_date_raw_text(post_body)
            price_info = self._find_price_info(title, post_body)

            # The registration URL is now primarily handled by the fallback logic
            # in data_cleaner.py. We can simplify this to a basic link search.
            registration_url = ''
            for a_tag in post_body.find_all('a', href=True):
                href = a_tag['href']
                if any(keyword in href for keyword in ['bit.ly', 's.id', 'linktr.ee', 'forms.gle']):
                    registration_url = href
                    break


            self.logger.info(f"Berhasil memproses: {title}")
            return {
                'title': title,
                'source_url': url,
                'description': description,
                'date_raw_text': date_raw_text,
                'organizer': organizer,
                'price_info': price_info,
                'poster_url': poster_url,
                'registration_url': registration_url
            }

        except Exception as e:
            self.logger.error(f"[DEEP SCRAPE] Terjadi error tak terduga saat memproses {url}", exc_info=True)
            return None
