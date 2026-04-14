# Local Cron Setup Guide - Windows Task Scheduler

**Date**: April 13, 2026  
**Purpose**: Run Infortic Scraper daily on your local machine  
**Estimated Time**: 15-30 minutes

---

## Overview

This guide will help you set up the scraper to run automatically every day on your Windows machine using Task Scheduler. This is the **free alternative** to GitHub Actions that avoids geographic restrictions.

---

## Prerequisites

Before starting, make sure you have:

- [x] Python 3.11+ installed
- [x] Node.js 20+ installed
- [x] Virtual environment created (`venv` folder exists)
- [x] All dependencies installed
- [x] `config/.env` file with API keys and database URL
- [x] Playwright browser installed

---

## Step 1: Verify Your Setup (5 minutes)

### 1.1 Run the Test Script

Double-click `test_setup.bat` or run in Command Prompt:

```cmd
test_setup.bat
```

**Expected Output**:
```
[TEST 1/6] Checking directory... [PASS]
[TEST 2/6] Checking virtual environment... [PASS]
[TEST 3/6] Checking Python packages... [PASS]
[TEST 4/6] Checking config/.env file... [PASS]
[TEST 5/6] Checking Gemini API keys... [PASS]
[TEST 6/6] Checking database connection... [PASS]

All Tests Passed!
```

### 1.2 If Any Test Fails

**Virtual environment not found**:
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

**Packages not installed**:
```cmd
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
playwright install-deps chromium
```

**config/.env not found**:
- Copy `config/.env.example` to `config/.env`
- Add your API keys and database URL

**Database connection failed**:
- Check your `DATABASE_URL` in `config/.env`
- Make sure Neon database is accessible

---

## Step 2: Test Manual Run (5 minutes)

### 2.1 Run the Scraper Manually

Double-click `run_daily_scraper.bat` or run in Command Prompt:

```cmd
run_daily_scraper.bat
```

**What This Does**:
1. Activates Python virtual environment
2. Runs the complete pipeline:
   - Scrapes Instagram accounts
   - Extracts data with Gemini AI
   - Inserts into database
   - Cleans up expired opportunities
   - Verifies results
3. Deactivates virtual environment

### 2.2 Expected Output

```
============================================================
Infortic Scraper - Daily Run
============================================================
Started: 04/13/2026 18:00:00
============================================================

[STEP 1/2] Activating Python virtual environment...
[SUCCESS] Virtual environment activated

[STEP 2/2] Running scraper pipeline...

[PIPELINE] Infortic Scraper - Complete Pipeline
============================================================
[STEP 1/5] Instagram Scraping
[STEP 2/5] AI Extraction (Gemini + OCR)
[STEP 3/5] Database Insertion
[STEP 4/5] Cleanup Expired Opportunities
[STEP 5/5] Results Verification

[COMPLETE] Pipeline Execution Complete!
============================================================
```

### 2.3 Verify Results

Check that:
- [ ] No errors in the output
- [ ] Data was scraped successfully
- [ ] Extraction completed
- [ ] Database was updated
- [ ] Exit code is 0

**If there are errors**: Fix them before proceeding to Task Scheduler setup.

---

## Step 3: Set Up Windows Task Scheduler (10 minutes)

### 3.1 Open Task Scheduler

**Method 1**: Search
1. Press `Win + S`
2. Type "Task Scheduler"
3. Click "Task Scheduler" app

**Method 2**: Run Dialog
1. Press `Win + R`
2. Type `taskschd.msc`
3. Press Enter

### 3.2 Create a New Task

1. In Task Scheduler, click **"Create Basic Task..."** in the right panel
2. Or: **Action** menu → **Create Basic Task...**

### 3.3 Configure Task - General

**Name**: `Infortic Scraper Daily`

**Description**: 
```
Runs the Infortic Instagram scraper daily to collect competition and opportunity data. 
Scrapes Instagram accounts, extracts data with AI, and updates the database.
```

Click **Next**

### 3.4 Configure Task - Trigger

**When do you want the task to start?**: Select **"Daily"**

Click **Next**

**Start date**: Today's date  
**Start time**: `00:00:00` (midnight WIB)  
**Recur every**: `1` days

Click **Next**

### 3.5 Configure Task - Action

**What action do you want the task to perform?**: Select **"Start a program"**

Click **Next**

**Program/script**: Click **Browse** and navigate to:
```
D:\Gerry\Programmer\Best Terbaik(2026)\Tools\Project Instagram Scraper\infortic_scraper\run_daily_scraper.bat
```

**Start in (optional)**: 
```
D:\Gerry\Programmer\Best Terbaik(2026)\Tools\Project Instagram Scraper\infortic_scraper
```

Click **Next**

### 3.6 Configure Task - Finish

Review the summary:
- Name: Infortic Scraper Daily
- Trigger: Daily at 00:00
- Action: Start run_daily_scraper.bat

**Check**: ☑ **"Open the Properties dialog for this task when I click Finish"**

Click **Finish**

---

## Step 4: Advanced Task Settings (5 minutes)

The Properties dialog should open automatically. If not, right-click the task and select **Properties**.

### 4.1 General Tab

**Security options**:
- ☑ **Run whether user is logged on or not**
- ☑ **Run with highest privileges**
- ☐ Do not store password (leave unchecked)

**Configure for**: Windows 10 (or your Windows version)

### 4.2 Triggers Tab

Click **Edit** on the daily trigger:

**Advanced settings**:
- ☑ **Enabled**
- ☐ Stop task if it runs longer than: (leave unchecked, or set to 3 hours)
- ☑ **Repeat task every**: (optional, leave unchecked for once daily)

Click **OK**

### 4.3 Actions Tab

Verify the action is correct:
- Action: Start a program
- Program: `...\run_daily_scraper.bat`
- Start in: `...\infortic_scraper`

### 4.4 Conditions Tab

**Power**:
- ☐ Start the task only if the computer is on AC power (uncheck this!)
- ☐ Stop if the computer switches to battery power (uncheck this!)
- ☑ **Wake the computer to run this task** (check this!)

**Network**:
- ☑ **Start only if the following network connection is available**: Any connection

### 4.5 Settings Tab

**General**:
- ☑ **Allow task to be run on demand**
- ☑ **Run task as soon as possible after a scheduled start is missed**
- ☐ If the task fails, restart every: (leave unchecked)

**If the task is already running**:
- Select: **Do not start a new instance**

Click **OK**

### 4.6 Enter Your Password

Windows will ask for your password to save the task.

Enter your Windows password and click **OK**.

---

## Step 5: Test the Scheduled Task (5 minutes)

### 5.1 Run Task Manually

1. In Task Scheduler, find your task: **Infortic Scraper Daily**
2. Right-click the task
3. Select **Run**

### 5.2 Monitor Execution

**Method 1**: Task Scheduler
- The task status will change to "Running"
- Wait for it to complete (usually 2-5 minutes)
- Status should change to "Ready"
- Check "Last Run Result": Should be "The operation completed successfully (0x0)"

**Method 2**: Check Logs
- Open: `infortic_scraper\logs\`
- Find the latest log file
- Verify no errors

### 5.3 Verify Results

Check the database:
```sql
SELECT COUNT(*) FROM opportunities WHERE status = 'active';
```

Should show updated count.

---

## Step 6: Disable GitHub Actions (2 minutes)

Since you're now running locally, disable the GitHub Actions schedule to avoid conflicts.

### 6.1 Edit Workflow File

Open: `.github/workflows/multi-account-scrape.yml`

### 6.2 Comment Out Schedule

Change:
```yaml
on:
  schedule:
    - cron: '0 17 * * *'
  workflow_dispatch:
```

To:
```yaml
on:
  # schedule:
  #   - cron: '0 17 * * *'
  workflow_dispatch:  # Keep manual trigger for testing
```

### 6.3 Commit and Push

```bash
git add .github/workflows/multi-account-scrape.yml
git commit -m "Disable scheduled GitHub Actions (using local cron instead)"
git push origin main
```

---

## Troubleshooting

### Task Doesn't Run

**Check 1**: Task is enabled
- Right-click task → Properties → General tab
- Make sure "Enabled" is checked

**Check 2**: Computer is on
- Task Scheduler can wake the computer, but it must be on (not shut down)
- Consider using Sleep mode instead of Shutdown

**Check 3**: Network is available
- Task requires internet connection
- Check Conditions tab → Network settings

### Task Runs But Fails

**Check 1**: View task history
- Task Scheduler → View → Show All Running Tasks
- Check "Last Run Result" column

**Check 2**: Check logs
- Open: `infortic_scraper\logs\`
- Find latest log file
- Look for errors

**Check 3**: Run manually
- Double-click `run_daily_scraper.bat`
- See what error appears

### Common Errors

**"Virtual environment not found"**:
```cmd
cd infortic_scraper
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**"Module not found"**:
```cmd
venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

**"Database connection failed"**:
- Check `config/.env` → `DATABASE_URL`
- Verify Neon database is accessible

**"API key error"**:
- Check `config/.env` → `GEMINI_API_KEY`
- Verify keys are valid (not revoked)

---

## Monitoring

### Daily Checks (Optional)

**Check 1**: Task History
- Open Task Scheduler
- Find your task
- Check "Last Run Time" and "Last Run Result"

**Check 2**: Database
```sql
SELECT 
  DATE(created_at) as date,
  COUNT(*) as new_opportunities
FROM opportunities
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;
```

**Check 3**: Logs
- Check `infortic_scraper\logs\` folder
- Review recent log files for errors

### Email Notifications (Advanced)

You can configure Task Scheduler to send email on failure:
1. Task Properties → Actions tab
2. Add new action: "Send an e-mail"
3. Configure SMTP settings

**Note**: This requires SMTP server configuration.

---

## Maintenance

### Weekly

- [ ] Check task is running successfully
- [ ] Review logs for any warnings
- [ ] Verify database is being updated

### Monthly

- [ ] Update dependencies: `pip install -r requirements.txt --upgrade`
- [ ] Check for Playwright updates: `playwright install chromium`
- [ ] Review and clean old log files

### As Needed

- [ ] Update API keys if they expire
- [ ] Adjust schedule if needed
- [ ] Update scraper configuration

---

## Advantages of Local Cron

✅ **Free**: No costs  
✅ **Reliable**: No geographic restrictions  
✅ **Fast**: Local execution  
✅ **Flexible**: Easy to modify schedule  
✅ **Debuggable**: Easy to test and troubleshoot

---

## Disadvantages

⚠️ **Computer must be on**: Task won't run if computer is off  
⚠️ **No cloud backup**: Runs only on your machine  
⚠️ **Manual updates**: Need to update code manually

---

## Next Steps

Once this is working reliably, consider:

1. **Upgrade to Paid Tier** ($0.03/month)
   - Re-enable GitHub Actions
   - No need to keep computer on
   - Cloud-based execution

2. **Set up VPS** (if you want cloud execution but free)
   - Rent a cheap VPS ($5/month)
   - Run the same batch script
   - Use Linux cron instead of Task Scheduler

3. **Add Monitoring**
   - Set up email notifications
   - Create a dashboard
   - Track success rates

---

## Summary

You've successfully set up local cron execution! 🎉

**What you did**:
1. ✅ Created batch scripts for automation
2. ✅ Tested manual execution
3. ✅ Configured Windows Task Scheduler
4. ✅ Set up daily automated runs
5. ✅ Disabled GitHub Actions schedule

**What happens now**:
- Every day at midnight (00:00 WIB)
- Your computer will automatically run the scraper
- Data will be collected and inserted into database
- No geographic restrictions
- Completely free

**Important**: Keep your computer on (or in sleep mode) for the task to run!

---

**Questions?** Check the troubleshooting section or review the logs in `infortic_scraper\logs\`.
