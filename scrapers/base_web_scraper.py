import os
import re
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, Page, Browser, TimeoutError as PlaywrightTimeoutError

from .base_scraper import BaseScraper

class BaseWebScraper(BaseScraper):
    """A base class for web scrapers that manages a Playwright browser instance."""

    def __init__(self, supabase_client, source_name, debug=False):
        super().__init__(supabase_client, source_name)
        self.debug = debug
        self.debug_dir = 'debug_output'
        self.cache_dir = 'local_cache'
        self.playwright = None
        self.browser = None
        if self.debug:
            os.makedirs(self.debug_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

    def __enter__(self):
        """Starts Playwright and launches the browser, making this a context manager."""
        self.logger.info("Starting Playwright browser...")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=True)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stops Playwright and closes the browser."""
        self.logger.info("Closing Playwright browser...")
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def get_page(self, url: str) -> Page | None:
        """Creates a new page in the browser and navigates to the URL."""
        if not self.browser:
            self.logger.error("Browser is not running. Call this method within a 'with' block.")
            return None
        
        page = self.browser.new_page()
        try:
            self.logger.info(f"Navigating to {url}")
            page.goto(url, timeout=60000, wait_until='domcontentloaded')
            return page
        except Exception as e:
            self.logger.error(f"Failed to get page {url}: {e}")
            page.close()
            return None

    def save_debug_page(self, page: Page, page_name="page"):
        """Saves the page's HTML content to a debug file."""
        if not self.debug:
            return
        
        sanitized_page_name = re.sub(r'https?://(www\.)?', '', page_name)
        sanitized_page_name = re.sub(r'[\\/:*?"<>|]', '_', sanitized_page_name).replace('.html', '')
        filename = f"{self.source_name}_{sanitized_page_name}.html"
        if len(filename) > 250:
            filename = filename[:245] + ".html"

        filepath = os.path.join(self.debug_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(page.content())
            self.logger.info(f"Debug HTML saved to {filepath}")
        except Exception as e:
            self.logger.error(f"Failed to save debug HTML to {filepath}: {e}")

    def get_cache_path(self, filename: str) -> Path:
        """Constructs the full path for a cache file."""
        return Path(self.cache_dir) / filename

    def _fetch_static_page(self, url):
        """Fetches a static web page using requests and returns BeautifulSoup."""
        self.logger.info(f"Fetching static page: {url}")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            if self.debug:
                self.save_debug_page(response.text, page_name=url) # Note: this is text, not a page object
            return BeautifulSoup(response.content, 'html.parser')
        except requests.RequestException as e:
            self.logger.error(f"Failed to fetch static page {url}: {e}")
            return None
