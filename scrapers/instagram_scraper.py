import logging
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from instagrapi import Client
import re

from scrapers.base_scraper import BaseScraper
from core.data_cleaner import parse_dates, clean_title, extract_title_from_caption

# Load environment variables at the module level
load_dotenv()

class InstagramScraper(BaseScraper):
    ACCOUNT_EVENT_TYPE_MAPPING = {
        'csrelatedcompetitions': 'Lomba',
        'infolombaevent.id': 'Lomba',
        'anakmagang.id': 'Magang',
        'maganghub': 'Magang',
        'beasiswa.co': 'Beasiswa',
    }
    """Scraper for fetching event data from Instagram accounts."""

    def __init__(self, supabase_client, source_name='instagram', debug=False):
        super().__init__(supabase_client, source_name, debug=debug)
        self.cl = Client()
        self.target_accounts = [
            'csrelatedcompetitions',
            'infolombaevent.id',
            'anakmagang.id',
            'maganghub',
            'beasiswa.co'
        ]
        self.session_file = Path("session.json")
        self.debug_output_path = Path("debug_output")
        self.debug_output_path.mkdir(exist_ok=True)

    def _login(self):
        """Logs into Instagram, using a saved session if available."""
        username = os.getenv('INSTAGRAM_USERNAME')
        password = os.getenv('INSTAGRAM_PASSWORD')

        if not username or not password:
            self.logger.error("INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD must be set in .env file.")
            return False

        try:
            if self.session_file.exists():
                self.logger.info(f"Found session file, loading settings from {self.session_file}")
                self.cl.load_settings(self.session_file)
                self.logger.info("Attempting to log in with saved session...")
                self.cl.login(username, password)
                self.logger.info("Login with session successful.")
            else:
                self.logger.info("No session file found, performing a new login.")
                self.cl.login(username, password)
                self.logger.info("New login successful.")
                self.cl.dump_settings(self.session_file)
                self.logger.info(f"New session saved to {self.session_file}")
        except Exception as e:
            self.logger.error(f"Instagram login failed: {e}", exc_info=True)
            if self.session_file.exists():
                self.logger.warning(f"Removing potentially corrupt session file: {self.session_file}")
                os.remove(self.session_file)
            return False
            
        return True

    def _parse_single_post(self, post_data):
        """Extracts event information from a single Instagram post dictionary."""
        caption = post_data.get('caption_text', '')
        if not caption:
            return None

        source_username = post_data.get('user', {}).get('username', '')
        post_code = post_data.get('code', '')

        # Basic Information
        title = extract_title_from_caption(caption)
        description = caption.strip()
        image_url = post_data.get('image_versions2', {}).get('candidates', [{}])[0].get('url', '')
        source_url = f"https://www.instagram.com/p/{post_code}/" if post_code else ''
        event_type = self.ACCOUNT_EVENT_TYPE_MAPPING.get(source_username, 'Lainnya')

        # Find Registration URL - prioritize links with registration keywords or common shorteners
        # This regex looks for common registration keywords followed by a URL.
        reg_link_pattern = r'(?:pendaftaran|registrasi|daftar|form|bit\.ly|s\.id|t\.ly)[^\n]*?(https?://[\S]+)'
        url_match = re.search(reg_link_pattern, caption, re.IGNORECASE)
        
        if url_match:
            registration_url = url_match.group(1).strip('.,')
        else:
            # Fallback to the first URL if no registration keyword is found
            url_match = re.search(r'https?://[\S]+', caption)
            registration_url = url_match.group(0).strip('.,') if url_match else ''

        # Date Parsing
        deadline_date, start_date, end_date = parse_dates(caption)

        # Ensure we have a title, a registration URL, and a potential date
        if not registration_url:
            self.logger.warning(f"No registration URL found for post {source_url}. Skipping.")
            return None

        if not title or not (deadline_date or start_date or end_date):
            if self.debug:
                self.logger.debug(f"Skipping post from {source_username} due to missing title or dates. Title: '{title}'")
            return None

        return {
            'title': title,
            'description': description,
            'registration_deadline': deadline_date,
            'event_start': start_date,
            'event_end': end_date,
            'event_type': event_type,
            'image_url': image_url,
            'source_url': source_url,
            'registration_url': registration_url,
            'organizer': source_username,
            'categories': [], # Will be populated by the main runner
            'is_online': 'online' in caption.lower() or 'daring' in caption.lower(),
            'price': 0, # Default price
        }

    def scrape(self):
        """Scrapes target Instagram accounts for posts and saves raw data for analysis."""
        self.logger.info(f"Starting scrape for {self.source_name}")
        if not self._login():
            self.logger.error("Halting Instagram scrape due to login failure.")
            return []

        all_parsed_events = []

        for target_username in self.target_accounts:
            self.logger.info(f"Scraping user: {target_username}")
            try:
                user_id = self.cl.user_id_from_username(target_username)
                self.logger.info(f"Successfully fetched user ID for {target_username}: {user_id}")
                medias = self.cl.user_medias(user_id, amount=10)
                self.logger.info(f"Found {len(medias)} posts for {target_username}.")
                posts_data = [media.dict() for media in medias]

                if self.debug:
                    debug_file = self.debug_output_path / f"instagram_{target_username}_posts.json"
                    with open(debug_file, 'w', encoding='utf-8') as f:
                        json.dump(posts_data, f, indent=4, ensure_ascii=False, default=str)
                    self.logger.info(f"Raw post data for {target_username} saved to {debug_file}")

                for post in posts_data:
                    parsed_event = self._parse_single_post(post)
                    if parsed_event:
                        all_parsed_events.append(parsed_event)
                        self.logger.info(f"Successfully parsed event: {parsed_event['title']}")

            except Exception as e:
                self.logger.error(f"An error occurred while scraping {target_username}: {e}", exc_info=True)

        self.logger.info(f"Successfully scraped {len(all_parsed_events)} events from {self.source_name}")
        return all_parsed_events
