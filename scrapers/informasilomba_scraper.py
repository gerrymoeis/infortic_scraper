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
        
        self.logger.info(f"Selesai scrape dari {self.source_name}, mendapatkan {len(scraped_events)} kompetisi mentah.")
        return scraped_events

    def _find_organizer(self, description_text):
        """Finds the event organizer from the description text."""
        try:
            search_text = description_text.lower()
            for line in search_text.splitlines():
                if 'penyelenggara' in line:
                    potential_organizer = line.split('penyelenggara', 1)[1].strip(' :').strip()
                    if potential_organizer and len(potential_organizer) < 70:
                        return potential_organizer.title()
        except Exception:
            pass
        return ''

    def _find_price_info(self, title, description_text):
        """
        Searches for price information more accurately.
        Checks title and the entire body for price-related keywords.
        """
        if 'gratis' in title.lower():
            return 'Gratis'
        
        price_keywords = ['gratis', 'free', 'tanpa dipungut biaya']
        text_content = description_text.lower()

        if any(keyword in text_content for keyword in price_keywords):
            return 'Gratis'
        return 'Lihat poster'

    def _find_registration_link(self, container):
        """Finds the most likely registration link within a container element."""
        keywords = ['pendaftaran', 'registrasi', 'daftar', 'form', 'bit.ly', 'submit', 'submission']
        all_links = container.find_all('a', href=True)
        
        potential_links = []
        for link in all_links:
            href = link['href']
            link_text = link.get_text().lower()
            
            if 'informasilomba.com' in href or href.startswith('#') or 'blogger.googleusercontent.com' in href:
                continue

            if any(keyword in link_text for keyword in keywords) or any(keyword in href for keyword in keywords):
                self.logger.info(f"Found potential registration link by keyword: {href}")
                potential_links.append(href)

        if potential_links:
            return potential_links[0]

        for link in all_links:
            href = link['href']
            if 'informasilomba.com' not in href and not href.startswith('#') and 'blogger.googleusercontent.com' not in href:
                self.logger.info(f"Using fallback registration link (first external): {href}")
                return href

        self.logger.warning("No registration link found.")
        return ''

    def _parse_deadline_from_text(self, text):
        """More robust deadline parsing."""
        sentences = text.lower().split('.')
        deadline_keywords = ['deadline', 'pendaftaran', 'batas akhir', 'timeline', 'pengumpulan']
        
        for sentence in sentences:
            if any(keyword in sentence for keyword in deadline_keywords):
                date_match = re.search(r'(\d{1,2}\s+(?:januari|februari|maret|april|mei|juni|juli|agustus|september|oktober|november|desember)\s+\d{4})', sentence, re.I)
                if date_match:
                    self.logger.info(f"Found deadline '{date_match.group(1)}' in sentence: '{sentence[:100]}...'" )
                    return date_match.group(1)

        self.logger.warning("Could not find a specific deadline date in the text.")
        return ''

    def _parse_detail_page(self, url):
        """Parses the detail page to extract core event information."""
        soup = self._fetch_static_page(url)
        if not soup:
            return None

        title_element = soup.find('h1', class_='post-title')
        title = title_element.get_text(strip=True) if title_element else 'No title found'

        description_element = soup.find('div', class_='post-body')
        if not description_element:
            self.logger.error(f"Could not find 'div.post-body' in {url}")
            return None

        description_text = description_element.get_text(strip=True)

        # 1. Find Poster URL
        poster_url = ''
        poster_div = description_element.find('div', class_='separator')
        if poster_div and poster_div.find('img'):
            poster_url = poster_div.find('img')['src']
        
        if not poster_url:
            og_image = soup.find('meta', property='og:image')
            if og_image and og_image.get('content'):
                poster_url = og_image['content']
                self.logger.info("Found poster via og:image tag.")

        # 2. Find Deadline
        date_text = self._parse_deadline_from_text(description_text)

        # 3. Find Registration URL
        registration_url = self._find_registration_link(description_element)

        return {
            'title': title,
            'description': description_text,
            'poster_url': poster_url,
            'registration_url': registration_url,
            'deadline': date_text,
            'source_url': url
        }

    def _deep_scrape_detail(self, url):
        """Helper function to scrape and enrich detailed information from an event page."""
        self.logger.info(f"[DEEP SCRAPE] Memproses {url}")
        
        event_data = self._parse_detail_page(url)

        if event_data:
            organizer = self._find_organizer(event_data['description'])
            price_info = self._find_price_info(event_data['title'], event_data['description'])

            event_data['organizer'] = organizer
            event_data['price_info'] = price_info

            self.logger.info(f"Berhasil memproses: {event_data['title']}")
            return event_data

        self.logger.error(f"[DEEP SCRAPE] Gagal memproses {url}")
        return None
