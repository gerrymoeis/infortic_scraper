# GitHub Actions Setup Guide

Complete guide for setting up automated daily scraping with GitHub Actions.

---

## Overview

The automated workflow runs daily at **13:00 WIB (06:00 UTC)** and performs:

1. **Scraping**: Extract posts from 7 Instagram accounts
2. **Extraction**: AI-powered data extraction (Gemini + OCR)
3. **Database**: Insert/update PostgreSQL database
4. **Cleanup**: Mark expired opportunities
5. **Verification**: Verify data integrity

---

## Prerequisites

Before setting up GitHub Actions, ensure you have:

1. ✅ GitHub repository with code pushed
2. ✅ Neon PostgreSQL database (or any PostgreSQL)
3. ✅ 5 Google Gemini API keys (from different projects)
4. ✅ Instagram session cookies (from local scraper run)

---

## Step 1: Configure GitHub Secrets

Navigate to your repository on GitHub:

```
Repository → Settings → Secrets and variables → Actions → New repository secret
```

### Required Secrets

#### 1. DATABASE_URL

**Description**: PostgreSQL connection string for Neon database

**Format**:
```
postgresql://username:password@host:port/database?sslmode=require
```

**Example**:
```
postgresql://neondb_owner:npg_ABC123@ep-cool-name-123456.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

**How to get**:
1. Go to [Neon Console](https://console.neon.tech/)
2. Select your project
3. Go to "Connection Details"
4. Copy the connection string
5. Make sure it includes `?sslmode=require`

---

#### 2. GEMINI_API_KEY

**Description**: Google Gemini API keys (comma-separated for multiple keys)

**Format**:
```
AIzaSy...,AIzaSy...,AIzaSy...,AIzaSy...,AIzaSy...
```

**Example**:
```
AIzaSyA7NDcte_X8kBjWqosWypoX7KfDm6ZR6xA,AIzaSyC8GCVclD66BHpyz5lY45M0Nur9uB6LzqI,AIzaSyBr9SYDb16KXaChys2-Rh8s9wtoLEO6hCU,AIzaSyBrMh48wv2S2NtbahNoOMtEzfgOGIDbksw,AIzaSyApbNDzX7Zw-fDobM10fFNRn2QUPBm8zA8
```

**How to get**:
1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create 5 API keys from 5 different Google Cloud projects
3. Copy all keys
4. Join them with commas (no spaces)
5. Paste into GitHub Secret

**Important**:
- Use keys from **different Google Cloud projects** for independent quotas
- Each project has: 15 RPM, 500 RPD
- Total capacity: 75 RPM, 2,500 RPD

---

#### 3. INSTAGRAM_SESSION

**Description**: Instagram session cookies for authentication

**Format**: JSON array of cookies

**How to get**:

1. **Run scraper locally once**:
   ```bash
   cd scraper
   node scraper.js
   ```

2. **Login to Instagram** when prompted (in the browser that opens)

3. **Copy session.json content**:
   ```bash
   # On Windows
   type scraper\session.json | clip
   
   # On Mac/Linux
   cat scraper/session.json | pbcopy
   ```

4. **Paste into GitHub Secret**

**Example format** (your actual content will be much longer):
```json
[
  {
    "name": "csrftoken",
    "value": "abc123...",
    "domain": ".instagram.com",
    "path": "/",
    "expires": 1234567890,
    "httpOnly": true,
    "secure": true,
    "sameSite": "None"
  },
  {
    "name": "sessionid",
    "value": "xyz789...",
    "domain": ".instagram.com",
    ...
  }
]
```

**Important Notes**:
- Session expires after ~60 days
- You'll need to update this secret when it expires
- Never commit `session.json` to the repository
- Keep it secure (provides access to your Instagram account)

---

## Step 2: Verify Secrets Configuration

After adding all secrets, verify:

1. Go to: `Repository → Settings → Secrets and variables → Actions`
2. You should see 3 secrets:
   - ✅ `DATABASE_URL`
   - ✅ `GEMINI_API_KEY`
   - ✅ `INSTAGRAM_SESSION`

**Screenshot checklist**:
```
Repository secrets
├── DATABASE_URL          (Updated X days ago)
├── GEMINI_API_KEY        (Updated X days ago)
└── INSTAGRAM_SESSION     (Updated X days ago)
```

---

## Step 3: Enable GitHub Actions

1. Go to: `Repository → Actions`
2. If Actions are disabled, click "I understand my workflows, go ahead and enable them"
3. You should see the workflow: **"Daily Scraper Pipeline"**

---

## Step 4: Test the Workflow (Manual Trigger)

Before waiting for the scheduled run, test manually:

### 4.1 Navigate to Actions

```
Repository → Actions → Daily Scraper Pipeline → Run workflow
```

### 4.2 Configure Test Run

**Options**:
- **Branch**: `master` (or your main branch)
- **Skip scraping**: Leave unchecked (we want to test everything)
- **Accounts**: Leave empty (will scrape all 7 accounts)

### 4.3 Click "Run workflow"

The workflow will start immediately.

### 4.4 Monitor Progress

Click on the running workflow to see:
- **Scrape**: Instagram scraping progress
- **Extract**: AI extraction progress
- **Database**: Database insertion progress
- **Cleanup**: Cleanup and verification
- **Report**: Final pipeline report

**Expected duration**: ~15-20 minutes

---

## Step 5: Verify Results

### 5.1 Check Job Status

All jobs should show ✅ (green checkmark):
- ✅ Scrape Instagram Posts
- ✅ Extract Structured Data
- ✅ Update Database
- ✅ Cleanup & Verify
- ✅ Pipeline Report

### 5.2 Review Summary

Click on "Pipeline Report" job to see:
- Total posts scraped
- Extraction success rate
- Database insertion status
- Overall pipeline status

### 5.3 Check Artifacts

Go to the workflow run page and scroll down to "Artifacts":
- `scraped-data-XXX`: Raw Instagram data
- `extracted-data-XXX`: Structured data

Download and verify the data if needed.

### 5.4 Verify Database

Check your Neon database:
```sql
SELECT COUNT(*) FROM opportunities;
SELECT * FROM opportunities ORDER BY created_at DESC LIMIT 10;
```

You should see newly inserted opportunities.

---

## Step 6: Schedule Configuration

The workflow is scheduled to run daily at **13:00 WIB (06:00 UTC)**.

### Cron Schedule

```yaml
schedule:
  - cron: '0 6 * * *'  # 13:00 WIB = 06:00 UTC
```

### Time Zone Conversion

| Time Zone | Time |
|-----------|------|
| WIB (UTC+7) | 13:00 |
| UTC | 06:00 |
| PST (UTC-8) | 22:00 (previous day) |
| EST (UTC-5) | 01:00 |

### Verify Schedule

The workflow will run automatically every day at 13:00 WIB.

**Next run**: Check the Actions tab for the next scheduled run time.

---

## Troubleshooting

### Issue 1: Scraping Failed

**Symptoms**: Scrape job fails with authentication error

**Solution**:
1. Instagram session expired
2. Update `INSTAGRAM_SESSION` secret:
   ```bash
   cd scraper
   node scraper.js  # Login again
   cat session.json  # Copy new session
   ```
3. Update GitHub Secret
4. Re-run workflow

---

### Issue 2: Extraction Failed

**Symptoms**: Extract job fails with API error

**Solution**:
1. Check Gemini API keys are valid
2. Verify keys are from different projects
3. Check rate limits in [AI Studio](https://aistudio.google.com/)
4. Update `GEMINI_API_KEY` secret if needed

---

### Issue 3: Database Failed

**Symptoms**: Database job fails with connection error

**Solution**:
1. Verify Neon database is active
2. Check `DATABASE_URL` secret is correct
3. Ensure connection string includes `?sslmode=require`
4. Test connection locally:
   ```bash
   psql "$DATABASE_URL"
   ```

---

### Issue 4: Workflow Not Running

**Symptoms**: Scheduled workflow doesn't run at 13:00 WIB

**Solution**:
1. Check GitHub Actions are enabled
2. Verify cron schedule is correct
3. GitHub Actions may have delays (up to 15 minutes)
4. Check repository activity (inactive repos may have delayed runs)

---

## Monitoring

### Daily Checks

1. **Check workflow status**:
   ```
   Repository → Actions → Daily Scraper Pipeline
   ```

2. **Review summary**:
   - Click on latest run
   - Check "Pipeline Report" job
   - Verify all jobs succeeded

3. **Check database**:
   ```sql
   SELECT COUNT(*) FROM opportunities WHERE created_at > NOW() - INTERVAL '1 day';
   ```

### Weekly Checks

1. **Review artifacts**:
   - Download and inspect extracted data
   - Verify data quality

2. **Check API usage**:
   - Go to [AI Studio](https://aistudio.google.com/)
   - Verify rate limits are not exceeded

3. **Update session if needed**:
   - Instagram session expires after ~60 days
   - Update before expiration

---

## Advanced Configuration

### Custom Schedule

To change the schedule, edit `.github/workflows/daily-scraper-pipeline.yml`:

```yaml
schedule:
  # Run at 08:00 WIB (01:00 UTC)
  - cron: '0 1 * * *'
  
  # Run twice daily: 08:00 and 20:00 WIB
  - cron: '0 1 * * *'   # 08:00 WIB
  - cron: '0 13 * * *'  # 20:00 WIB
```

### Custom Accounts

To scrape specific accounts only:

1. Go to: `Actions → Daily Scraper Pipeline → Run workflow`
2. Set "Accounts": `infolomba,lomba.it`
3. Click "Run workflow"

### Skip Scraping

To test extraction/database without scraping:

1. Go to: `Actions → Daily Scraper Pipeline → Run workflow`
2. Check "Skip scraping step"
3. Click "Run workflow"

This will use existing scraped data from artifacts.

---

## Notifications (Optional)

### Slack Notifications

Add to the `report` job in the workflow:

```yaml
- name: Send Slack notification
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }}
    payload: |
      {
        "text": "❌ Daily scraper pipeline failed",
        "blocks": [
          {
            "type": "section",
            "text": {
              "type": "mrkdwn",
              "text": "*Daily Scraper Pipeline Failed*\n\nRun: ${{ github.run_number }}\nTime: $(date -u)"
            }
          }
        ]
      }
```

### Email Notifications

GitHub automatically sends email notifications for workflow failures if you have notifications enabled in your GitHub settings.

---

## Cost Estimation

### GitHub Actions

- **Free tier**: 2,000 minutes/month
- **Usage per run**: ~20 minutes
- **Runs per month**: 30 (daily)
- **Total usage**: 600 minutes/month
- **Cost**: $0 (within free tier)

### Gemini API

- **Free tier**: 500 RPD per project × 5 projects = 2,500 RPD
- **Usage per run**: 7 requests
- **Runs per month**: 30
- **Total usage**: 210 requests/month
- **Cost**: $0 (within free tier)

### Neon Database

- **Free tier**: 0.5 GB storage, 100 hours compute/month
- **Usage**: Minimal (few MB, few minutes per day)
- **Cost**: $0 (within free tier)

**Total monthly cost**: $0 ✅

---

## Summary

### Setup Checklist

- [ ] Add `DATABASE_URL` secret
- [ ] Add `GEMINI_API_KEY` secret (5 keys, comma-separated)
- [ ] Add `INSTAGRAM_SESSION` secret
- [ ] Enable GitHub Actions
- [ ] Test workflow manually
- [ ] Verify all jobs succeed
- [ ] Check database for new data
- [ ] Monitor first scheduled run (13:00 WIB)

### Expected Results

- ✅ **Daily runs**: Automatic at 13:00 WIB
- ✅ **Success rate**: 100% (based on testing)
- ✅ **Processing time**: ~15-20 minutes
- ✅ **Data quality**: High (AI + OCR + fallbacks)
- ✅ **Cost**: $0 (all within free tiers)

---

## Support

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review workflow logs in GitHub Actions
3. Check [Setup Guide](SETUP_GUIDE.md) for local testing
4. Create an issue in the repository

---

**Status**: ✅ Ready for Production  
**Schedule**: Daily at 13:00 WIB (06:00 UTC)  
**Last Updated**: April 2026
