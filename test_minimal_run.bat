@echo off
REM ============================================================
REM Test Minimal Run - Scrape and Extract Minimal Data
REM ============================================================
REM This script tests the complete pipeline with minimal data:
REM - Scrapes only 1 account (infolomba)
REM - Only 1 scroll (1-2 posts)
REM - Extracts those posts with Gemini
REM - Inserts into database
REM - Safe to run without hitting daily limits
REM ============================================================

echo.
echo ============================================================
echo Infortic Scraper - Minimal Test Run
echo ============================================================
echo Started: %date% %time%
echo ============================================================
echo.
echo [INFO] This will scrape 1-2 posts from @infolomba only
echo [INFO] Safe to run without consuming daily API limits
echo.

REM Change to the script's directory
cd /d "%~dp0"

REM Check if Python virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo [ERROR] Please run test_setup.bat first
    exit /b 1
)

REM Backup original config
echo [STEP 1/6] Backing up scraper configuration...
if not exist "config\scraper.config.json.backup" (
    copy "config\scraper.config.json" "config\scraper.config.json.backup" >nul
    echo [SUCCESS] Config backed up
) else (
    echo [INFO] Backup already exists
)
echo.

REM Create minimal test config
echo [STEP 2/6] Creating minimal test configuration...
(
echo {
echo   "accounts": ["infolomba"],
echo   "scrollCount": 1,
echo   "deepScrapeMode": true,
echo   "downloadImages": false,
echo   "batchSize": 25,
echo   "delayBetweenRequests": 4
echo }
) > "config\scraper.config.json"
echo [SUCCESS] Minimal config created (1 account, 1 scroll, no images)
echo.

REM Activate virtual environment
echo [STEP 3/6] Activating Python virtual environment...
call "%cd%\venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    exit /b 1
)
echo [SUCCESS] Virtual environment activated
echo.

REM Run scraper
echo [STEP 4/6] Running Instagram scraper (minimal mode)...
echo.
cd scraper
node scraper.js
set SCRAPER_EXIT_CODE=%errorlevel%
cd ..

if %SCRAPER_EXIT_CODE% neq 0 (
    echo.
    echo [ERROR] Scraper failed with exit code: %SCRAPER_EXIT_CODE%
    goto restore_config
)
echo.
echo [SUCCESS] Scraping complete
echo.

REM Check if scraper output exists
if not exist "scraper\instagram_data.json" (
    echo [ERROR] Scraper output not found: scraper\instagram_data.json
    goto restore_config
)

REM Run extraction
echo [STEP 5/6] Running AI extraction (Gemini)...
echo.
python src\extraction\main.py scraper\instagram_data.json
set EXTRACTION_EXIT_CODE=%errorlevel%

if %EXTRACTION_EXIT_CODE% neq 0 (
    echo.
    echo [ERROR] Extraction failed with exit code: %EXTRACTION_EXIT_CODE%
    goto restore_config
)
echo.
echo [SUCCESS] Extraction complete
echo.

REM Find latest extracted file
for /f "delims=" %%i in ('dir /b /od "data\processed\extracted_data_*.json" 2^>nul') do set LATEST_FILE=%%i

if not defined LATEST_FILE (
    echo [ERROR] No extracted data file found
    goto restore_config
)

REM Run database insertion
echo [STEP 6/6] Running database insertion...
echo.
python src\database\main.py "data\processed\%LATEST_FILE%"
set INSERTION_EXIT_CODE=%errorlevel%

if %INSERTION_EXIT_CODE% neq 0 (
    echo.
    echo [ERROR] Insertion failed with exit code: %INSERTION_EXIT_CODE%
    goto restore_config
)
echo.
echo [SUCCESS] Insertion complete
echo.

:restore_config
REM Restore original config
echo [CLEANUP] Restoring original configuration...
if exist "config\scraper.config.json.backup" (
    copy "config\scraper.config.json.backup" "config\scraper.config.json" >nul
    del "config\scraper.config.json.backup" >nul
    echo [SUCCESS] Original config restored
)
echo.

REM Deactivate virtual environment
call "%cd%\venv\Scripts\deactivate.bat" 2>nul

echo.
echo ============================================================
echo Minimal Test Run Complete
echo ============================================================
echo Finished: %date% %time%
echo ============================================================
echo.

if %SCRAPER_EXIT_CODE% neq 0 (
    echo [RESULT] FAILED at scraping step
    exit /b %SCRAPER_EXIT_CODE%
)

if %EXTRACTION_EXIT_CODE% neq 0 (
    echo [RESULT] FAILED at extraction step
    exit /b %EXTRACTION_EXIT_CODE%
)

if %INSERTION_EXIT_CODE% neq 0 (
    echo [RESULT] FAILED at insertion step
    exit /b %INSERTION_EXIT_CODE%
)

echo [RESULT] SUCCESS - All steps completed
echo.
echo Next steps:
echo   1. Check database for new opportunities
echo   2. If successful, run full pipeline: run_daily_scraper.bat
echo   3. Set up Task Scheduler for daily automation
echo.
exit /b 0
