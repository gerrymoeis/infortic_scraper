import os
import json
from datetime import datetime, timezone
from pydantic import HttpUrl
from dotenv import load_dotenv
import logging

# Use the new centralized logging setup
from core.logging_config import get_logger

# Import application modules
from core.database import get_supabase_client, get_or_create_source, save_competitions, get_all_categories, delete_expired_competitions
from core.data_cleaner import clean_competition_data
from scrapers.base_web_scraper import BaseWebScraper
from scrapers.infolomba_scraper import InfolombaScraper
from scrapers.informasilomba_scraper import InformasilombaScraper
from scrapers.infolombait_scraper import InfolombaitScraper
from scrapers.instagram_playwright_scraper import InstagramPlaywrightScraper

# Get a logger for this module
logger = get_logger(__name__)

# Load environment variables from file .env
load_dotenv()

def json_datetime_serializer(obj):
    """JSON serializer for objects not serializable by default json."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, HttpUrl):
        return str(obj)
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

def main(target_scraper=None, debug=False):
    """Main function to orchestrate the entire scraping process."""
    logger.info(f"Starting scraping process... (Debug Mode: {debug})")

    supabase = get_supabase_client()
    if not supabase:
        logger.error("Stopping process due to failed Supabase connection.")
        return

    logger.info("Starting cleanup of expired competitions in the database...")
    delete_expired_competitions(supabase)
    logger.info("Cleanup finished.")

    categories = get_all_categories(supabase)
    if categories is None:
        logger.error("Could not retrieve categories from the database. Stopping process.")
        return

    web_sources = [
        {"name": "infolomba.id", "url": "https://www.infolomba.id/", "scraper_class": InfolombaScraper},
        # Paused: {"name": "informasilomba.com", "url": "https://www.informasilomba.com/", "scraper_class": InformasilombaScraper},
        # Paused: {"name": "infolombait.com", "url": "https://www.infolombait.com/", "scraper_class": InfolombaitScraper},
    ]
    
    instagram_accounts = ["csrelatedcompetitions", "infolombait"]

    sources_to_scrape = web_sources
    if target_scraper:
        # Allow targeting web scrapers by name
        sources_to_scrape = [s for s in web_sources if s['name'] == target_scraper]
        # Allow targeting all instagram scrapers
        if target_scraper == 'instagram':
            sources_to_scrape = [] # Will only run instagram scrapers
        elif target_scraper not in [s['name'] for s in web_sources]:
            available_scrapers = [s['name'] for s in web_sources] + ['instagram']
            logger.error(f"Scraper '{target_scraper}' not found. Available scrapers: {available_scrapers}")
            return

    all_competitions = []
    source_counts = {}

    # --- Process Web Scrapers ---
    for source_info in sources_to_scrape:
        source_name = source_info['name']
        source_url = source_info.get('url', '')
        logger.info(f"Starting process for source: {source_name}")
        
        source_id = get_or_create_source(supabase, source_name, source_url)
        if not source_id:
            logger.warning(f"Failed to get source_id for {source_name}. Skipping.")
            source_counts[source_name] = 'Failed (Source ID)'
            continue

        try:
            scraper_class = source_info['scraper_class']
            with scraper_class(debug=debug) as scraper_instance:
                scraped_competitions = scraper_instance.scrape()
            
            count = len(scraped_competitions) if scraped_competitions else 0
            source_counts[source_name] = count
            logger.info(f"Finished scraping from {source_name}, got {count} raw competitions.")

            if scraped_competitions:
                valid_competitions = _validate_and_clean_competitions(scraped_competitions, source_id, source_name, categories, source_url)
                if valid_competitions:
                    logger.info(f"Adding {len(valid_competitions)} valid competitions from {source_name} to be saved.")
                    all_competitions.extend(valid_competitions)

        except Exception:
            logger.error(f"Caught an exception while running scraper: {source_name}", exc_info=True)
            source_counts[source_name] = 'Failed (Exception)'

    # --- Process Instagram Scrapers ---
    if not target_scraper or target_scraper == 'instagram':
        for account_name in instagram_accounts:
            source_name = f"instagram:{account_name}"
            source_url = f"https://www.instagram.com/{account_name}/"
            logger.info(f"Starting process for source: {source_name}")

            source_id = get_or_create_source(supabase, source_name, source_url)
            if not source_id:
                logger.warning(f"Failed to get source_id for {source_name}. Skipping.")
                source_counts[source_name] = 'Failed (Source ID)'
                continue
            
            try:
                scraper_instance = InstagramPlaywrightScraper(target_account=account_name, debug=debug)
                scraped_competitions = scraper_instance.scrape()

                count = len(scraped_competitions) if scraped_competitions else 0
                source_counts[source_name] = count
                logger.info(f"Finished scraping from {source_name}, got {count} raw competitions.")
                
                if scraped_competitions:
                    valid_competitions = _validate_and_clean_competitions(scraped_competitions, source_id, source_name, categories)
                    if valid_competitions:
                        logger.info(f"Adding {len(valid_competitions)} valid competitions from {source_name} to be saved.")
                        all_competitions.extend(valid_competitions)

            except Exception:
                logger.error(f"Caught an exception while running scraper: {source_name}", exc_info=True)
                source_counts[source_name] = 'Failed (Exception)'


    if all_competitions:
        log_dir = 'logs'
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        log_file_path = os.path.join(log_dir, f'saved_competitions_{timestamp}.json')
        try:
            serializable_competitions = json.loads(json.dumps(all_competitions, default=json_datetime_serializer))
            with open(log_file_path, 'w', encoding='utf-8') as f:
                json.dump(serializable_competitions, f, ensure_ascii=False, indent=4)
            logger.info(f"Saved competition data to: {log_file_path}")
        except (IOError, TypeError) as e:
            logger.error(f"Failed to save log file: {e}")

        logger.info(f"Saving {len(all_competitions)} validated competitions to the database...")
        save_competitions(supabase, all_competitions)
    else:
        logger.warning("No new competitions were successfully scraped and validated from any source.")

    logger.info('Scraping process finished.')
    logger.info('--- Scraping Summary ---')
    for source, count in source_counts.items():
        logger.info(f'{source}: {count} events')
    logger.info('------------------------')

def _validate_and_clean_competitions(scraped_competitions, source_id, source_name, categories, source_url=None):
    """Helper function to validate and clean a list of scraped competitions."""
    valid_competitions = []
    now = datetime.now(timezone.utc)

    for raw_competition in scraped_competitions:
        raw_competition['source_id'] = source_id
        if not raw_competition.get('url') and source_url:
            raw_competition['url'] = source_url

        competition = clean_competition_data(raw_competition, categories)

        if not competition or not competition.get('title'):
            logger.warning(f"Skipping competition from {source_name} due to missing title after cleaning.")
            continue

        if competition.get('deadline') and competition.get('deadline') < now:
            logger.warning(f"Skipping expired competition: '{competition.get('title')}'")
            continue
        
        has_required_fields = (
            competition.get('registration_url') and
            competition.get('poster_url') and
            (competition.get('deadline') or competition.get('event_date_start'))
        )

        if not has_required_fields:
            logger.warning(f"Filtering competition '{competition.get('title')}' due to missing mandatory fields.")
            continue

        valid_competitions.append(competition)
    
    return valid_competitions

if __name__ == "__main__":
    # This block is now primarily for direct execution/testing of this module
    # The main entry point is run.py
    main(debug=True)
