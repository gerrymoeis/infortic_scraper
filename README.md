# Infortic Scraper

Production-ready Instagram opportunity scraper with AI-powered extraction and automated database management.

**Latest Update (April 2026)**: System optimized with 100% success rate, proactive API key rotation, and zero rate limit errors.

## Features

- 🤖 Instagram post scraping with Playwright
- 🧠 AI-powered data extraction using Google Gemini 3.1 Flash-Lite
- 📸 OCR fallback for date extraction (Tesseract)
- 🔄 Proactive API key rotation (5 keys, round-robin)
- 🔍 Intelligent duplicate detection and merging
- ⏰ Automatic expiration filtering
- 🗄️ PostgreSQL database integration (Neon)
- 🚀 Complete automation with GitHub Actions
- ✅ 100% success rate with comprehensive error recovery

## Performance Metrics

- **Success Rate**: 100% (168/168 posts)
- **Processing Time**: ~15 minutes for 168 posts
- **API Usage**: 0.28% of daily capacity (7 requests)
- **Rate Limit Errors**: 0 (proactive key rotation)
- **Capacity**: Can run 357 times per day

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

- 📖 [Setup Guide](SETUP_GUIDE.md) - Installation and configuration
- 🚀 [Quick Start](QUICK_START.md) - Get started in 5 minutes
- 🔑 [Multi-Account Setup](MULTI_ACCOUNT_UPDATE.md) - Configure multiple API keys

## Architecture

```
Instagram → Scraper (Node.js) → Extraction (Python + AI) → Database (PostgreSQL)
```

The system follows clean architecture with three distinct layers:

1. **Scraper Layer**: Extracts raw data from Instagram (Node.js + Playwright)
2. **Extraction Layer**: Transforms captions into structured data (Gemini → Regex → OCR)
3. **Database Layer**: Validates, deduplicates, and persists data (PostgreSQL)

### Key Optimizations (April 2026)

- **Proactive Key Rotation**: 5 API keys rotate before each request (not just on errors)
- **Optimal Model**: gemini-3.1-flash-lite-preview (15 RPM, 500 RPD - best free tier)
- **5 JSON Recovery Strategies**: Direct parse, regex extraction, formatting fixes, object rebuild, truncation fix
- **Unicode-Safe Logging**: Graceful error handling for Windows console encoding

## Key Features

### Proactive API Key Rotation (New!)
- **5 API Keys**: Supports multiple Google Cloud projects
- **Round-Robin Rotation**: Keys rotate before each request (not just on errors)
- **Even Load Distribution**: Prevents any single project from hitting rate limits
- **Zero Rate Limit Errors**: Achieved in production testing

### 5-Strategy JSON Recovery
1. **Direct Parse**: Standard JSON parsing (fastest)
2. **Regex Extraction**: Extract JSON array from response
3. **Formatting Fixes**: Fix trailing commas, missing commas
4. **Object Rebuild**: Parse individual objects and rebuild array (most robust)
5. **Truncation Fix**: Handle incomplete API responses

### 3-Step Extraction Fallback
1. **Gemini AI**: Primary extraction method (gemini-3.1-flash-lite-preview)
2. **Regex**: Fallback for common patterns (dates, contacts, URLs)
3. **OCR**: Extracts text from images when caption lacks details

### Intelligent Duplicate Detection
- Detects duplicates by title, organizer, and dates
- Merges records intelligently
- Preserves all source information

### Expiration Filtering
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
2. Configure GitHub Secrets (see below)
3. Workflow runs daily at 2 AM UTC
4. Manual trigger available in Actions tab

### GitHub Secrets Setup

Navigate to your repository → Settings → Secrets and variables → Actions → New repository secret

Add the following secrets:

1. **DATABASE_URL**
   - Your Neon PostgreSQL connection string
   - Format: `postgresql://user:password@host:port/database?sslmode=require`
   - Example: `postgresql://user:pass@ep-cool-name-123456.us-east-2.aws.neon.tech/neondb?sslmode=require`

2. **GEMINI_API_KEY**
   - Your Google Gemini API keys (comma-separated for multiple keys)
   - Get them from: https://aistudio.google.com/app/apikey
   - Format: `AIzaSy...,AIzaSy...,AIzaSy...` (5 keys recommended)
   - **Important**: Use keys from different Google Cloud projects for independent quotas

3. **INSTAGRAM_SESSION**
   - Instagram session cookies for authentication
   - Required for scraper to access Instagram
   
   **How to get session.json content:**
   
   a. Run the scraper locally once:
   ```bash
   cd scraper
   node scraper.js
   ```
   
   b. After successful login, copy the entire content of `scraper/session.json`
   
   c. Paste the entire JSON array into the GitHub Secret (including the `[` and `]` brackets)
   
   d. The content should look like:
   ```json
   [
     {
       "name": "csrftoken",
       "value": "...",
       "domain": ".instagram.com",
       ...
     },
     ...
   ]
   ```
   
   **Important Notes:**
   - Session expires after ~60 days, you'll need to update the secret
   - Never commit `session.json` to the repository
   - Keep your session.json secure (it provides access to your Instagram account)

See [Multi-Account Setup](MULTI_ACCOUNT_UPDATE.md) for detailed API key configuration.

## Configuration

### Environment Variables (`.env`)

```env
# Gemini API Keys (5 different projects - comma-separated)
# Each project has independent quotas: 15 RPM, 500 RPD
GEMINI_API_KEY=key1,key2,key3,key4,key5

# Database (Neon PostgreSQL)
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require

# Extractor Settings
BATCH_SIZE=25                    # Posts per API request (optimal for ~24 posts/account)
DELAY_BETWEEN_REQUESTS=5         # Seconds between requests (safe buffer)
GEMINI_MODEL=gemini-3.1-flash-lite-preview  # Best free tier limits
```

**Why These Settings?**
- **BATCH_SIZE=25**: Perfect for ~24 posts per account (1 request per account)
- **DELAY=5**: Safe buffer for API processing (15 RPM = 1 request every 4s minimum)
- **Flash-Lite**: Best free tier limits (15 RPM, 500 RPD vs 5 RPM, 20 RPD for other models)
- **5 Keys**: Total capacity = 75 RPM, 2,500 RPD (can run 357 times per day)

### Scraper Config (`scraper.config.json`)

```json
{
  "accounts": ["infolomba", "lomba.it", "csrelatedcompetitions"],
  "scrollCount": 2,
  "deepScrapeMode": true,
  "downloadImages": true
}
```

## Performance

### Production Metrics (April 2026)
- **Success Rate**: 100% (168/168 posts)
- **Processing Time**: ~15 minutes for 168 posts
- **API Requests**: 7 (one per account)
- **API Usage**: 0.28% of daily capacity
- **Rate Limit Errors**: 0 (proactive key rotation)
- **JSON Parse Errors**: 0 (5 recovery strategies)
- **Average Response Time**: 19.4 seconds per account

### Capacity
- **Daily Capacity**: 2,500 requests (5 keys × 500 RPD)
- **Runs Per Day**: 357 possible runs
- **Scalability**: Can add more accounts without hitting limits

### Efficiency
- Processes 25 posts per API call
- 5-second rate limiting between batches
- Proactive key rotation prevents quota exhaustion
- Duplicate detection in O(n) time

## Contributing

This is a production system. For development:
1. Test changes thoroughly before deploying
2. Document changes in backup folder (`infortic_scraper_backup/`)
3. Follow the rules in `infortic_scraper_backup/rules.md`
4. Update tests and documentation
5. Submit PR with clear description

## Recent Updates

### April 2026 - System Optimization
- ✅ Achieved 100% success rate (up from 85.7%)
- ✅ Implemented proactive API key rotation (5 keys, round-robin)
- ✅ Added 5 JSON recovery strategies
- ✅ Fixed Unicode logging for Windows compatibility
- ✅ Removed fallback models (kept only best-performing model)
- ✅ Zero rate limit errors in production testing
- ✅ Comprehensive documentation in backup folder

See `infortic_scraper_backup/FINAL_TEST_RESULTS_SUCCESS_2026_04_17.md` for detailed test results.

## Troubleshooting

### Rate Limit Errors
- **Solution**: System now uses proactive key rotation (5 keys)
- **Status**: Zero rate limit errors in production

### JSON Parsing Errors
- **Solution**: 5 recovery strategies implemented
- **Status**: 100% success rate in production

### Unicode Logging Errors (Windows)
- **Solution**: UTF-8 encoding with graceful fallback
- **Status**: Fixed in logger.py

For more issues, see [Setup Guide](SETUP_GUIDE.md) or create an issue.

## License

MIT

## Support

- 📖 [Quick Start Guide](QUICK_START.md)
- 🔧 [Setup Guide](SETUP_GUIDE.md)
- 🔑 [Multi-Account Setup](MULTI_ACCOUNT_UPDATE.md)
- 📊 [Test Results](../infortic_scraper_backup/FINAL_TEST_RESULTS_SUCCESS_2026_04_17.md)
- 🐛 [Issues](https://github.com/your-repo/issues)
- 💬 [Discussions](https://github.com/your-repo/discussions)

---

**Status**: ✅ Production Ready | **Success Rate**: 100% | **Last Updated**: April 2026
