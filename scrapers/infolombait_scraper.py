import requests
import re
import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime, timezone
from .base_scraper import BaseScraper
from core.data_cleaner import clean_event_data, parse_price, parse_dates, clean_title

class InfolombaitScraper(BaseScraper):
    def __init__(self, supabase_client, source_name='infolombait.com'):
        super().__init__(supabase_client, source_name)
        self.base_url = "https://www.infolombait.com/"

    def scrape(self):
        self.logger.info(f'Starting scrape for {self.source_name}')
        
        html_content = None
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                self.logger.info(f"Navigating to {self.base_url} with Playwright.")
                page.goto(self.base_url, timeout=60000)
                
                self.logger.info("Waiting for article selector '.post h2 a' to appear...")
                page.wait_for_selector('.post h2 a', timeout=30000)
                
                html_content = page.content()
                self.logger.info("Successfully fetched dynamic content.")

            except PlaywrightTimeoutError:
                self.logger.error(f"Timeout waiting for selector '.post h2 a' on {self.base_url}. The page structure might have changed.")
                html_content = page.content() # Save what we have for debugging
            except Exception as e:
                self.logger.error(f"An error occurred with Playwright: {e}")
                return []
            finally:
                browser.close()

        if not html_content:
            self.logger.error("Failed to retrieve HTML content using Playwright.")
            return []

        # Save the HTML for debugging in the correct directory
        debug_dir = "debug_output"
        os.makedirs(debug_dir, exist_ok=True)
        html_filename = os.path.join(debug_dir, "infolombait_homepage.html")
        with open(html_filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        self.logger.info(f"Homepage HTML saved to {html_filename} for debugging.")

        soup = BeautifulSoup(html_content, 'html.parser')
        events = []
        
        article_links = soup.select('.post h2 a')
        self.logger.info(f"Found {len(article_links)} article links on the main page using selector '.post h2 a'.")

        if not article_links:
            self.logger.warning("Could not find any article links with the new selector. Please inspect 'debug_output/infolombait_homepage.html'.")
            return []

        for link in article_links:
            url = link.get('href')
            if url and url.startswith('http'):
                event_detail = self._deep_scrape_detail(url)
                if event_detail:
                    events.append(event_detail)

        self.logger.info(f"Successfully scraped {len(events)} detailed events from {self.source_name}")
        return events

    def _deep_scrape_detail(self, url):
        self.logger.info(f"[DEEP SCRAPE] Processing {url}")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.RequestException as e:
            self.logger.error(f'Failed to fetch detail page {url}: {e}')
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        title_element = soup.select_one('h1.post-title')
        if not title_element:
            self.logger.warning(f"Could not find title for {url}")
            return None
        title = clean_title(title_element.get_text(strip=True))

        post_body = soup.select_one('div.post-body')
        if not post_body:
            self.logger.warning(f'Could not find post body for {url}')
            return None

        description = post_body.get_text(separator='\n', strip=True)

        poster_url = None
        poster_img = post_body.select_one('img')
        if poster_img:
            poster_url = poster_img.get('src')

        date_data = {}
        # Prioritaskan parsing dari <abbr> tag karena lebih andal
        time_tag = soup.select_one('abbr.timeago')
        if time_tag and time_tag.has_attr('title'):
            self.logger.info(f"Menemukan tag <abbr> untuk {url}. Mencoba parsing.")
            try:
                date_aware = datetime.fromisoformat(time_tag['title'])
                date_utc = date_aware.astimezone(timezone.utc)
                date_data['deadline'] = date_utc
                date_data['event_date_start'] = date_utc
                self.logger.info(f"Berhasil mem-parsing tanggal dari <abbr>: {date_utc}")
            except (ValueError, KeyError):
                self.logger.error(f"Gagal mem-parsing tanggal dari <abbr> title: {time_tag.get('title')}")

        # Fallback: jika <abbr> gagal, coba parse dari deskripsi
        if not date_data.get('deadline'):
            self.logger.warning(f"Gagal mendapatkan tanggal dari <abbr> untuk {url}. Fallback ke parsing deskripsi.")
            date_data = parse_dates(description)

        price_data = parse_price(description)
        
        organizer = self._find_organizer(post_body)
        registration_url = self._find_registration_url(post_body, url)

        event_data = {
            'title': title,
            'url': url,
            'description': description,
            'poster_url': poster_url,
            'organizer': organizer,
            'registration_url': registration_url,
            **date_data,
            **price_data,
        }
        
        self.logger.info(f"Successfully processed: {title}")
        return event_data

    def _find_organizer(self, soup_element):
        for a in soup_element.select('a[href*="instagram.com"]'):
            href = a.get('href', '')
            if 'instagram.com/' in href:
                try:
                    handle = href.split('instagram.com/')[1].split('/')[0].split('?')[0]
                    if handle:
                        self.logger.info(f"Found organizer from Instagram link: @{handle}")
                        return f"@{handle}"
                except IndexError:
                    continue
        self.logger.warning("Could not find organizer from Instagram link.")
        return None

    def _find_registration_url(self, soup_element, original_url):
        excluded_domains = ['google.com', 'facebook.com', 'twitter.com', 'linkedin.com', 'wa.me', 't.me', 'line.me', 'blogger.com', 'infolombait.com', 'blogger.googleusercontent.com', 'instagram.com']
        priority_keywords = ['pendaftaran', 'registrasi', 'form', 'bit.ly', 's.id', 'linktr.ee', 'daftar']
        
        all_links = soup_element.select('a')
        
        for link in all_links:
            href = link.get('href')
            text = link.get_text(strip=True).lower()
            if href and any(keyword in href for keyword in priority_keywords) or any(keyword in text for keyword in priority_keywords):
                if not any(domain in href for domain in excluded_domains):
                    self.logger.info(f"Found priority registration link: {href}")
                    return href
        
        for link in all_links:
            href = link.get('href')
            if href and href.startswith('http') and not any(domain in href for domain in excluded_domains):
                 self.logger.info(f"Using fallback registration link: {href}")
                 return href

        self.logger.warning(f"No valid registration link found for {original_url}. Returning original URL as fallback.")
        return original_url
