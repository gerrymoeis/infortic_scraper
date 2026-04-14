# Windows Task Scheduler Setup Guide

## Quick Setup (5 minutes)

### Step 1: Open Task Scheduler
1. Press `Win + R`
2. Type `taskschd.msc`
3. Press Enter

### Step 2: Create New Task
1. Click "Create Task" (not "Create Basic Task")
2. Name: `Infortic Daily Scraper`
3. Description: `Daily Instagram scraping at 9 PM WIB`
4. ✅ Check "Run whether user is logged on or not"
5. ✅ Check "Run with highest privileges"
6. Configure for: Windows 10

### Step 3: Triggers Tab
1. Click "New..."
2. Begin the task: **On a schedule**
3. Settings: **Daily**
4. Start: **21:00:00** (9 PM)
5. Recur every: **1 days**
6. ✅ Check "Enabled"
7. Click OK

### Step 4: Actions Tab
1. Click "New..."
2. Action: **Start a program**
3. Program/script: `cmd.exe`
4. Add arguments: `/c "cd /d "D:\Gerry\Programmer\Best Terbaik(2026)\Tools\Project Instagram Scraper\infortic_scraper" && run_daily_scraper.bat"`
   
   **IMPORTANT**: Replace the path with your actual path to `infortic_scraper` folder
   
5. Click OK

### Step 5: Conditions Tab
1. ✅ Check "Start only if the computer is on AC power"
2. ✅ Check "Wake the computer to run this task"
3. ✅ Uncheck "Stop if the computer switches to battery power"
4. ✅ Check "Start the task only if the computer is on AC power" (for laptops)

### Step 6: Settings Tab
1. ✅ Check "Allow task to be run on demand"
2. ✅ Check "Run task as soon as possible after a scheduled start is missed"
3. ✅ Check "If the task fails, restart every: 10 minutes"
4. Attempt to restart up to: **3 times**
5. Stop the task if it runs longer than: **2 hours**
6. If the running task does not end when requested: **Stop the existing instance**

### Step 7: Save and Test
1. Click OK
2. Enter your Windows password when prompted
3. Right-click the task → "Run" to test immediately
4. Check logs in `infortic_scraper/logs/` folder

## Important Notes

### ⚠️ Computer Must Be Online
- **YES**, your laptop/PC must be:
  - ✅ Powered on (or in sleep mode with "Wake to run" enabled)
  - ✅ Connected to internet
  - ✅ At 21:00 WIB (9 PM Indonesia time) every day

### ⚠️ Instagram Session
- Instagram session expires after ~60 days
- If scraper fails with "Not logged in" error:
  1. Run scraper manually once: `cd scraper && node scraper.js`
  2. Login when prompted
  3. Session will be saved automatically

### ⚠️ API Keys
- Free Gemini API keys have daily limits
- System will automatically rotate between keys
- If all keys fail, check Google AI Studio for quota

## Monitoring

### Check if Task is Running
```powershell
Get-ScheduledTask -TaskName "Infortic Daily Scraper"
```

### View Last Run Result
```powershell
Get-ScheduledTaskInfo -TaskName "Infortic Daily Scraper"
```

### Check Logs
- Location: `infortic_scraper/logs/`
- Latest log: `pipeline_YYYYMMDD.log`
- Check for errors or success messages

## Troubleshooting

### Task Doesn't Run
1. Check if computer was online at 21:00 WIB
2. Check Task Scheduler History (enable in Task Scheduler → View → Show History)
3. Verify path in Actions tab is correct
4. Check Windows Event Viewer for errors

### Scraper Fails
1. Check logs in `infortic_scraper/logs/`
2. Run manually to see error: `run_daily_scraper.bat`
3. Common issues:
   - Instagram session expired → Login again
   - API quota exceeded → Wait 24 hours or add more keys
   - Database connection failed → Check DATABASE_URL in config/.env

### Pipeline Runs But No Data
1. Check if Instagram accounts posted new content
2. Verify extraction logs for Gemini API errors
3. Check database insertion logs for validation errors

## Alternative: Run Manually

If you prefer to run manually instead of scheduling:

```batch
cd "D:\Gerry\Programmer\Best Terbaik(2026)\Tools\Project Instagram Scraper\infortic_scraper"
run_daily_scraper.bat
```

## Timezone Note

**21:00 WIB = 14:00 UTC**

Windows Task Scheduler uses your local time (WIB), so setting 21:00 will run at 9 PM Indonesia time automatically.

## Success Indicators

After successful run, you should see:
- ✅ New log file in `logs/` folder
- ✅ New opportunities in database
- ✅ Exit code 0 in Task Scheduler history
- ✅ Summary showing scraped/extracted/inserted counts

## Next Steps

1. ✅ Set up Task Scheduler (follow steps above)
2. ✅ Test run manually first
3. ✅ Wait for first scheduled run at 21:00 WIB
4. ✅ Check logs next morning
5. ✅ Monitor for first week to ensure stability
