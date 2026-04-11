# Infortic Scraper

Production-ready Instagram opportunity scraper with AI-powered extraction and automated database management.

## Features

- 🤖 Instagram post scraping with Playwright
- 🧠 AI-powered data extraction using Google Gemini
- 📸 OCR fallback for date extraction (Tesseract)
- 🔍 Intelligent duplicate detection and merging
- ⏰ Automatic expiration filtering
- 🗄️ PostgreSQL database integration (Neon)
- 🔄 Complete automation with GitHub Actions

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt
cd scraper && npm install && npx playwright install

# 2. Configure environment
cp config/.env.example config/.env
# Edit config/.env with your credentials

# 3. Run the pipeline
python run.py
```

## Documentation

- 📖 [Setup Guide](docs/SETUP.md) - Installation and configuration
- 🚀 [Usage Guide](docs/USAGE.md) - Running and scheduling
- 🏗️ [Architecture](docs/ARCHITECTURE.md) - System design and data flow

## Architecture

```
Instagram → Scraper (Node.js) → Extraction (Python + AI) → Database (PostgreSQL)
```

The system follows clean architecture with three distinct layers:

1. **Scraper Layer**: Extracts raw data from Instagram
2. **Extraction Layer**: Transforms captions into structured data (Gemini → Regex → OCR)
3. **Database Layer**: Validates, deduplicates, and persists data

See [Architecture Documentation](docs/ARCHITECTURE.md) for details.

## Key Features

### 3-Step Extraction Fallback
1. **Gemini AI**: Primary extraction method
2. **Regex**: Fallback for common patterns
3. **OCR**: Extracts dates from images when text fails

### Intelligent Duplicate Detection (Phase 2)
- Detects duplicates by title, organizer, and dates
- Merges records intelligently
- Preserves all source information

### Expiration Filtering (Phase 1)
- Automatically filters expired opportunities
- Validates registration and deadline dates
- Only inserts active opportunities

## Requirements

- Python 3.11+
- Node.js 20+
- PostgreSQL (Neon recommended)
- Google Gemini API key
- Tesseract OCR (optional)

## Project Structure

```
infortic_scraper/
├── config/              # Configuration files
├── scraper/             # Instagram scraper (Node.js)
├── src/
│   ├── extraction/      # AI extraction pipeline
│   └── database/        # Database operations
├── scripts/             # Utility scripts
├── data/                # Data directories
├── docs/                # Documentation
└── run.py               # Main pipeline runner
```

## Usage

### Complete Pipeline

```bash
python run.py
```

### Individual Steps

```bash
# 1. Scrape
cd scraper && node scraper.js

# 2. Extract
python src/extraction/main.py scraper/instagram_data.json

# 3. Insert
python src/database/main.py data/processed/extracted_data_*.json

# 4. Verify
python scripts/verify.py
```

### Utilities

```bash
# Clean database
python scripts/clean_db.py

# Verify results
python scripts/verify.py
```

## Automation

### GitHub Actions

The repository includes automated daily scraping:

1. Push to GitHub
2. Add secrets: `DATABASE_URL`, `GEMINI_API_KEY`
3. Workflow runs daily at 2 AM UTC
4. Manual trigger available in Actions tab

See [Usage Guide](docs/USAGE.md) for cron and Task Scheduler setup.

## Configuration

### Environment Variables (`.env`)

```env
DATABASE_URL=postgresql://user:password@host:port/database
GEMINI_API_KEY=your_api_key_here
BATCH_SIZE=25
DELAY_BETWEEN_REQUESTS=4
```

### Scraper Config (`scraper.config.json`)

```json
{
  "accounts": ["infolomba", "lomba.it"],
  "scrollCount": 3,
  "deepScrapeMode": true,
  "downloadImages": true
}
```

## Performance

- Processes 25 posts per API call
- 4-second rate limiting between batches
- Handles 50-100 posts in ~5 minutes
- Duplicate detection in O(n) time

## Contributing

This is a production system. For development:
1. Test changes in `main_scraper/` (experimental folder)
2. Document changes thoroughly
3. Update tests and documentation
4. Submit PR with clear description

## License

MIT

## Support

- 📖 [Documentation](docs/)
- 🐛 [Issues](https://github.com/your-repo/issues)
- 💬 [Discussions](https://github.com/your-repo/discussions)
