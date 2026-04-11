"""
Main Data Extraction Pipeline
"""

import json
import sys
import time
from pathlib import Path
from typing import Dict, List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.extraction.gemini_client import GeminiClient
from src.extraction.ocr_extractor import OCRExtractor
from src.extraction.utils.config import config
from src.extraction.utils.logger import setup_logger
from src.extraction.utils.helpers import extract_urls, extract_phone_numbers, get_timestamp, extract_registration_date_fallback, extract_organizer_fallback

logger = setup_logger('extractor')

class DataExtractor:
    def __init__(self):
        """Initialize data extractor"""
        config.validate()
        self.gemini_client = GeminiClient()
        self.ocr_extractor = OCRExtractor()
        
        # Track OCR usage
        self.ocr_attempts = 0
        self.ocr_successes = 0
    
    def process_account(self, account_name: str, captions: List[Dict]) -> List[Dict]:
        """Process captions for a single account with error handling"""
        
        total_captions = len(captions)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"[ACCOUNT] Processing @{account_name} ({total_captions} posts)")
        logger.info('='*60)
        
        all_results = []
        failed_batches = []
        fallback_stats = {
            'regex_dates': 0,
            'ocr_dates': 0,
            'regex_contacts': 0,
            'regex_organizers': 0,
            'regex_urls': 0
        }
        
        # Process in batches
        for i in range(0, total_captions, config.BATCH_SIZE):
            batch_num = (i // config.BATCH_SIZE) + 1
            total_batches = (total_captions + config.BATCH_SIZE - 1) // config.BATCH_SIZE
            
            batch = captions[i:i + config.BATCH_SIZE]
            
            logger.info(f"  [BATCH {batch_num}/{total_batches}] Posts {i+1}-{min(i+config.BATCH_SIZE, total_captions)}")
            
            try:
                # Process batch with Gemini
                batch_results = self.gemini_client.process_batch(batch)
                
                if batch_results:
                    # Add metadata to results with robust fallback logic
                    for j, result in enumerate(batch_results):
                        if j >= len(batch):
                            logger.warning(f"    [WARNING] Result index {j} exceeds batch size {len(batch)}")
                            continue
                            
                        original_caption = batch[j]['caption']
                        
                        # Store raw caption for frontend display
                        result['raw_caption'] = original_caption
                        
                        # ROBUST FALLBACK: Registration Date
                        if not result.get('registration_date'):
                            # Step 1: Try regex fallback on caption
                            fallback_date = extract_registration_date_fallback(original_caption)
                            if fallback_date:
                                result['registration_date'] = fallback_date
                                fallback_stats['regex_dates'] += 1
                                logger.debug(f"[FALLBACK-REGEX] Extracted registration_date: {fallback_date}")
                            
                            # Step 2: Try OCR fallback on image (if regex failed)
                            elif self.ocr_extractor.available and 'downloaded_image' in batch[j]:
                                self.ocr_attempts += 1
                                image_filename = batch[j]['downloaded_image']
                                
                                # Resolve full path to image
                                project_root = Path(__file__).parent.parent.parent
                                image_path = project_root / 'data' / 'images' / image_filename
                                
                                # Extract text from image
                                ocr_text = self.ocr_extractor.extract_text(str(image_path), timeout=5)
                                
                                if ocr_text:
                                    # Try to extract date from OCR text
                                    ocr_date = extract_registration_date_fallback(ocr_text)
                                    if ocr_date:
                                        result['registration_date'] = ocr_date
                                        self.ocr_successes += 1
                                        fallback_stats['ocr_dates'] += 1
                                        logger.debug(f"[FALLBACK-OCR] Extracted registration_date: {ocr_date}")
                                    else:
                                        logger.debug(f"[FALLBACK-OCR] No date found in OCR text")
                                else:
                                    logger.debug(f"[FALLBACK-OCR] No text extracted from image")
                        
                        # ROBUST FALLBACK: Contact Phone
                        if not result.get('contact'):
                            phones = extract_phone_numbers(original_caption)
                            if phones:
                                result['contact'] = phones[0]
                                fallback_stats['regex_contacts'] += 1
                                logger.debug(f"[FALLBACK] Extracted contact via regex: {phones[0]}")
                        
                        # ROBUST FALLBACK: Organizer
                        if not result.get('organizer'):
                            fallback_organizer = extract_organizer_fallback(original_caption, account_name)
                            if fallback_organizer:
                                result['organizer'] = fallback_organizer
                                fallback_stats['regex_organizers'] += 1
                                logger.debug(f"[FALLBACK] Extracted organizer via fallback: {fallback_organizer}")
                        
                        # ROBUST FALLBACK: Registration URL
                        if not result.get('registration_url'):
                            urls = extract_urls(original_caption)
                            if urls:
                                # Prioritize registration-related URLs
                                registration_keywords = ['daftar', 'regist', 'form', 'pendaftaran', 'bit.ly', 'forms.gle', 'linktr.ee', 's.id']
                                
                                best_url = None
                                for url in urls:
                                    url_lower = url.lower()
                                    if any(kw in url_lower for kw in registration_keywords):
                                        best_url = url
                                        break
                                    url_index = original_caption.lower().find(url.lower())
                                    if url_index > 0:
                                        context = original_caption[max(0, url_index-50):url_index].lower()
                                        if any(kw in context for kw in registration_keywords):
                                            best_url = url
                                            break
                                
                                if not best_url and urls:
                                    best_url = urls[0]
                                
                                if best_url:
                                    result['registration_url'] = best_url
                                    fallback_stats['regex_urls'] += 1
                                    logger.debug(f"[FALLBACK] Extracted registration_url via regex: {best_url}")
                        
                        # Add source metadata
                        result['source_url'] = batch[j]['url']
                        result['source_account'] = account_name
                        result['image_url'] = batch[j].get('image_url')
                        
                        # Add downloaded image filename if exists
                        if 'downloaded_image' in batch[j]:
                            result['downloaded_image'] = batch[j]['downloaded_image']
                    
                    all_results.extend(batch_results)
                    logger.info(f"    [GEMINI] Response received: {len(batch_results)}/{len(batch)} items extracted")
                else:
                    logger.warning(f"    [WARNING] Batch returned no results")
                    failed_batches.append({
                        'batch_num': batch_num,
                        'posts': [p['post_id'] for p in batch]
                    })
                
            except KeyboardInterrupt:
                logger.warning(f"    [INTERRUPT] Processing interrupted at batch {batch_num}/{total_batches}")
                logger.info(f"    [SAVE] Saving {len(all_results)} results collected so far...")
                raise
                
            except Exception as e:
                logger.error(f"    [ERROR] Error processing batch {batch_num}: {e}")
                failed_batches.append({
                    'batch_num': batch_num,
                    'posts': [p['post_id'] for p in batch],
                    'error': str(e)
                })
                continue
            
            # Rate limiting
            if i + config.BATCH_SIZE < total_captions:
                logger.info(f"    [WAIT] Rate limiting: {config.DELAY_BETWEEN_REQUESTS}s delay...")
                time.sleep(config.DELAY_BETWEEN_REQUESTS)
        
        # Show fallback usage summary
        total_fallbacks = sum(fallback_stats.values())
        if total_fallbacks > 0:
            logger.info(f"  [FALLBACK] Applied fallbacks:")
            if fallback_stats['regex_dates'] > 0:
                logger.info(f"    - Regex Dates:      {fallback_stats['regex_dates']} extracted")
            if fallback_stats['ocr_dates'] > 0:
                logger.info(f"    - OCR Dates:        {fallback_stats['ocr_dates']} extracted")
            if fallback_stats['regex_contacts'] > 0:
                logger.info(f"    - Regex Contacts:   {fallback_stats['regex_contacts']} extracted")
            if fallback_stats['regex_organizers'] > 0:
                logger.info(f"    - Regex Organizers: {fallback_stats['regex_organizers']} extracted")
            if fallback_stats['regex_urls'] > 0:
                logger.info(f"    - Regex URLs:       {fallback_stats['regex_urls']} extracted")
        
        success_rate = len(all_results)/total_captions*100 if total_captions > 0 else 0
        logger.info(f"\n[ACCOUNT SUMMARY] @{account_name}:")
        logger.info(f"  Posts Processed:    {total_captions}")
        logger.info(f"  Successfully Extracted: {len(all_results)}/{total_captions} ({success_rate:.1f}%)")
        if failed_batches:
            logger.warning(f"  Failed Batches:     {len(failed_batches)}")
        if total_fallbacks > 0:
            logger.info(f"  Fallbacks Applied:  {total_fallbacks} times")
        
        return all_results
    
    def process_all_accounts(self, instagram_data: Dict) -> List[Dict]:
        """Process all accounts in the Instagram data"""
        
        # Detect all accounts
        accounts = {k: v for k, v in instagram_data.items() if isinstance(v, list) and len(v) > 0}
        
        if not accounts:
            logger.error("[ERROR] No accounts found in instagram_data!")
            return []
        
        total_posts = sum(len(posts) for posts in accounts.values())
        
        logger.info(f"\n{'='*60}")
        logger.info(f"[EXTRACTION] AI Extraction Pipeline Starting...")
        logger.info('='*60)
        logger.info(f"[INPUT] Detected {len(accounts)} account(s), {total_posts} total posts")
        for account_name, posts in accounts.items():
            logger.info(f"  - @{account_name}: {len(posts)} posts")
        logger.info(f"[CONFIG] Model: {config.GEMINI_MODEL} | Batch size: {config.BATCH_SIZE} | Rate limit: {config.DELAY_BETWEEN_REQUESTS}s")
        
        all_results = []
        
        # Process each account
        for account_index, (account_name, captions) in enumerate(accounts.items(), 1):
            account_results = self.process_account(account_name, captions)
            all_results.extend(account_results)
            
            # Small delay between accounts
            if account_index < len(accounts):
                logger.info(f"[WAIT] Pausing 2s before next account...")
                time.sleep(2)
        
        success_rate = len(all_results)/total_posts*100 if total_posts > 0 else 0
        logger.info(f"\n{'='*60}")
        logger.info(f"[COMPLETE] All Accounts Processed")
        logger.info('='*60)
        logger.info(f"[SUMMARY] Extraction Results:")
        logger.info(f"  Total Posts:        {total_posts}")
        logger.info(f"  Successfully Extracted: {len(all_results)}/{total_posts} ({success_rate:.1f}%)")
        
        return all_results
    
    def validate_results(self, results: List[Dict]) -> Dict:
        """Validate extraction results and provide quality metrics"""
        
        total = len(results)
        
        metrics = {
            'total_processed': total,
            'has_title': sum(1 for r in results if r.get('title')),
            'has_category': sum(1 for r in results if r.get('category')),
            'has_audiences': sum(1 for r in results if r.get('audiences')),
            'has_registration_date': sum(1 for r in results if r.get('registration_date')),
            'has_contact': sum(1 for r in results if r.get('contact')),
            'has_event_type': sum(1 for r in results if r.get('event_type')),
            'has_fee_type': sum(1 for r in results if r.get('fee_type')),
            'has_organizer': sum(1 for r in results if r.get('organizer')),
            'has_registration_url': sum(1 for r in results if r.get('registration_url')),
        }
        
        logger.info(f"\n[QUALITY] Data Completeness:")
        logger.info(f"  Required Fields:")
        logger.info(f"    - Title:            {metrics['has_title']}/{total} ({metrics['has_title']/total*100:.1f}%)")
        logger.info(f"    - Category:         {metrics['has_category']}/{total} ({metrics['has_category']/total*100:.1f}%)")
        logger.info(f"    - Audiences:        {metrics['has_audiences']}/{total} ({metrics['has_audiences']/total*100:.1f}%)")
        logger.info(f"")
        logger.info(f"  Optional Fields:")
        logger.info(f"    - Registration Date: {metrics['has_registration_date']}/{total} ({metrics['has_registration_date']/total*100:.1f}%)")
        logger.info(f"    - Contact:          {metrics['has_contact']}/{total} ({metrics['has_contact']/total*100:.1f}%)")
        logger.info(f"    - Organizer:        {metrics['has_organizer']}/{total} ({metrics['has_organizer']/total*100:.1f}%)")
        logger.info(f"    - Registration URL: {metrics['has_registration_url']}/{total} ({metrics['has_registration_url']/total*100:.1f}%)")
        logger.info(f"    - Event Type:       {metrics['has_event_type']}/{total} ({metrics['has_event_type']/total*100:.1f}%)")
        logger.info(f"    - Fee Type:         {metrics['has_fee_type']}/{total} ({metrics['has_fee_type']/total*100:.1f}%)")
        
        return metrics

def save_results(results: List[Dict], metrics: Dict = None, partial: bool = False) -> tuple:
    """Save extraction results and metrics to files"""
    
    timestamp = get_timestamp()
    prefix = 'partial_' if partial else 'extracted_data_'
    
    # Save results
    output_file = config.PROCESSED_DIR / f'{prefix}{timestamp}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"[SAVE] Results saved: {output_file}")
    
    # Save metrics if provided
    if metrics:
        metrics_file = config.PROCESSED_DIR / f'extraction_metrics_{timestamp}.json'
        with open(metrics_file, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=2)
        logger.info(f"[SAVE] Metrics saved: {metrics_file}")
        return output_file, metrics_file
    
    return output_file, None

def main():
    """Main execution function with comprehensive error handling"""
    
    logger.info(f"\n{'='*60}")
    logger.info('[EXTRACTION] Instagram Data Extraction Starting...')
    logger.info('='*60 + '\n')
    
    results = []
    
    try:
        # Get input file from command line or use latest
        if len(sys.argv) > 1:
            input_file = Path(sys.argv[1])
        else:
            # Find latest file in raw directory
            raw_files = list(config.OUTPUT_DIR.glob('instagram_data_*.json'))
            if not raw_files:
                logger.error("[ERROR] No input files found in data/raw/")
                logger.info("Usage: python src/extraction/main.py [input_file]")
                sys.exit(1)
            input_file = max(raw_files, key=lambda p: p.stat().st_mtime)
        
        logger.info(f"[LOAD] Loading Instagram data from: {input_file}")
        
        try:
            with open(input_file, 'r', encoding='utf-8') as f:
                instagram_data = json.load(f)
            
            total_posts = sum(len(v) for v in instagram_data.values() if isinstance(v, list))
            logger.info(f"[SUCCESS] Loaded {total_posts} posts\n")
            
        except FileNotFoundError:
            logger.error(f"[ERROR] File not found: {input_file}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"[ERROR] Invalid JSON format: {e}")
            sys.exit(1)
        
        # Process all accounts
        extractor = DataExtractor()
        results = extractor.process_all_accounts(instagram_data)
        
        if not results:
            logger.error("[ERROR] No results to save!")
            sys.exit(1)
        
        # Validate results
        metrics = extractor.validate_results(results)
        
        # Save results
        output_file, metrics_file = save_results(results, metrics, partial=False)
        
        logger.info(f"\n{'='*60}")
        logger.info("[COMPLETE] Extraction Complete!")
        logger.info('='*60)
        logger.info(f"[SUMMARY] Final Statistics:")
        logger.info(f"  Total Posts:        {total_posts}")
        logger.info(f"  Successfully Extracted: {len(results)}/{total_posts} ({len(results)/total_posts*100:.1f}%)")
        logger.info(f"  Output File:        {output_file.name}")
        logger.info(f"  Duration:           {extractor.gemini_client.total_time:.1f}s" if hasattr(extractor.gemini_client, 'total_time') else "")
        logger.info('='*60)
        logger.info(f"\n[NEXT] Database Insertion:")
        logger.info(f"  python src/database/main.py {output_file}\n")
        
    except KeyboardInterrupt:
        logger.warning(f"\n\n{'='*60}")
        logger.warning("[INTERRUPT] Extraction interrupted by user")
        logger.warning('='*60)
        
        if results:
            logger.info(f"\n[SAVE] Saving {len(results)} partial results...")
            try:
                output_file, _ = save_results(results, partial=True)
                logger.info(f"[SUCCESS] Partial results saved: {output_file.name}")
                logger.info(f"  You can resume or use partial data")
            except Exception as e:
                logger.error(f"[ERROR] Failed to save partial results: {e}")
        else:
            logger.warning("[WARNING] No results to save")
        
        sys.exit(130)
        
    except Exception as e:
        logger.error(f"\n{'='*60}")
        logger.error(f"[ERROR] Fatal Error: {type(e).__name__}: {e}")
        logger.error('='*60)
        import traceback
        logger.debug(traceback.format_exc())
        
        if results:
            logger.info(f"\n[SAVE] Attempting to save {len(results)} partial results...")
            try:
                output_file, _ = save_results(results, partial=True)
                logger.info(f"[SUCCESS] Partial results saved: {output_file.name}")
            except Exception as save_error:
                logger.error(f"[ERROR] Failed to save partial results: {save_error}")
        
        sys.exit(1)

if __name__ == '__main__':
    main()
