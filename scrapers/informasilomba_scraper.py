import requests
import logging
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from .base_scraper import BaseScraper

class InformasilombaScraper(BaseScraper):
    def __init__(self, supabase_client, source_name='informasilomba.com'):
        super().__init__(supabase_client, source_name)
        self.base_url = "https://www.informasilomba.com/"

    def scrape(self):
        """Scrapes event data from informasilomba.com."""
        self.logger.info(f"Mengambil data dari {self.base_url}")
        scraped_events = []

        try:
            response = requests.get(self.base_url, timeout=20)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f"Gagal mengambil halaman utama {self.base_url}: {e}")
            return scraped_events

        soup = BeautifulSoup(response.text, 'html.parser')
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
        """
        Mencoba menemukan penyelenggara acara dengan beberapa metode fallback yang lebih andal.
        1. Mencari link profil Instagram (bukan post/reel) di seluruh body.
        2. Jika tidak ada, mencari mention Instagram (@username) dalam teks.
        3. Jika masih tidak ada, mencari teks eksplisit seperti "Penyelenggara:".
        """
        self.logger.debug("Memulai pencarian penyelenggara dengan metode baru...")

        for a_tag in post_body.find_all('a', href=True):
            href = a_tag.get('href', '')
            match = re.search(r"instagram\.com/(?!p/|reel/|explore/|stories/)([a-zA-Z0-9._]{3,30})/?$", href)
            if match:
                username = match.group(1)
                if '.' not in username.split('/')[-1]: 
                    self.logger.info(f"Menemukan penyelenggara dari link profil Instagram: {username}")
                    return username

        text_content = post_body.get_text()
        mention_match = re.search(r'(?<!\w)@([a-zA-Z0-9_](?:[a-zA-Z0-9_.]*[a-zA-Z0-9_])?)', text_content)
        if mention_match:
            username = mention_match.group(1)
            if 3 <= len(username) <= 30 and '.' not in username:
                self.logger.info(f"Menemukan penyelenggara dari mention Instagram: @{username}")
                return username

        try:
            search_text = post_body.get_text(separator='\n').lower()
            for line in search_text.split('\n'):
                if 'penyelenggara' in line:
                    potential_organizer = line.split('penyelenggara', 1)[1].strip(' :').strip()
                    if potential_organizer and len(potential_organizer) < 70:
                        self.logger.info(f"Menemukan kandidat penyelenggara dari teks: '{potential_organizer}'")
                        return potential_organizer
        except Exception:
            pass

        self.logger.warning("Tidak dapat menemukan penyelenggara dengan metode yang ada.")
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
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        try:
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

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

            excluded_domains = ['google.com', 'facebook.com', 'twitter.com/share', 'linkedin.com/share', 'wa.me', 't.me', 'line.me', 'blogger.com', 'informasilomba.com', 'blogger.googleusercontent.com']
            priority_keywords = ['pendaftaran', 'registrasi', 'form', 'bit.ly', 's.id', 'linktr.ee', 'daftar']
            
            potential_links = []
            for a_tag in post_body.find_all('a', href=True):
                href = a_tag['href']
                if not any(domain in href for domain in excluded_domains):
                    potential_links.append(href)

            registration_url = ''
            first_ig_profile_link = ''

            for href in potential_links:
                if 'instagram.com/' in href and '/p/' not in href and '/reel/' not in href:
                    if not first_ig_profile_link:
                        if re.search(r"instagram\.com/(?!p/|reel/|explore/|stories/)([a-zA-Z0-9._]{3,30})/?$", href):
                            first_ig_profile_link = href

            if not organizer and first_ig_profile_link:
                match = re.search(r"instagram\.com/([a-zA-Z0-9._]+)", first_ig_profile_link)
                if match:
                    username = match.group(1).replace('/', '')
                    if len(username) > 2:
                        organizer = username
                        self.logger.info(f"Menemukan penyelenggara dari link profil Instagram: {organizer}")

            for link in potential_links:
                if any(keyword in link.lower() for keyword in priority_keywords):
                    registration_url = link
                    self.logger.info(f"Menemukan link prioritas: {registration_url}")
                    break

            if not registration_url:
                if first_ig_profile_link:
                    registration_url = first_ig_profile_link
                    self.logger.info("Link prioritas tidak ditemukan, fallback ke link profil IG pertama.")
                elif organizer:
                    clean_organizer = organizer.replace('@', '').strip()
                    registration_url = f"https://www.instagram.com/{clean_organizer}"
                    self.logger.info("Link prioritas/profil IG tidak ditemukan, fallback ke IG dari @mention.")
                else:
                    for link in potential_links:
                        if 'instagram.com/p/' not in link and 'instagram.com/reel/' not in link:
                            registration_url = link
                            self.logger.info(f"Tidak ada link prioritas/IG, menggunakan link potensial valid pertama: {registration_url}")
                            break

            if organizer:
                organizer = organizer.replace('@', '').strip()

            self.logger.info(f"Berhasil memproses: {title}")
            return {
                'title': title,
                'url': url,
                'description': description,
                'date_raw_text': date_raw_text,
                'organizer': organizer,
                'price_info': price_info,
                'poster_url': poster_url,
                'registration_url': registration_url
            }

        except requests.RequestException as e:
            self.logger.error(f"[DEEP SCRAPE] Gagal mengambil {url}", exc_info=True)
            return None
        except Exception as e:
            self.logger.error(f"[DEEP SCRAPE] Terjadi error tak terduga saat memproses {url}", exc_info=True)
            return None
