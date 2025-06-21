import sys
import os

# Add the project root directory to the Python path to ensure that all modules can be imported correctly.
# This is a clean and robust way to handle the local project structure.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now that the path is configured, we can import and run the main application.
import scraper

if __name__ == "__main__":
    scraper.main()
