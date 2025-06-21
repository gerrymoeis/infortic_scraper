import os
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from datetime import datetime

from .base_scraper import BaseScraper

class BaseWebScraper(BaseScraper):
    """A base class for scrapers that fetch data from websites."""

    def __init__(self, supabase_client, source_name, debug=False):
        super().__init__(supabase_client, source_name)
        self.debug = debug
        self.debug_dir = 'debug_output'
        if self.debug:
            os.makedirs(self.debug_dir, exist_ok=True)

    def _save_debug_html(self, content, page_name="page"):
        if not self.debug:
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{self.source_name}_{page_name}_{timestamp}.html"
        filepath = os.path.join(self.debug_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            self.logger.info(f"Debug HTML saved to {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to save debug HTML to {filepath}: {e}")

    def _fetch_static_page(self, url):
        """Fetches a static web page using requests."""
        self.logger.info(f"Fetching static page: {url}")
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            self._save_debug_html(response.text, page_name=url.replace('/', '_'))
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch static page {url}: {e}")
            return None

    def _fetch_dynamic_page(self, url, selector_to_wait):
        """Fetches a dynamic web page using Playwright."""
        self.logger.info(f"Fetching dynamic page: {url}")
        html_content = None
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, timeout=60000)
                page.wait_for_selector(selector_to_wait, timeout=30000)
                html_content = page.content()
                self.logger.info(f"Successfully fetched dynamic content from {url}.")
            except PlaywrightTimeoutError:
                self.logger.error(f"Timeout waiting for selector '{selector_to_wait}' on {url}.")
                html_content = page.content() # Save what we have for debugging
            except Exception as e:
                self.logger.error(f"An error occurred with Playwright at {url}: {e}")
            finally:
                browser.close()

        if not html_content:
            self.logger.error(f"Failed to retrieve HTML content from {url}.")
            return None

        self._save_debug_html(html_content, page_name=url.replace('/', '_'))
        return BeautifulSoup(html_content, 'html.parser')
