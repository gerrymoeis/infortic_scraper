import os
import re
import time
from bs4 import BeautifulSoup
from .base_web_scraper import BaseWebScraper

class InfolombaitScraper(BaseWebScraper):
    def __init__(self, supabase_client, source_name='infolombait.com', debug=False, use_local_cache=False):
        super().__init__(supabase_client, source_name, debug=debug)
        self.base_url = "https://www.infolombait.com/"
        self.use_local_cache = use_local_cache

    def _get_poster_url(self, style_tag):
        """Extracts the poster URL from a style attribute."""
        if not style_tag:
            return None
        match = re.search(r'url\((.*?)\)', style_tag)
        return match.group(1).replace("'", "").replace('"', '') if match else None

    def get_page_content(self, url, cache_filename=None, with_pagination=False):
        """
        Fetches page content using Playwright, with local caching and optional pagination.
        """
        if not cache_filename:
            cache_filename = self.source_name + '_' + url.split('/')[-1]
        
        cache_path = self.get_cache_path(cache_filename)

        if self.use_local_cache and cache_path.exists():
            self.logger.info(f"Using local cache: {cache_path}")
            with open(cache_path, 'r', encoding='utf-8') as f:
                return f.read()

        self.logger.info(f"Fetching live content for {url}")
        if not self.browser:
            self.logger.error("Playwright browser is not running.")
            return None

        page = self.browser.new_page()
        try:
            page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            if with_pagination:
                page_count = 1
                self.logger.info("Starting pagination. Will click 'Load more' until the button disappears.")
                while True:
                    try:
                        # Save a screenshot for debugging pagination
                        screenshot_path = os.path.join(self.debug_dir, f'pagination_debug_page_{page_count}.png')
                        page.screenshot(path=screenshot_path)
                        self.logger.info(f"Saved pagination debug screenshot to: {screenshot_path}")

                        load_more_button = page.locator('a.blog-pager-older-link')
                        self.logger.debug(f"Checking for 'Load more' button on page {page_count}. Found elements: {load_more_button.count()}")

                        # Use a short timeout to quickly check for the button's existence
                        if load_more_button.is_visible(timeout=5000):
                            self.logger.info(f"'Load more' button is visible. Clicking it now.")
                            load_more_button.click()
                            page_count += 1
                            # Wait for network to be idle, indicating new posts have loaded. Increased timeout for safety.
                            page.wait_for_load_state('networkidle', timeout=15000)
                        else:
                            self.logger.info("No more 'Load more posts' button found or it's not visible. Reached the end.")
                            break
                    except Exception as e:
                        self.logger.warning(f"Could not find or click 'Load more posts' button after page {page_count}. Assuming end of pages. Error: {e}")
                        break

            content = page.content()
            
            # Save to cache
            with open(cache_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.info(f"Saved content to cache: {cache_path}")
            
            return content
        except Exception as e:
            self.logger.error(f"Playwright error fetching {url}: {e}", exc_info=True)
            return None
        finally:
            page.close()

    def _parse_main_page(self, soup):
        """Parses the main competition listing page."""
        events = []
        event_containers = soup.select('div.post-outer')
        self.logger.info(f"Found {len(event_containers)} event containers on the main page.")

        for event in event_containers:
            title_element = event.select_one('h2.post-title.entry-title a')
            if not title_element:
                continue

            url = title_element.get('href')
            title = title_element.get_text(strip=True)
            
            summary_element = event.select_one('div.resumo span')
            summary = summary_element.get_text(strip=True) if summary_element else "No summary available."

            poster_element = event.select_one('div.thumb a')
            poster_url = self._get_poster_url(poster_element.get('style')) if poster_element else None
            
            date_element = event.select_one('abbr.published.timeago')
            date_text = date_element.get('title') if date_element else None

            events.append({
                'source_id': self.source_id,
                'url': url,
                'title': title,
                'summary': summary,
                'poster_url': poster_url,
                'deadline': None,
                'registration_url': None,
                'date_text': date_text,
                'participant': None,
                'location': None
            })
        return events

    def _deep_scrape(self, url):
        """Scrapes deadline and registration URL from the event detail page."""
        try:
            page_content = self.get_page_content(url)
            if not page_content:
                return None

            soup = BeautifulSoup(page_content, 'html.parser')
            post_body = soup.select_one('div.post-body.entry-content')

            if not post_body:
                self.logger.warning(f"Could not find post body for {url}")
                return None

            # --- Deadline Extraction (from plain text) ---
            full_text = post_body.get_text(separator='\n', strip=True)
            self.logger.debug(f"Full text for {url}:\n{full_text[:500]}...")
            
            deadline_text = None
            # More specific regex to avoid capturing the event date.
            deadline_match = re.search(r'(?:Batas Pendaftaran|Deadline|Masa Pendaftaran|Masa)\s*:\s*(.*?)\n', full_text, re.IGNORECASE)
            if deadline_match:
                deadline_text = deadline_match.group(1).strip()
                self.logger.info(f"DEADLINE found via regex: '{deadline_text}' for {url}")
            else:
                self.logger.warning(f"Could not find specific deadline text for {url} using regex.")

            # --- Registration URL Extraction (from HTML) ---
            registration_url = None
            # Find all links within the post body
            links = post_body.find_all('a', href=True)
            self.logger.debug(f"Found {len(links)} links in post body for {url}")

            # Prioritize links with registration-related keywords in their text
            for link in links:
                link_text = link.get_text(strip=True).lower()
                if any(keyword in link_text for keyword in ['daftar', 'registrasi', 'pendaftaran', 'register', 'form']):
                    registration_url = link['href']
                    self.logger.info(f"REGISTRATION URL found via keyword in link text: {registration_url}")
                    break
            
            # If not found, look for common shortlinks
            if not registration_url:
                for link in links:
                    if any(shortlink in link['href'] for shortlink in ['bit.ly', 's.id', 'linktr.ee', 'forms.gle', 't.ly']):
                        registration_url = link['href']
                        self.logger.info(f"REGISTRATION URL found via common shortlink: {registration_url}")
                        break
            
            if not registration_url:
                self.logger.error(f"Could not find any registration URL for {url}")

            self.logger.debug(f"Deep scrape for {url} finished. Date Text: '{deadline_text}', Reg URL: {registration_url}")

            return {
                'date_text': deadline_text,
                'registration_url': registration_url
            }
        except Exception as e:
            self.logger.error(f"Error deep scraping {url}: {e}", exc_info=True)
            return None

    def scrape(self):
        """Main scraping logic for infolombait.com."""
        self.logger.info(f"Starting scrape for {self.source_name}. Local cache: {self.use_local_cache}")
        
        # When scraping the main page, enable pagination.
        # The cache filename is updated to reflect it contains multiple pages.
        main_page_content = self.get_page_content(
            self.base_url, 
            cache_filename="main_page_paginated", 
            with_pagination=True
        )
        
        if not main_page_content:
            self.logger.error("Failed to get main page content. Aborting scrape.")
            return []
            
        soup = BeautifulSoup(main_page_content, 'html.parser')
        scraped_events = self._parse_main_page(soup)

        self.logger.info(f"Found {len(scraped_events)} events in total. Starting deep scrape.")
        
        for event in scraped_events:
            self.logger.info(f"Deep scraping: {event['url']}")
            # Deep scrapes do not need pagination
            detail_data = self._deep_scrape(event['url'])
            if detail_data:
                event.update(detail_data)
            # Small delay to be polite to the server
            time.sleep(1) 

        self.logger.info(f"Successfully scraped and processed {len(scraped_events)} events from {self.source_name}.")
        return scraped_events
