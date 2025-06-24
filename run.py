import sys
import os
import argparse

# Add the project root directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now that the path is configured, we can import our modules
from core.logging_config import setup_logging
import scraper

def main():
    """
    Parses command-line arguments, sets up logging, and runs the main scraper application.
    """
    parser = argparse.ArgumentParser(description="Infortic Scraper")
    parser.add_argument(
        '--scraper',
        type=str,
        help='Run a specific scraper by name (e.g., instagram). If not provided, all scrapers will run.',
        default=None
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug mode for more verbose logging.'
    )
    args = parser.parse_args()

    # Setup logging as the very first step, using the debug flag from args
    setup_logging(debug=args.debug)

    # Pass the arguments to the main scraper logic
    scraper.main(target_scraper=args.scraper, debug=args.debug)

if __name__ == "__main__":
    main()
