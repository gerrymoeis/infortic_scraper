@echo off
REM ============================================================
REM Infortic Scraper - Daily Automated Run
REM ============================================================
REM This script runs the complete scraping pipeline:
REM 1. Scrapes Instagram accounts
REM 2. Extracts data with Gemini AI
REM 3. Inserts into database
REM 4. Cleans up expired opportunities
REM 5. Verifies results
REM ============================================================

echo.
echo ============================================================
echo Infortic Scraper - Daily Run
echo ============================================================
echo Started: %date% %time%
echo ============================================================
echo.

REM Change to the script's directory
cd /d "%~dp0"

REM Check if Python virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo [ERROR] Please run: python -m venv venv
    echo [ERROR] Then: venv\Scripts\activate
    echo [ERROR] Then: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo [STEP 1/2] Activating Python virtual environment...
call venv\Scripts\activate.bat

REM Check if activation was successful
if errorlevel 1 (
    echo [ERROR] Failed to activate virtual environment
    pause
    exit /b 1
)

echo [SUCCESS] Virtual environment activated
echo.

REM Run the pipeline
echo [STEP 2/2] Running scraper pipeline...
echo.
python run.py

REM Capture exit code
set PIPELINE_EXIT_CODE=%errorlevel%

REM Deactivate virtual environment
call venv\Scripts\deactivate.bat 2>nul

echo.
echo ============================================================
echo Pipeline Execution Complete
echo ============================================================
echo Finished: %date% %time%
echo Exit Code: %PIPELINE_EXIT_CODE%
echo ============================================================
echo.

REM Exit with the pipeline's exit code
exit /b %PIPELINE_EXIT_CODE%
