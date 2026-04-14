#!/usr/bin/env python3
"""
Main Pipeline Runner
Orchestrates the complete scraping, extraction, and insertion pipeline
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime
import json

# Add to path
sys.path.append(str(Path(__file__).parent))

from src.extraction.utils.logger import setup_logger

logger = setup_logger('pipeline')

def run_command(cmd, cwd=None, description="", step_num=0, total_steps=0):
    """Run a command and return success status"""
    step_label = f"[STEP {step_num}/{total_steps}]" if step_num > 0 else "[STEP]"
    
    logger.info(f"\n{'='*60}")
    logger.info(f"{step_label} {description}")
    logger.info('='*60)
    logger.info(f"[COMMAND] {' '.join(cmd)}")
    
    step_start = datetime.now()
    
    try:
        # Use Popen to stream output in real-time (prevents hanging)
        process = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True,
            encoding='utf-8',
            errors='replace'  # Replace invalid characters instead of crashing
        )
        
        # Stream output line by line
        for line in process.stdout:
            print(line, end='')
        
        # Wait for process to complete
        return_code = process.wait()
        
        step_duration = datetime.now() - step_start
        
        if return_code == 0:
            logger.info(f"[COMPLETE] {description}: SUCCESS ({step_duration.total_seconds():.1f}s)")
            return True
        else:
            logger.error(f"[FAILED] {description}: FAILED ({step_duration.total_seconds():.1f}s)")
            logger.error(f"[ERROR] Exit code: {return_code}")
            return False
        
    except Exception as e:
        step_duration = datetime.now() - step_start
        logger.error(f"[FAILED] {description}: FAILED ({step_duration.total_seconds():.1f}s)")
        logger.error(f"[ERROR] {str(e)}")
        return False

def find_latest_extracted_file():
    """Find the most recent extracted data file"""
    processed_dir = Path(__file__).parent / 'data' / 'processed'
    
    if not processed_dir.exists():
        return None
    
    files = list(processed_dir.glob('extracted_data_*.json'))
    
    if not files:
        return None
    
    # Sort by modification time, most recent first
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    return files[0]

def main():
    """Run the complete pipeline"""
    
    start_time = datetime.now()
    
    logger.info("\n" + "="*60)
    logger.info("[PIPELINE] Infortic Scraper - Complete Pipeline")
    logger.info("="*60)
    logger.info(f"[PIPELINE] Started: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info("="*60 + "\n")
    
    project_root = Path(__file__).parent
    scraper_dir = project_root / 'scraper'
    
    total_steps = 5  # Updated from 4 to 5 (added cleanup step)
    step_results = {}
    
    # Step 1: Run Instagram Scraper
    logger.info("[PIPELINE] Starting pipeline execution...")
    if not run_command(
        ['node', 'scraper.js'],
        cwd=scraper_dir,
        description="Instagram Scraping",
        step_num=1,
        total_steps=total_steps
    ):
        logger.error("[PIPELINE] Pipeline failed at scraping step")
        return False
    
    step_results['scraping'] = 'SUCCESS'
    
    # Check if scraper output exists
    scraper_output = scraper_dir / 'instagram_data.json'
    if not scraper_output.exists():
        logger.error(f"[ERROR] Scraper output not found: {scraper_output}")
        return False
    
    # Get post count from scraper output
    try:
        with open(scraper_output, 'r', encoding='utf-8') as f:
            scraper_data = json.load(f)
            total_posts = sum(len(v) for v in scraper_data.values() if isinstance(v, list))
            logger.info(f"[OUTPUT] Scraped data: {scraper_output.name} ({total_posts} posts)")
    except Exception as e:
        logger.warning(f"[WARNING] Could not read scraper output: {e}")
        total_posts = 0
    
    # Step 2: Run Extraction Pipeline
    if not run_command(
        ['python', 'src/extraction/main.py', str(scraper_output)],
        cwd=project_root,
        description="AI Extraction (Gemini + OCR)",
        step_num=2,
        total_steps=total_steps
    ):
        logger.error("[PIPELINE] Pipeline failed at extraction step")
        return False
    
    step_results['extraction'] = 'SUCCESS'
    
    # Find the latest extracted file
    extracted_file = find_latest_extracted_file()
    if not extracted_file:
        logger.error("[ERROR] No extracted data file found")
        return False
    
    # Get record count from extracted file
    try:
        with open(extracted_file, 'r', encoding='utf-8') as f:
            extracted_data = json.load(f)
            extracted_count = len(extracted_data)
            logger.info(f"[OUTPUT] Extracted data: {extracted_file.name} ({extracted_count} records)")
    except Exception as e:
        logger.warning(f"[WARNING] Could not read extracted file: {e}")
        extracted_count = 0
    
    # Step 3: Run Database Insertion
    if not run_command(
        ['python', 'src/database/main.py', str(extracted_file)],
        cwd=project_root,
        description="Database Insertion",
        step_num=3,
        total_steps=total_steps
    ):
        logger.error("[PIPELINE] Pipeline failed at database insertion step")
        return False
    
    step_results['insertion'] = 'SUCCESS'
    
    # Step 4: Cleanup Expired Opportunities
    if not run_command(
        ['python', 'scripts/mark_expired.py'],
        cwd=project_root,
        description="Cleanup Expired Opportunities",
        step_num=4,
        total_steps=total_steps
    ):
        logger.warning("[WARNING] Cleanup step failed, but pipeline can continue")
        step_results['cleanup'] = 'FAILED'
    else:
        step_results['cleanup'] = 'SUCCESS'
    
    # Step 5: Verify Results
    if not run_command(
        ['python', 'scripts/verify.py'],
        cwd=project_root,
        description="Results Verification",
        step_num=5,
        total_steps=total_steps
    ):
        logger.warning("[WARNING] Verification step failed, but pipeline completed")
        step_results['verification'] = 'FAILED'
    else:
        step_results['verification'] = 'SUCCESS'
    
    # Pipeline complete
    end_time = datetime.now()
    duration = end_time - start_time
    
    logger.info("\n" + "="*60)
    logger.info("[COMPLETE] Pipeline Execution Complete!")
    logger.info("="*60)
    logger.info(f"[SUMMARY] Pipeline Summary:")
    logger.info(f"  Started:  {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Finished: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Duration: {duration.total_seconds():.1f}s ({duration.total_seconds()//60:.0f}m {duration.total_seconds()%60:.0f}s)")
    logger.info(f"")
    logger.info(f"[SUMMARY] Step Results:")
    logger.info(f"  1. Scraping:      {step_results.get('scraping', 'UNKNOWN')}")
    logger.info(f"  2. Extraction:    {step_results.get('extraction', 'UNKNOWN')}")
    logger.info(f"  3. Insertion:     {step_results.get('insertion', 'UNKNOWN')}")
    logger.info(f"  4. Cleanup:       {step_results.get('cleanup', 'UNKNOWN')}")
    logger.info(f"  5. Verification:  {step_results.get('verification', 'UNKNOWN')}")
    logger.info(f"")
    if total_posts > 0 and extracted_count > 0:
        logger.info(f"[SUMMARY] Data Flow:")
        logger.info(f"  Scraped:          {total_posts} posts")
        logger.info(f"  Extracted:        {extracted_count} records")
        logger.info(f"  Extraction Rate:  {extracted_count/total_posts*100:.1f}%")
    logger.info("="*60 + "\n")
    
    return True

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
