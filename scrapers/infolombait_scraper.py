import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup

from .base_web_scraper import BaseWebScraper
from core.data_cleaner import parse_price, parse_dates, clean_title

class InfolombaitScraper(BaseWebScraper):
    def __init__(self, supabase_client, source_name='infolombait.com', debug=False):
        super().__init__(supabase_client, source_name, debug=debug)
        self.base_url = "https://www.infolombait.com/"

    def scrape(self):
        self.logger.info(f'Starting scrape for {self.source_name}')
        
        soup = self._fetch_dynamic_page(self.base_url, selector_to_wait='.post h2 a')
        if not soup:
            return []
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
        soup = self._fetch_static_page(url)
        if not soup:
            return None

        try:
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
            time_tag = soup.select_one('abbr.timeago')
            if time_tag and time_tag.has_attr('title'):
                self.logger.info(f"Found <abbr> tag for {url}. Attempting to parse.")
                try:
                    date_aware = datetime.fromisoformat(time_tag['title'])
                    date_utc = date_aware.astimezone(timezone.utc)
                    date_data['deadline'] = date_utc
                    date_data['event_date_start'] = date_utc
                    self.logger.info(f"Successfully parsed date from <abbr>: {date_utc}")
                except (ValueError, KeyError):
                    self.logger.error(f"Failed to parse date from <abbr> title: {time_tag.get('title')}")

            if not date_data.get('deadline'):
                self.logger.warning(f"Failed to get date from <abbr> for {url}. Falling back to description parsing.")
                date_data = parse_dates(description)

            price_data = parse_price(description)
            
            registration_url_match = re.search(r'(?:link pendaftaran|registrasi|daftar di|informasi lebih lanjut|selengkapnya|official account|website)[^\n]*?(https?://[\S]+)', description, re.IGNORECASE)
            registration_url = None
            if registration_url_match:
                registration_url = registration_url_match.group(1).strip('.,')
            else:
                fallback_match = re.search(r'https?://[\S]+', description)
                if fallback_match:
                    registration_url = fallback_match.group(0).strip('.,')

            if not registration_url:
                self.logger.warning(f"Could not find registration URL for {url}. Skipping.")
                return None

            event_data = {
                'title': title,
                'source_url': url,
                'description': description,
                'poster_url': poster_url,
                'organizer': None,
                'registration_url': registration_url,
                **date_data,
                **price_data,
            }
            
            self.logger.info(f"Successfully processed: {title}")
            return event_data

        except Exception as e:
            self.logger.error(f"Error deep scraping {url}: {e}", exc_info=True)
            return None

