import os
import time
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import dateparser
from scrapers.base_scraper import BaseScraper
from core.data_cleaner import extract_title_from_caption

class InstagramPlaywrightScraper(BaseScraper):
    def __init__(self, target_account, debug=False):
        super().__init__(debug=debug)
        self.target_account = target_account
        self.auth_file = 'auth/instagram_auth_state.json'
        self.log_dir = 'logs'  # Define log_dir for debug artifacts
        self.logger.info(f"InstagramPlaywrightScraper initialized for '{self.target_account}' (Debug: {self.debug}).")

    def scrape(self):
        self.logger.info("Starting Instagram scrape with Playwright.")

        if not os.path.exists(self.auth_file):
            self.logger.error(f"Authentication file not found at '{self.auth_file}'.")
            self.logger.error("Please run 'python setup_instagram_session.py' to log in and create the auth file.")
            return []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False) # Headless=False for debugging
            context = browser.new_context(
                storage_state=self.auth_file,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            target_account = self.target_account
            self.logger.info(f"Navigating to {target_account}'s profile.")
            page.goto(f"https://www.instagram.com/{target_account}/")

            try:
                self.logger.info("Waiting for profile header to load...")
                page.wait_for_selector("header h2", timeout=15000)
                self.logger.info("Profile header loaded.")

                # Scroll a few times to load initial posts
                self.logger.info("Scrolling down to trigger post loading...")
                for i in range(3):
                    page.mouse.wheel(0, 1500)
                    self.logger.info(f"Scroll attempt {i+1}/3, waiting for content...")
                    time.sleep(3)

                # Use BeautifulSoup to find posts
                html_content = page.content()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                post_selector = f'a[href^="/{target_account}/p/"]'
                post_links = soup.select(post_selector)

                if not post_links:
                    raise Exception("No post links found with BeautifulSoup. Account might be private or the UI has changed.")
                
                self.logger.info(f"Post grid found with BeautifulSoup. Found {len(post_links)} initial posts. Proceeding with scrape.")

            except Exception as e:
                self.logger.warning(f"Could not find post grid for '{target_account}'. Error: {e}")
                # Save screenshot and HTML for debugging
                screenshot_path = os.path.join(self.log_dir, f"instagram_profile_failed_{target_account}.png")
                html_path = os.path.join(self.log_dir, f"instagram_profile_failed_{target_account}.html")
                page.screenshot(path=screenshot_path)
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(page.content())
                self.logger.info(f"Saved screenshot to {screenshot_path} and HTML to {html_path}")
                browser.close()
                return []

            self.logger.info("Scrolling to load all posts and collecting URLs with BeautifulSoup...")
            post_urls = set()
            scroll_attempts = 0
            max_scroll_attempts = 10

            while scroll_attempts < max_scroll_attempts:
                html_content = page.content()
                soup = BeautifulSoup(html_content, 'html.parser')
                
                new_links = soup.select(post_selector)
                
                current_urls = set()
                for link in new_links:
                    href = link.get('href')
                    if href:
                        current_urls.add(f"https://www.instagram.com{href}")

                newly_found_urls = current_urls - post_urls
                if newly_found_urls:
                    self.logger.info(f"Found {len(newly_found_urls)} new post URLs. Total unique URLs: {len(post_urls.union(current_urls))}")
                    post_urls.update(current_urls)
                else:
                    self.logger.info("No new posts found on this scroll. Assuming end of page.")
                    break

                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                self.logger.debug(f"Scrolling down... Attempt {scroll_attempts + 1}/{max_scroll_attempts}")
                time.sleep(3)
                
                scroll_attempts += 1
                if scroll_attempts >= max_scroll_attempts:
                    self.logger.warning("Reached max scroll attempts.")

            self.logger.info(f"Finished scrolling. Collected {len(post_urls)} unique post URLs.")

            if self.debug:
                urls_log_path = os.path.join(self.log_dir, f"instagram_urls_{target_account}.txt")
                with open(urls_log_path, "w", encoding="utf-8") as f:
                    for url in sorted(list(post_urls)):
                        f.write(f"{url}\n")
                self.logger.info(f"Saved collected URLs to {urls_log_path}")

            competitions = []
            urls_to_process = sorted(list(post_urls), reverse=True)[:5] if self.debug else sorted(list(post_urls), reverse=True)[:30]

            for url in urls_to_process:
                self.logger.info(f"Scraping post: {url}")
                try:
                    page.goto(url, wait_until='load', timeout=30000)
                    
                    article_selector = "article"
                    page.wait_for_selector(article_selector, timeout=15000)
                    self.logger.info("Article element loaded.")
                    
                    caption_selector = "article h1"
                    page.wait_for_selector(caption_selector, timeout=10000)
                    caption_element = page.locator(caption_selector)
                    
                    caption_text = ""
                    if caption_element.count() > 0:
                        caption_text = caption_element.first.inner_text()
                        self.logger.info(f"Found caption for {url}")
                    else:
                        self.logger.warning(f"Caption element not found for {url}")

                    # Use the advanced title extractor from the data cleaner
                    extracted_title = extract_title_from_caption(caption_text)

                    # Extract poster URL
                    poster_url = ""
                    poster_selector = "article img[srcset]"
                    poster_element = page.locator(poster_selector).first
                    if poster_element.count() > 0:
                        poster_url = poster_element.get_attribute('src')
                        self.logger.info(f"Found poster for {url}")
                    else:
                        self.logger.warning(f"Poster element not found for {url}")

                    # Extract post timestamp as a fallback
                    post_timestamp = None
                    time_selector = "article time"
                    time_element = page.locator(time_selector).first
                    if time_element.count() > 0:
                        datetime_str = time_element.get_attribute('datetime')
                        if datetime_str:
                            post_timestamp = dateparser.parse(datetime_str)
                            self.logger.info(f"Found post timestamp for {url}: {post_timestamp}")
                    else:
                        self.logger.warning(f"Timestamp element not found for {url}")

                    competition_data = {
                        'title': extracted_title,
                        'url': url,
                        'description': caption_text,
                        'poster_url': poster_url,
                        'date_text': caption_text,  # Provide caption for deadline parsing
                        'event_date_start': post_timestamp,  # Provide the post date as a fallback
                    }
                    competitions.append(competition_data)

                except Exception as e:
                    self.logger.error(f"Failed to scrape post {url}: {e}")
                    screenshot_path = os.path.join(self.log_dir, f"instagram_post_failed_{url.split('/')[-2]}.png")
                    page.screenshot(path=screenshot_path)
                    self.logger.info(f"Saved screenshot for failed post to {screenshot_path}")

            self.logger.info("Scraping finished.")
            browser.close()
            
            return competitions
