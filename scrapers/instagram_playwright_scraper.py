import os
import time
from playwright.sync_api import sync_playwright
from scrapers.base_scraper import BaseScraper

class InstagramPlaywrightScraper(BaseScraper):
    def __init__(self, source_id, source_name="instagram.com", debug=False, log_dir="logs"):
        super().__init__(source_id, source_name, debug, log_dir)

        username = os.getenv("INSTAGRAM_USERNAME")
        password = os.getenv("INSTAGRAM_PASSWORD")

        self.username = "csrelatedcompetitions"
        self.auth_file = 'auth/instagram_auth_state.json'
        self.logger.info(f"Scraper for {self.source_name} initialized (Debug: {self.debug}).")

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

            target_account = self.username
            self.logger.info(f"Navigating to {target_account}'s profile.")
            page.goto(f"https://www.instagram.com/{target_account}/")

            try:
                self.logger.info("Waiting for profile header to load...")
                page.wait_for_selector("header h2", timeout=15000)
                self.logger.info("Profile header loaded.")

                # Give the page a moment and try a gentle scroll to trigger lazy-loading
                self.logger.info("Performing a gentle scroll to encourage post grid to load...")
                time.sleep(2) # Brief pause
                page.mouse.wheel(0, 500) # Scroll down slightly
                time.sleep(2) # Wait for content to potentially load

                # New strategy: Check for the post grid directly with a longer timeout.
                self.logger.info("Checking for post grid to determine if account is public...")
                page.wait_for_selector("a[href^='/p/']", timeout=20000) # Use a more generic selector for any post link
                self.logger.info("Post grid found. Account is public, proceeding with scrape.")

            except Exception as e:
                # This exception will likely be a TimeoutError if the post grid isn't found.
                self.logger.warning(f"Could not find post grid for '{target_account}'. The account is likely private or restricted. Error: {e}")
                # Save screenshot and HTML for debugging
                screenshot_path = os.path.join(self.log_dir, f"instagram_profile_failed_{target_account}.png")
                html_path = os.path.join(self.log_dir, f"instagram_profile_failed_{target_account}.html")
                main_html_path = os.path.join(self.log_dir, f"instagram_profile_failed_{target_account}_main.html")

                page.screenshot(path=screenshot_path)
                
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(page.content())
                
                # Try to get the HTML of the main element for more focused debugging
                try:
                    main_element = page.locator("main")
                    if main_element.count() > 0:
                        main_html = main_element.inner_html()
                        with open(main_html_path, "w", encoding="utf-8") as f:
                            f.write(main_html)
                        self.logger.info(f"Saved main element HTML to {main_html_path}")
                    else:
                        self.logger.warning("Could not find main element on the page.")
                except Exception as e:
                    self.logger.error(f"Could not get main element HTML: {e}")

                self.logger.info(f"Saved screenshot to {screenshot_path}")
                self.logger.info(f"Saved HTML to {html_path}")
                browser.close()
                return []

            self.logger.info("Scrolling to load all posts and collecting URLs...")
            post_urls = set()
            scroll_attempts = 0
            max_scroll_attempts = 50  # Avoid infinite loops

            while scroll_attempts < max_scroll_attempts:
                # Extract links visible on the page
                new_links = page.query_selector_all("a[href^='/p/']")
                
                current_urls = set()
                for link in new_links:
                    href = link.get_attribute('href')
                    if href:
                        current_urls.add(f"https://www.instagram.com{href}")

                if not post_urls.issuperset(current_urls):
                    new_count = len(current_urls - post_urls)
                    self.logger.info(f"Found {new_count} new post URLs. Total unique URLs: {len(post_urls.union(current_urls))}")
                    post_urls.update(current_urls)
                else:
                    self.logger.info("No new posts found on this scroll. Assuming end of page.")
                    break

                # Scroll down
                page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                self.logger.debug(f"Scrolling down... Attempt {scroll_attempts + 1}/{max_scroll_attempts}")
                time.sleep(3)  # Wait for new posts to load
                
                scroll_attempts += 1
                if scroll_attempts >= max_scroll_attempts:
                    self.logger.warning("Reached max scroll attempts.")

            self.logger.info(f"Finished scrolling. Collected {len(post_urls)} unique post URLs.")
            
            # For now, just log the URLs for debugging
            if self.debug:
                urls_log_path = os.path.join(self.log_dir, f"instagram_urls_{target_account}.txt")
                with open(urls_log_path, "w", encoding="utf-8") as f:
                    for url in sorted(list(post_urls)):
                        f.write(f"{url}\n")
                self.logger.info(f"Saved collected URLs to {urls_log_path}")
            
            self.logger.info("Scraping finished.")
            browser.close()

            # In the next phase, we will process these URLs. For now, return an empty list.
            return []
