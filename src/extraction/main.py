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
from src.extraction.organizer_validator import OrganizerValidator
from src.extraction.checkpoint_manager import CheckpointManager
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
        self.organizer_validator = OrganizerValidator()
        self.checkpoint_manager = CheckpointManager(config.PROCESSED_DIR)
        
        # Track OCR usage
        self.ocr_attempts = 0
        self.ocr_successes = 0
    
    def extract_all_ocr_texts(self, captions: List[Dict]) -> Dict[str, tuple]:
        """
        Extract OCR text from ALL images BEFORE processing with Gemini (Phase A Enhancement)
        This is the key change - OCR happens FIRST, not as fallback
        
        Args:
            captions: List of caption dictionaries with image info
        
        Returns:
            Dictionary mapping post_id to (ocr_text, confidence_score)
        """
        logger.info(f"[OCR] Extracting text from {len(captions)} images...")
        
        ocr_texts = {}
        ocr_stats = {
            'total_images': 0,
            'successful': 0,
            'failed': 0,
            'no_image': 0,
            'total_chars': 0,
            'avg_confidence': []
        }
        
        for item in captions:
            if 'downloaded_image' not in item:
                ocr_stats['no_image'] += 1
                continue
            
            ocr_stats['total_images'] += 1
            image_filename = item['downloaded_image']
            post_id = item['post_id']
            
            # Resolve full path to image
            project_root = Path(__file__).parent.parent.parent
            # FIX: Images are in scraper/instagram_images/, not data/images/
            image_path = project_root / 'scraper' / 'instagram_images' / image_filename
            
            if not image_path.exists():
                logger.warning(f"[OCR] Image not found: {image_filename}")
                ocr_stats['failed'] += 1
                continue
            
            # Extract with preprocessing and confidence
            ocr_text, confidence = self.ocr_extractor.extract_with_confidence(
                str(image_path),
                timeout=10
            )
            
            if ocr_text:
                ocr_texts[post_id] = (ocr_text, confidence)
                ocr_stats['successful'] += 1
                ocr_stats['total_chars'] += len(ocr_text)
                ocr_stats['avg_confidence'].append(confidence)
                logger.debug(f"[OCR] {post_id}: {len(ocr_text)} chars, {confidence}% confidence")
            else:
                ocr_stats['failed'] += 1
                logger.debug(f"[OCR] {post_id}: No text extracted")
        
        # Log summary
        success_rate = (ocr_stats['successful'] / ocr_stats['total_images'] * 100) if ocr_stats['total_images'] > 0 else 0
        avg_conf = sum(ocr_stats['avg_confidence']) // len(ocr_stats['avg_confidence']) if ocr_stats['avg_confidence'] else 0
        
        logger.info(f"[OCR] Extraction complete:")
        logger.info(f"  Total images:      {ocr_stats['total_images']}")
        logger.info(f"  Successful:        {ocr_stats['successful']} ({success_rate:.1f}%)")
        logger.info(f"  Failed:            {ocr_stats['failed']}")
        logger.info(f"  No image:          {ocr_stats['no_image']}")
        logger.info(f"  Total chars:       {ocr_stats['total_chars']}")
        logger.info(f"  Avg confidence:    {avg_conf}%")
        
        return ocr_texts
    
    def process_account(self, account_name: str, captions: List[Dict]) -> List[Dict]:
        """Process captions for a single account with error handling"""
        
        total_captions = len(captions)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"[ACCOUNT] Processing @{account_name} ({total_captions} posts)")
        logger.info('='*60)
        
        # PHASE A CHANGE: Extract OCR text from ALL images FIRST
        ocr_texts = {}
        if self.ocr_extractor.available:
            ocr_texts = self.extract_all_ocr_texts(captions)
        else:
            logger.warning("[OCR] OCR not available - continuing without OCR enhancement")
            logger.warning("[OCR] Install Tesseract OCR for better extraction accuracy")
        
        all_results = []
        failed_batches = []
        fallback_stats = {
            'regex_dates': 0,
            'ocr_dates': 0,
            'regex_contacts': 0,
            'ocr_contacts': 0,  # NEW: Track OCR contact extractions
            'regex_organizers': 0,
            'ocr_organizers': 0,  # NEW: Track OCR organizer extractions
            'regex_urls': 0,
            'ocr_urls': 0  # NEW: Track OCR URL extractions
        }
        
        # Process in batches
        for i in range(0, total_captions, config.BATCH_SIZE):
            batch_num = (i // config.BATCH_SIZE) + 1
            total_batches = (total_captions + config.BATCH_SIZE - 1) // config.BATCH_SIZE
            
            batch = captions[i:i + config.BATCH_SIZE]
            
            logger.info(f"  [BATCH {batch_num}/{total_batches}] Posts {i+1}-{min(i+config.BATCH_SIZE, total_captions)}")
            
            try:
                # Process batch with Gemini (SEND IMAGES for better accuracy!)
                batch_results = self.gemini_client.process_batch(batch, ocr_texts, send_images=True)
                
                # Add delay between batches to avoid overwhelming API (except for last batch)
                if batch_num < total_batches:
                    import time
                    delay = config.DELAY_BETWEEN_REQUESTS
                    logger.info(f"  [WAIT] Waiting {delay}s before next batch...")
                    time.sleep(delay)
                
                if batch_results:
                    # Add metadata to results with robust fallback logic
                    for j, result in enumerate(batch_results):
                        if j >= len(batch):
                            logger.warning(f"    [WARNING] Result index {j} exceeds batch size {len(batch)}")
                            continue
                            
                        original_caption = batch[j]['caption']
                        
                        # Store raw caption for frontend display
                        result['raw_caption'] = original_caption
                        
                        # Get post_id for OCR text lookup
                        post_id = batch[j]['post_id']
                        ocr_text = None
                        if post_id in ocr_texts:
                            ocr_text, ocr_confidence = ocr_texts[post_id]
                        
                        # ROBUST FALLBACK: Title (PHASE C PART 3)
                        if not result.get('title') or not result.get('title').strip():
                            # Try to extract from first line of caption
                            if original_caption:
                                first_line = original_caption.split('\n')[0].strip()
                                # Remove common prefixes
                                for prefix in ['📢', '🎉', '🔥', '✨', '⚡', '🎯', '📣']:
                                    first_line = first_line.replace(prefix, '').strip()
                                
                                if first_line and len(first_line) >= 5:
                                    # Use first 100 characters as title
                                    result['title'] = first_line[:100]
                                    fallback_stats['title_fallback'] = fallback_stats.get('title_fallback', 0) + 1
                                    logger.debug(f"[FALLBACK-CAPTION] Extracted title: {result['title'][:50]}...")
                            
                            # If still no title, try OCR text
                            if (not result.get('title') or not result.get('title').strip()) and ocr_text:
                                first_line_ocr = ocr_text.split('\n')[0].strip()
                                if first_line_ocr and len(first_line_ocr) >= 5:
                                    result['title'] = first_line_ocr[:100]
                                    fallback_stats['title_fallback_ocr'] = fallback_stats.get('title_fallback_ocr', 0) + 1
                                    logger.debug(f"[FALLBACK-OCR] Extracted title: {result['title'][:50]}...")
                        
                        # ROBUST FALLBACK: Registration Date
                        if not result.get('registration_date'):
                            # Step 1: Try regex fallback on caption
                            fallback_date = extract_registration_date_fallback(original_caption)
                            if fallback_date:
                                result['registration_date'] = fallback_date
                                fallback_stats['regex_dates'] += 1
                                logger.debug(f"[FALLBACK-REGEX] Extracted registration_date: {fallback_date}")
                            
                            # Step 2: Try OCR text (already extracted)
                            elif ocr_text:
                                ocr_date = extract_registration_date_fallback(ocr_text)
                                if ocr_date:
                                    result['registration_date'] = ocr_date
                                    fallback_stats['ocr_dates'] += 1
                                    logger.debug(f"[FALLBACK-OCR] Extracted registration_date: {ocr_date}")
                        
                        # ROBUST FALLBACK: Contact Phone
                        if not result.get('contact'):
                            # Step 1: Try regex on caption
                            phones = extract_phone_numbers(original_caption)
                            if phones:
                                result['contact'] = phones[0]
                                fallback_stats['regex_contacts'] += 1
                                logger.debug(f"[FALLBACK-REGEX] Extracted contact: {phones[0]}")
                            
                            # Step 2: Try OCR text (PHASE A NEW)
                            elif ocr_text:
                                phones_ocr = extract_phone_numbers(ocr_text)
                                if phones_ocr:
                                    result['contact'] = phones_ocr[0]
                                    fallback_stats['ocr_contacts'] += 1
                                    logger.debug(f"[FALLBACK-OCR] Extracted contact: {phones_ocr[0]}")
                        
                        # ROBUST FALLBACK: Organizer (PHASE B: With Validation)
                        if not result.get('organizer'):
                            extracted_organizer = None
                            extraction_source = None
                            
                            # Step 1: Try regex on caption
                            fallback_organizer = extract_organizer_fallback(original_caption, account_name)
                            if fallback_organizer:
                                extracted_organizer = fallback_organizer
                                extraction_source = 'regex'
                            
                            # Step 2: Try OCR text
                            elif ocr_text:
                                organizer_ocr = extract_organizer_fallback(ocr_text, account_name)
                                if organizer_ocr:
                                    extracted_organizer = organizer_ocr
                                    extraction_source = 'ocr'
                            
                            # Step 3: Try extracting from @mentions
                            if not extracted_organizer:
                                mention_organizer = self.organizer_validator.extract_from_mentions(
                                    original_caption,
                                    ocr_text
                                )
                                if mention_organizer:
                                    extracted_organizer = mention_organizer
                                    extraction_source = 'mention'
                            
                            # PHASE B: Validate extracted organizer
                            if extracted_organizer:
                                validated_organizer, confidence = self.organizer_validator.validate(
                                    extracted_organizer,
                                    account_name,
                                    original_caption,
                                    ocr_text
                                )
                                
                                if validated_organizer:
                                    result['organizer'] = validated_organizer
                                    result['organizer_confidence'] = confidence
                                    
                                    # Track by source
                                    if extraction_source == 'regex':
                                        fallback_stats['regex_organizers'] += 1
                                    elif extraction_source == 'ocr':
                                        fallback_stats['ocr_organizers'] += 1
                                    elif extraction_source == 'mention':
                                        fallback_stats['mention_organizers'] = fallback_stats.get('mention_organizers', 0) + 1
                                    
                                    logger.debug(f"[FALLBACK-{extraction_source.upper()}] Extracted organizer: {validated_organizer} (confidence: {confidence}%)")
                                else:
                                    logger.debug(f"[FALLBACK] Organizer validation failed: '{extracted_organizer}' (confidence: {confidence}%)")
                        
                        # PHASE B: Validate Gemini-extracted organizer
                        elif result.get('organizer'):
                            gemini_organizer = result['organizer']
                            validated_organizer, confidence = self.organizer_validator.validate(
                                gemini_organizer,
                                account_name,
                                original_caption,
                                ocr_text
                            )
                            
                            if validated_organizer:
                                result['organizer'] = validated_organizer
                                result['organizer_confidence'] = confidence
                                logger.debug(f"[GEMINI-VALIDATED] Organizer: {validated_organizer} (confidence: {confidence}%)")
                            else:
                                # Gemini extracted invalid organizer, remove it
                                logger.warning(f"[VALIDATION] Removed invalid Gemini organizer: '{gemini_organizer}' (confidence: {confidence}%)")
                                result['organizer'] = None
                                result['organizer_confidence'] = 0
                        
                        # ROBUST FALLBACK: Registration URL
                        if not result.get('registration_url'):
                            # Step 1: Try regex on caption
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
                                    logger.debug(f"[FALLBACK-REGEX] Extracted registration_url: {best_url}")
                            
                            # Step 2: Try OCR text (PHASE A NEW)
                            elif ocr_text:
                                urls_ocr = extract_urls(ocr_text)
                                if urls_ocr:
                                    # Same prioritization logic
                                    registration_keywords = ['daftar', 'regist', 'form', 'pendaftaran', 'bit.ly', 'forms.gle', 'linktr.ee', 's.id']
                                    
                                    best_url = None
                                    for url in urls_ocr:
                                        url_lower = url.lower()
                                        if any(kw in url_lower for kw in registration_keywords):
                                            best_url = url
                                            break
                                    
                                    if not best_url and urls_ocr:
                                        best_url = urls_ocr[0]
                                    
                                    if best_url:
                                        result['registration_url'] = best_url
                                        fallback_stats['ocr_urls'] += 1
                                        logger.debug(f"[FALLBACK-OCR] Extracted registration_url: {best_url}")
                        
                        # SMART DATE FALLBACK (FIX 1: Required Dates - 2026-05-01)
                        # Apply smart fallback to ensure registration_date is always present
                        registration_date = result.get('registration_date')
                        
                        if not registration_date or not registration_date.strip():
                            # No registration_date found, try to generate from deadline if available
                            # This will be handled by normalizer, just log for now
                            logger.debug(f"[SMART FALLBACK] No registration_date for: {result.get('title', 'Unknown')[:50]}")
                            fallback_stats['no_registration_date'] = fallback_stats.get('no_registration_date', 0) + 1
                        else:
                            # Registration date exists, validate it has proper format
                            # Extract deadline to ensure we have structured dates
                            from src.extraction.utils.helpers import extract_deadline_from_registration
                            deadline = extract_deadline_from_registration(registration_date)
                            if deadline:
                                logger.debug(f"[DATE VALIDATION] registration_date: {registration_date}, deadline: {deadline}")
                        
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
            if fallback_stats.get('title_fallback', 0) > 0:
                logger.info(f"    - Title (Caption):  {fallback_stats['title_fallback']} extracted")
            if fallback_stats.get('title_fallback_ocr', 0) > 0:
                logger.info(f"    - Title (OCR):      {fallback_stats['title_fallback_ocr']} extracted")
            if fallback_stats['regex_dates'] > 0:
                logger.info(f"    - Regex Dates:      {fallback_stats['regex_dates']} extracted")
            if fallback_stats['ocr_dates'] > 0:
                logger.info(f"    - OCR Dates:        {fallback_stats['ocr_dates']} extracted")
            if fallback_stats['regex_contacts'] > 0:
                logger.info(f"    - Regex Contacts:   {fallback_stats['regex_contacts']} extracted")
            if fallback_stats['ocr_contacts'] > 0:
                logger.info(f"    - OCR Contacts:     {fallback_stats['ocr_contacts']} extracted")
            if fallback_stats['regex_organizers'] > 0:
                logger.info(f"    - Regex Organizers: {fallback_stats['regex_organizers']} extracted")
            if fallback_stats['ocr_organizers'] > 0:
                logger.info(f"    - OCR Organizers:   {fallback_stats['ocr_organizers']} extracted")
            if fallback_stats['regex_urls'] > 0:
                logger.info(f"    - Regex URLs:       {fallback_stats['regex_urls']} extracted")
            if fallback_stats['ocr_urls'] > 0:
                logger.info(f"    - OCR URLs:         {fallback_stats['ocr_urls']} extracted")
        
        success_rate = len(all_results)/total_captions*100 if total_captions > 0 else 0
        logger.info(f"\n[ACCOUNT SUMMARY] @{account_name}:")
        logger.info(f"  Posts Processed:    {total_captions}")
        logger.info(f"  Successfully Extracted: {len(all_results)}/{total_captions} ({success_rate:.1f}%)")
        if failed_batches:
            logger.warning(f"  Failed Batches:     {len(failed_batches)}")
        if total_fallbacks > 0:
            logger.info(f"  Fallbacks Applied:  {total_fallbacks} times")
        
        # PHASE B: Organizer Quality Metrics
        organizers_extracted = sum(1 for r in all_results if r.get('organizer'))
        if organizers_extracted > 0:
            high_conf = sum(1 for r in all_results if r.get('organizer_confidence', 0) >= 90)
            medium_conf = sum(1 for r in all_results if 60 <= r.get('organizer_confidence', 0) < 90)
            low_conf = sum(1 for r in all_results if 30 <= r.get('organizer_confidence', 0) < 60)
            avg_confidence = sum(r.get('organizer_confidence', 0) for r in all_results if r.get('organizer')) / organizers_extracted
            
            logger.info(f"\n[ORGANIZER QUALITY] @{account_name}:")
            logger.info(f"  Organizers Extracted: {organizers_extracted}/{total_captions} ({organizers_extracted/total_captions*100:.1f}%)")
            logger.info(f"  High Confidence (90-100%): {high_conf} ({high_conf/organizers_extracted*100:.1f}%)")
            logger.info(f"  Medium Confidence (60-89%): {medium_conf} ({medium_conf/organizers_extracted*100:.1f}%)")
            logger.info(f"  Low Confidence (30-59%): {low_conf} ({low_conf/organizers_extracted*100:.1f}%)")
            logger.info(f"  Average Confidence: {avg_confidence:.1f}%")
        
        return all_results
    
    def process_all_accounts(self, instagram_data: Dict) -> List[Dict]:
        """Process all accounts in the Instagram data with checkpoint/resume support"""
        
        # Detect all accounts
        accounts = {k: v for k, v in instagram_data.items() if isinstance(v, list) and len(v) > 0}
        
        if not accounts:
            logger.error("[ERROR] No accounts found in instagram_data!")
            return []
        
        accounts_list = list(accounts.keys())
        total_accounts = len(accounts_list)
        total_posts = sum(len(posts) for posts in accounts.values())
        
        # Try to load checkpoint
        checkpoint, existing_results = self.checkpoint_manager.load_checkpoint()
        
        if checkpoint:
            start_index = self.checkpoint_manager.get_resume_index(checkpoint)
            all_results = existing_results
            
            logger.info(f"\n{'='*60}")
            logger.info(f"[RESUME] Checkpoint Found!")
            logger.info('='*60)
            logger.info(f"[RESUME] Last completed: {checkpoint['last_completed_account']}")
            logger.info(f"[RESUME] Progress: {checkpoint['last_completed_index']+1}/{total_accounts} accounts")
            logger.info(f"[RESUME] Results so far: {len(existing_results)} posts")
            logger.info(f"[RESUME] Resuming from account {start_index+1}/{total_accounts}")
            logger.info(f"[RESUME] Accounts remaining: {total_accounts - start_index}")
            logger.info(f"{'='*60}\n")
        else:
            start_index = 0
            all_results = []
            
            logger.info(f"\n{'='*60}")
            logger.info(f"[EXTRACTION] AI Extraction Pipeline Starting...")
            logger.info('='*60)
            logger.info(f"[INPUT] Detected {total_accounts} account(s), {total_posts} total posts")
            for account_name, posts in accounts.items():
                logger.info(f"  - @{account_name}: {len(posts)} posts")
            logger.info(f"[CONFIG] Model: {config.GEMINI_MODEL} | Batch size: {config.BATCH_SIZE} | Rate limit: {config.DELAY_BETWEEN_REQUESTS}s")
            logger.info(f"{'='*60}\n")
        
        # Process accounts from start_index
        for account_index in range(start_index, total_accounts):
            account_name = accounts_list[account_index]
            captions = accounts[account_name]
            
            try:
                account_results = self.process_account(account_name, captions)
                all_results.extend(account_results)
                
                # Save checkpoint after each account
                success = self.checkpoint_manager.save_checkpoint(
                    account_index=account_index,
                    account_name=account_name,
                    results=all_results,
                    total_accounts=total_accounts,
                    accounts_list=accounts_list
                )
                
                if success:
                    logger.info(f"[CHECKPOINT] Progress saved: {len(all_results)} results ({account_index+1}/{total_accounts} accounts)")
                else:
                    logger.warning(f"[CHECKPOINT] Failed to save (continuing anyway)")
                
                # Small delay between accounts
                if account_index < total_accounts - 1:
                    logger.info(f"[WAIT] Pausing 2s before next account...")
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"[ERROR] Failed to process account @{account_name}: {e}")
                logger.info(f"[CONTINUE] Continuing with next account...")
                continue
        
        # Cleanup checkpoint on successful completion
        self.checkpoint_manager.cleanup_checkpoint()
        
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
        
        # Try to load from latest checkpoint if no results in memory
        if not results:
            try:
                checkpoint_files = sorted(config.PROCESSED_DIR.glob('checkpoint_account_*.json'))
                if checkpoint_files:
                    latest_checkpoint = checkpoint_files[-1]
                    logger.info(f"[RECOVERY] Loading from checkpoint: {latest_checkpoint.name}")
                    with open(latest_checkpoint, 'r', encoding='utf-8') as f:
                        checkpoint_data = json.load(f)
                        results = checkpoint_data.get('results', [])
                    logger.info(f"[RECOVERY] Loaded {len(results)} results from checkpoint")
            except Exception as e:
                logger.warning(f"[RECOVERY] Failed to load checkpoint: {e}")
        
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
        
        # Try to load from latest checkpoint if no results in memory
        if not results:
            try:
                checkpoint_files = sorted(config.PROCESSED_DIR.glob('checkpoint_account_*.json'))
                if checkpoint_files:
                    latest_checkpoint = checkpoint_files[-1]
                    logger.info(f"[RECOVERY] Loading from checkpoint: {latest_checkpoint.name}")
                    with open(latest_checkpoint, 'r', encoding='utf-8') as f:
                        checkpoint_data = json.load(f)
                        results = checkpoint_data.get('results', [])
                    logger.info(f"[RECOVERY] Loaded {len(results)} results from checkpoint")
            except Exception as recovery_error:
                logger.warning(f"[RECOVERY] Failed to load checkpoint: {recovery_error}")
        
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
