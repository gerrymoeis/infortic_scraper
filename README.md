# Infortic Scraper

Production-ready Instagram opportunity scraper with AI-powered extraction, automated database management, and Cloudflare R2 CDN integration.

**Latest Update (May 2026)**: Added anti-detection features (random scheduling, checkpoint system, popup handlers) and R2 CDN integration.

## Features

- 🤖 Instagram post scraping with Playwright (dynamic 1-10 sessions)
- 🛡️ Anti-detection: random scheduling, account shuffling, popup handlers
- 🔄 Checkpoint system: resume capability on failures
- 🧠 AI-powered data extraction using Google Gemini 3.1 Flash-Lite
- 📸 OCR fallback for date extraction (Tesseract)
- 🔑 Proactive API key rotation (5 keys, round-robin)
- 🖼️ Cloudflare R2 CDN integration (WebP optimization, Q70)
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
Instagram → Scraper (Node.js) → Extraction (Python + AI) → R2 Upload (WebP) → Database (PostgreSQL)
```

The system follows clean architecture with four distinct layers:

1. **Scraper Layer**: Extracts raw data from Instagram (Node.js + Playwright)
2. **Extraction Layer**: Transforms captions into structured data (Gemini → Regex → OCR)
3. **R2 Upload Layer**: Optimizes and uploads images to Cloudflare R2 CDN (WebP Q70)
4. **Database Layer**: Validates, deduplicates, and persists data with R2 URLs (PostgreSQL)

### Key Optimizations (May 2026)

- **Cloudflare R2 CDN**: Images optimized to WebP Q70 (~60% size reduction) and served via CDN
- **R2 Before Database**: Images uploaded to R2 first, database populated with R2 URLs directly
- **Configurable Sessions**: Easy scaling from 2 to 5 scraper sessions (single constant change)
- **Proactive Key Rotation**: 5 API keys rotate before each request (not just on errors)
- **Optimal Model**: gemini-3.1-flash-lite-preview (15 RPM, 500 RPD - best free tier)
- **5 JSON Recovery Strategies**: Direct parse, regex extraction, formatting fixes, object rebuild, truncation fix
- **Unicode-Safe Logging**: Graceful error handling for Windows console encoding

## Key Features

### Anti-Detection System (New!)
- **Random Scheduling**: 7 different cron schedules (different time each day)
- **Random Startup Delay**: 10-40 minutes delay to avoid predictable patterns
- **Account Shuffling**: Fisher-Yates algorithm randomizes account order each run
- **Popup Handlers**: Auto-dismiss Instagram warnings and account selection screens
- **Password Challenge Handler**: Automatic re-authentication with human-like typing
- **Checkpoint System**: Resume from last successful point on failures
- **Debug Screenshots**: Automatic screenshots on errors for diagnosis

### Cloudflare R2 CDN Integration
- **WebP Optimization**: Images converted to WebP Q70 (~60% size reduction)
- **Fast CDN Delivery**: Images served via Cloudflare Workers
- **R2-First Architecture**: Images uploaded to R2 before database insertion
- **No Instagram URL Expiration**: All images permanently stored in R2
- **Automatic Upload**: GitHub Actions workflow handles R2 upload automatically

### Dynamic Multi-Session Scraping
- **1-10 Sessions**: Auto-detect available sessions dynamically
- **No Hardcoded Limits**: Easy scaling by adding session secrets
- **Independent Rate Limits**: Each session has isolated rate limiting
- **Staggered Starts**: 15-second intervals between sessions (human-like)

### Proactive API Key Rotation
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

2. **GEMINI_API_KEY**
   - Your Google Gemini API keys (comma-separated for multiple keys)
   - Get them from: https://aistudio.google.com/app/apikey
   - Format: `AIzaSy...,AIzaSy...,AIzaSy...` (5 keys recommended)

3. **INSTAGRAM_SESSION_1, INSTAGRAM_SESSION_2, ..., INSTAGRAM_SESSION_10**
   - Instagram session cookies for authentication (up to 10 sessions)
   - Generate using: `cd scraper && node generate-sessions.js`
   - Copy entire content of `session1.json`, `session2.json`, etc.
   - System auto-detects available sessions (1-10)

4. **INSTAGRAM_PASSWORD_1, INSTAGRAM_PASSWORD_2, ..., INSTAGRAM_PASSWORD_10**
   - Instagram account passwords for re-authentication challenges
   - Required when Instagram prompts for password after session login
   - One password per session (matches session number)
   - Used for automatic password challenge handling

5. **R2_ACCOUNT_ID**
   - Your Cloudflare R2 account ID
   - Get from: Cloudflare Dashboard → R2 → Overview

6. **R2_ACCESS_KEY_ID**
   - Your R2 access key ID
   - Generate from: Cloudflare Dashboard → R2 → Manage R2 API Tokens

7. **R2_SECRET_ACCESS_KEY**
   - Your R2 secret access key
   - Generated together with access key ID

8. **R2_BUCKET_NAME**
   - Your R2 bucket name (e.g., `infortic-images`)

9. **R2_PUBLIC_URL**
   - Your Cloudflare Worker URL for R2 bucket
   - Format: `https://your-bucket.your-domain.workers.dev`

See [Multi-Account Setup](MULTI_ACCOUNT_UPDATE.md) for detailed API key configuration.

## Configuration

### Environment Variables (`.env`)

```env
# Gemini API Keys (5 different projects - comma-separated)
GEMINI_API_KEY=key1,key2,key3,key4,key5

# Database (Neon PostgreSQL)
DATABASE_URL=postgresql://user:password@host:port/database?sslmode=require

# Cloudflare R2 Configuration
R2_ACCOUNT_ID=your_account_id_here
R2_ACCESS_KEY_ID=your_access_key_here
R2_SECRET_ACCESS_KEY=your_secret_key_here
R2_BUCKET_NAME=infortic-images
R2_PUBLIC_URL=https://infortic-images.gerrymoeis.workers.dev

# Extractor Settings
BATCH_SIZE=25
DELAY_BETWEEN_REQUESTS=5
GEMINI_MODEL=gemini-3.1-flash-lite-preview
```

### Scraper Config (`scraper.config.json`)

```json
{
  "accounts": ["infolomba", "lomba.it", "csrelatedcompetitions"],
  "scrollCount": 2,
  "deepScrapeMode": true,
  "downloadImages": true
}
```

### Session Generator Config (`scraper/generate-sessions.js`)

```javascript
// Change this to generate 2, 3, or 5 sessions
const SESSION_COUNT = 3;  // Default: 3 sessions
```

**How to scale sessions:**
1. Edit `scraper/generate-sessions.js`
2. Change `SESSION_COUNT` to 2, 3, or 5
3. Run: `node generate-sessions.js`
4. Update GitHub Secrets with new session files

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

### May 2026 - Anti-Detection & Reliability
- ✅ Random scheduling (7 different times per week)
- ✅ Random startup delay (10-40 minutes)
- ✅ Account shuffling (Fisher-Yates algorithm)
- ✅ Checkpoint system (resume on failures)
- ✅ Instagram popup handlers (automated behavior & account selection)
- ✅ Debug screenshots (automatic error diagnosis)
- ✅ Dynamic session detection (1-10 sessions)
- ✅ R2 CDN integration & WebP optimization
- ✅ Fixed R2 upload job dependencies

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

**Status**: ✅ Production Ready | **Success Rate**: 100% | **Last Updated**: May 2026
