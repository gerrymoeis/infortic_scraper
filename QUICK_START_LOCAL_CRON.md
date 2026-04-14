# Quick Start: Local Cron Setup (5 Minutes)

**For**: Running Infortic Scraper daily on your Windows machine  
**Time**: 5-10 minutes  
**Cost**: FREE

---

## Step 1: Test Your Setup (2 minutes)

Double-click: `test_setup.bat`

**Expected**: All 6 tests pass ✅

**If any test fails**: See `LOCAL_CRON_SETUP.md` for detailed fixes

---

## Step 2: Test Manual Run (2 minutes)

Double-click: `run_daily_scraper.bat`

**Expected**: Pipeline completes successfully with exit code 0

**If errors**: Fix them before continuing

---

## Step 3: Set Up Task Scheduler (3 minutes)

### Quick Steps:

1. **Open Task Scheduler**
   - Press `Win + S`
   - Type "Task Scheduler"
   - Open the app

2. **Create Task**
   - Click "Create Basic Task..."
   - Name: `Infortic Scraper Daily`
   - Trigger: Daily at 00:00
   - Action: Start a program
   - Program: Browse to `run_daily_scraper.bat`
   - Start in: `D:\Gerry\Programmer\Best Terbaik(2026)\Tools\Project Instagram Scraper\infortic_scraper`

3. **Configure Properties**
   - ☑ Run whether user is logged on or not
   - ☑ Run with highest privileges
   - ☑ Wake the computer to run this task
   - ☐ Start only if on AC power (UNCHECK THIS!)

4. **Test It**
   - Right-click task → Run
   - Wait for completion
   - Check "Last Run Result" = Success (0x0)

---

## Step 4: Disable GitHub Actions (1 minute)

Edit `.github/workflows/multi-account-scrape.yml`:

```yaml
on:
  # schedule:
  #   - cron: '0 17 * * *'
  workflow_dispatch:  # Keep manual trigger
```

Commit and push:
```bash
git add .github/workflows/multi-account-scrape.yml
git commit -m "Disable scheduled GitHub Actions (using local cron)"
git push
```

---

## Done! 🎉

Your scraper will now run automatically every day at midnight.

**Important**: Keep your computer on (or in sleep mode) for the task to run!

---

## Troubleshooting

**Task doesn't run**: Check computer is on and network is available

**Task fails**: Run `run_daily_scraper.bat` manually to see errors

**Need help**: See `LOCAL_CRON_SETUP.md` for detailed guide

---

## What Happens Now

- ✅ Every day at 00:00 WIB
- ✅ Scraper runs automatically
- ✅ Data collected and inserted
- ✅ No geographic restrictions
- ✅ Completely free

---

**Next**: Consider upgrading to paid tier ($0.03/month) to use GitHub Actions again without keeping your computer on.
