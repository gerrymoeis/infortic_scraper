@echo off
REM ============================================================
REM Test Setup Script
REM Verifies that everything is configured correctly
REM ============================================================

echo.
echo ============================================================
echo Infortic Scraper - Setup Verification
echo ============================================================
echo.

REM Change to script directory
cd /d "%~dp0"

echo [TEST 1/6] Checking directory...
echo Current directory: %cd%
if not exist "run.py" (
    echo [FAIL] run.py not found! Are you in the correct directory?
    exit /b 1
)
echo [PASS] Directory is correct
echo.

echo [TEST 2/6] Checking virtual environment...
if not exist "venv\Scripts\python.exe" (
    echo [FAIL] Virtual environment not found!
    echo.
    echo To create virtual environment:
    echo   1. Open PowerShell or Command Prompt
    echo   2. Navigate to the infortic_scraper directory
    echo   3. Run: python -m venv venv
    echo   4. Run: venv\Scripts\activate
    echo   5. Run: pip install -r requirements.txt
    echo.
    exit /b 1
)
echo [PASS] Virtual environment exists
echo.

echo [TEST 3/6] Checking Python packages...
call "%cd%\venv\Scripts\activate.bat"
python -c "import google.generativeai; print('[PASS] Required packages installed')" 2>nul
if errorlevel 1 (
    echo [FAIL] Required packages not installed!
    echo.
    echo To install packages:
    echo   1. Run: venv\Scripts\activate
    echo   2. Run: pip install -r requirements.txt
    echo   3. Run: playwright install chromium
    echo.
    exit /b 1
)
echo.

echo [TEST 4/6] Checking config/.env file...
if not exist "config\.env" (
    echo [FAIL] config/.env file not found!
    echo.
    echo Please create config/.env with:
    echo   - GEMINI_API_KEY=your_keys_here
    echo   - DATABASE_URL=your_database_url
    echo.
    exit /b 1
)
echo [PASS] config/.env exists
echo.

echo [TEST 5/6] Checking Gemini API keys...
python -c "from src.extraction.utils.config import config; print(f'[INFO] Found {len(config.GEMINI_API_KEYS)} API keys'); print('[PASS] API keys loaded')" 2>nul
if errorlevel 1 (
    echo [FAIL] Could not load API keys from config/.env
    exit /b 1
)
echo.

echo [TEST 6/6] Checking database connection...
python -c "import os; from dotenv import load_dotenv; load_dotenv('config/.env'); from src.database.client import DatabaseClient; db = DatabaseClient(os.getenv('DATABASE_URL')); db.connect(); db.close(); print('[PASS] Database connection successful')" 2>nul
if errorlevel 1 (
    echo [FAIL] Could not connect to database
    echo [INFO] Check your DATABASE_URL in config/.env
    exit /b 1
)
echo.

call "%cd%\venv\Scripts\deactivate.bat" 2>nul

echo ============================================================
echo All Tests Passed!
echo ============================================================
echo.
echo Your setup is ready. You can now:
echo   1. Test with minimal data: test_minimal_run.bat
echo   2. Run full pipeline: run_daily_scraper.bat
echo   3. Set up Task Scheduler for automation
echo.
echo ============================================================
echo.
