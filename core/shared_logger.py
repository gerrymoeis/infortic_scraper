import logging

# Create a single, shared logger instance for the entire application.
# This avoids issues with logger hierarchy and propagation that can be caused by third-party libraries.
logger = logging.getLogger('infortic_scraper')
