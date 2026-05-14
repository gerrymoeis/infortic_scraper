"""
OpenRouter API Client for data extraction fallback
"""

import json
import sys
import time
import requests
from pathlib import Path
from typing import List, Dict, Optional
import base64

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.extraction.utils.config import config
from src.extraction.utils.logger import setup_logger

logger = setup_logger('openrouter')

class OpenRouterClient:
    def __init__(self):
        """Initialize OpenRouter client with API key rotation support"""
        self.api_endpoint = "https://openrouter.ai/api/v1/chat/completions"
        self.model = "openrouter/free"  # Smart free model router
        self._initialize_client(config.OPENROUTER_API_KEY)
    
    def _initialize_client(self, api_key: str):
        """Initialize or reinitialize client with given API key"""
        self.api_key = api_key
        logger.info(f"Initialized OpenRouter client with model: {self.model}")
    
    def _parse_json_with_recovery(self, json_text: str) -> List[Dict]:
        """
        Parse JSON with multiple recovery strategies (same as Gemini)
        
        Args:
            json_text: Raw JSON text from API response
            
        Returns:
            Parsed JSON array or empty list if all strategies fail
        """
        import re
        
        # Strategy 1: Direct parse
        try:
            data = json.loads(json_text)
            logger.info("[OK] JSON parsed successfully (direct)")
            return data
        except json.JSONDecodeError as e:
            logger.warning(f"Direct JSON parse failed: {str(e)[:100]}")
        
        # Strategy 2: Extract JSON array with regex
        try:
            json_match = re.search(r'\[.*\]', json_text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                logger.info("[OK] JSON recovered (regex extraction)")
                return data
        except Exception as e:
            logger.warning(f"Regex extraction failed: {str(e)[:100]}")
        
        # Strategy 3: Fix common JSON formatting issues
        try:
            fixed_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
            fixed_text = re.sub(r'}\s*{', '},{', fixed_text)
            data = json.loads(fixed_text)
            logger.info("[OK] JSON recovered (formatting fixes)")
            return data
        except Exception as e:
            logger.warning(f"Formatting fixes failed: {str(e)[:100]}")
        
        # Strategy 4: Extract individual objects and rebuild array
        try:
            objects = re.findall(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', json_text)
            if objects:
                parsed_objects = []
                for obj_text in objects:
                    try:
                        obj = json.loads(obj_text)
                        parsed_objects.append(obj)
                    except:
                        continue
                
                if parsed_objects:
                    logger.info(f"[OK] JSON recovered (rebuilt from {len(parsed_objects)} objects)")
                    return parsed_objects
        except Exception as e:
            logger.warning(f"Object extraction failed: {str(e)[:100]}")
        
        # Strategy 5: Try to fix truncated JSON
        try:
            if json_text.strip().endswith(','):
                json_text = json_text.strip()[:-1]
            
            open_brackets = json_text.count('[') - json_text.count(']')
            open_braces = json_text.count('{') - json_text.count('}')
            
            if open_brackets > 0 or open_braces > 0:
                fixed_text = json_text
                fixed_text += '}' * open_braces
                fixed_text += ']' * open_brackets
                
                data = json.loads(fixed_text)
                logger.info("[OK] JSON recovered (truncation fix)")
                return data
        except Exception as e:
            logger.warning(f"Truncation fix failed: {str(e)[:100]}")
        
        # All strategies failed
        logger.error("[FAILED] All JSON recovery strategies failed")
        logger.error(f"Response preview: {json_text[:500]}...")
        return []
    
    def _rotate_api_key(self):
        """
        Rotate to next API key
        
        Returns:
            True if successfully rotated to a new key, False if all keys exhausted
        """
        if len(config.OPENROUTER_API_KEYS) <= 1:
            return False
        
        # Try next key
        new_key = config.get_next_openrouter_key()
        logger.info(f"Rotating to API key #{config.CURRENT_OPENROUTER_KEY_INDEX + 1}")
        self._initialize_client(new_key)
        
        return True
    
    def _encode_image_base64(self, image_path: Path) -> Optional[str]:
        """
        Encode image to base64 for OpenRouter API
        
        Args:
            image_path: Path to image file
            
        Returns:
            Base64 encoded image string or None if failed
        """
        try:
            from PIL import Image
            import io
            
            # Load and optimize image
            img = Image.open(image_path)
            
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large (max 2048x2048)
            max_size = 2048
            if img.width > max_size or img.height > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Convert to bytes
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='JPEG', quality=85)
            img_bytes = img_byte_arr.getvalue()
            
            # Encode to base64
            base64_image = base64.b64encode(img_bytes).decode('utf-8')
            
            return base64_image
            
        except Exception as e:
            logger.warning(f"Failed to encode image {image_path.name}: {e}")
            return None
    
    def _create_messages(self, captions_batch: List[Dict], ocr_texts: Dict[str, tuple] = None, send_images: bool = True):
        """
        Create messages array for OpenRouter API (OpenAI format)
        
        Args:
            captions_batch: List of caption dictionaries
            ocr_texts: Optional dict mapping post_id to (ocr_text, confidence) tuples
            send_images: If True, include images in messages
            
        Returns:
            Messages array for OpenRouter API
        """
        # System message with extraction instructions
        system_message = """Extract data from Indonesian competition/opportunity posts. You receive CAPTION + POSTER IMAGE for each post.

🎯 CRITICAL PRIORITY: REGISTRATION DATES ARE MANDATORY!

EXTRACTION STRATEGY FOR DATES:
1. CHECK IMAGE FIRST - dates are usually in the poster/flyer
2. Look for keywords: "Pendaftaran", "Registrasi", "Daftar", "Deadline", "DL", "Batas Akhir", "Tutup"
3. Common formats:
   - "1-14 April 2026" → "1 April 2026 - 14 April 2026"
   - "Pendaftaran: 1 April - 14 April 2026" → "1 April 2026 - 14 April 2026"
   - "DL: 15 April 2026" → use as end date
4. If you see a date range, extract BOTH start and end dates

REQUIRED FIELDS:
1. TITLE: Event title (original language, max 100 chars)
2. DESCRIPTION: Brief summary in Bahasa Indonesia (max 200 chars)
3. CATEGORY: competition|scholarship|internship|job|freelance|training|tryout|workshop|festival|hackathon
4. AUDIENCES: ["sd","smp","sma","smk","d2","d3","d4","s1","umum"]
5. REGISTRATION_DATE: "DD Month YYYY - DD Month YYYY" or null
6. CONTACT: Phone number only ("081234567890") or null
7. EVENT_TYPE: online|offline|hybrid
8. FEE_TYPE: gratis|berbayar
9. ORGANIZER: Organization name or null
10. REGISTRATION_URL: Main registration link or null

Return JSON array only:
[{"post_id":"string","title":"string","description":"string","category":"string","audiences":["string"],"registration_date":"string","contact":"string","event_type":"string","fee_type":"string","organizer":"string","registration_url":"string"}]"""
        
        # Build user message content
        user_content = []
        
        # Add text instruction
        user_content.append({
            "type": "text",
            "text": f"Processing {len(captions_batch)} posts:\n\n"
        })
        
        # Add each post
        project_root = Path(__file__).parent.parent.parent
        image_dir = project_root / 'scraper' / 'instagram_images'
        
        images_loaded = 0
        images_failed = 0
        
        for i, item in enumerate(captions_batch, 1):
            post_id = item['post_id']
            caption = item['caption']
            
            # Add caption text
            post_text = f"=== POST {i}/{len(captions_batch)} ===\nID: {post_id}\nCaption: {caption}\n"
            
            # Add OCR text if available
            if ocr_texts and post_id in ocr_texts:
                ocr_text, ocr_confidence = ocr_texts[post_id]
                if ocr_text:
                    post_text += f"Image Text (OCR, {ocr_confidence}% confidence): {ocr_text[:1000]}\n"
            
            user_content.append({
                "type": "text",
                "text": post_text
            })
            
            # Add image if available and send_images=True
            if send_images and 'downloaded_image' in item:
                image_filename = item['downloaded_image']
                image_path = image_dir / image_filename
                
                if image_path.exists():
                    base64_image = self._encode_image_base64(image_path)
                    if base64_image:
                        user_content.append({
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        })
                        images_loaded += 1
                        logger.debug(f"[IMAGE] Loaded {image_filename}")
                    else:
                        images_failed += 1
                else:
                    images_failed += 1
                    logger.warning(f"[IMAGE] Not found: {image_filename}")
        
        logger.info(f"[IMAGES] Loaded {images_loaded}/{len(captions_batch)} images successfully ({images_failed} failed)")
        
        # Build messages array
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_content}
        ]
        
        return messages
    
    def process_batch(self, captions_batch: List[Dict], ocr_texts: Dict[str, tuple] = None, send_images: bool = True) -> List[Dict]:
        """
        Process a batch of captions using OpenRouter API with comprehensive error handling
        
        Args:
            captions_batch: List of caption dictionaries
            ocr_texts: Optional dict mapping post_id to (ocr_text, confidence) tuples
            send_images: If True, send actual images to API (RECOMMENDED for better accuracy)
        """
        
        logger.info(f"[BATCH] Processing {len(captions_batch)} captions with OpenRouter...")
        
        if send_images:
            logger.info(f"[IMAGES] Preparing to send {len(captions_batch)} images to OpenRouter...")
        
        # PROACTIVE KEY ROTATION: Rotate to next key before each request
        if len(config.OPENROUTER_API_KEYS) > 1:
            config.get_next_openrouter_key()
            self._initialize_client(config.OPENROUTER_API_KEY)
            logger.info(f"[KEY ROTATION] Using API key #{config.CURRENT_OPENROUTER_KEY_INDEX + 1}/{len(config.OPENROUTER_API_KEYS)}")
        
        logger.info(f"[API] Sending request to OpenRouter API...")
        
        try:
            api_start_time = time.time()
            
            # Prepare messages
            messages = self._create_messages(captions_batch, ocr_texts, send_images)
            
            # Prepare request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/gerrymoeis/infortic_scraper",
                "X-Title": "Infortic Scraper"
            }
            
            payload = {
                "model": self.model,
                "messages": messages,
                "response_format": {"type": "json_object"}
            }
            
            # Call OpenRouter API with retry logic
            response = None
            last_error = None
            
            # Track which API keys we've tried
            tried_keys = set()
            tried_keys.add(config.CURRENT_OPENROUTER_KEY_INDEX)
            
            # Maximum attempts: all keys * 2
            max_attempts = len(config.OPENROUTER_API_KEYS) * 2
            
            for attempt in range(1, max_attempts + 1):
                try:
                    # Log progress for attempts after the first
                    if attempt > 1:
                        logger.info(f"[RETRY] Attempt {attempt}/{max_attempts} with key #{config.CURRENT_OPENROUTER_KEY_INDEX + 1}")
                    
                    # Make API call
                    response = requests.post(
                        self.api_endpoint,
                        headers=headers,
                        json=payload,
                        timeout=60
                    )
                    
                    # Check response status
                    if response.status_code == 200:
                        response_data = response.json()
                        response_text = response_data['choices'][0]['message']['content']
                        
                        # Success - break retry loop
                        api_duration = time.time() - api_start_time
                        logger.info(f"[SUCCESS] Response received in {api_duration:.1f}s with key #{config.CURRENT_OPENROUTER_KEY_INDEX + 1}")
                        break
                    else:
                        # API returned error status
                        error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                        raise Exception(error_msg)
                    
                except KeyboardInterrupt:
                    logger.warning("[INTERRUPT] Interrupted by user")
                    raise
                    
                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()
                    
                    # Log the actual error for debugging
                    logger.warning(f"[DEBUG] Full error: {str(e)[:200]}")
                    
                    # Classify error type
                    is_quota_error = 'quota' in error_msg or 'rate limit' in error_msg or '429' in error_msg
                    is_auth_error = 'api key' in error_msg or 'authentication' in error_msg or '403' in error_msg or 'unauthorized' in error_msg or '401' in error_msg
                    is_server_error = '503' in error_msg or 'service unavailable' in error_msg or '500' in error_msg or '502' in error_msg
                    
                    # Log error details
                    if is_server_error:
                        # Server overload - wait and retry with exponential backoff
                        wait_time = min(2 ** attempt, 30)
                        logger.warning(f"[WARNING] Server error (503/500) - waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        continue
                    elif is_quota_error:
                        logger.warning(f"[WARNING] Quota exceeded on key #{config.CURRENT_OPENROUTER_KEY_INDEX + 1}")
                    elif is_auth_error:
                        logger.warning(f"[WARNING] Authentication failed on key #{config.CURRENT_OPENROUTER_KEY_INDEX + 1}")
                    else:
                        logger.warning(f"[WARNING] Error: {str(e)[:100]}")
                    
                    # Determine next action
                    should_rotate_key = is_quota_error or is_auth_error
                    
                    # Try rotating key if needed
                    if should_rotate_key:
                        # Check if we have more keys to try
                        if len(tried_keys) < len(config.OPENROUTER_API_KEYS):
                            if self._rotate_api_key():
                                tried_keys.add(config.CURRENT_OPENROUTER_KEY_INDEX)
                                # Update headers with new key
                                headers["Authorization"] = f"Bearer {self.api_key}"
                                logger.info(f"[RETRY] Retrying with key #{config.CURRENT_OPENROUTER_KEY_INDEX + 1} (attempt {attempt}/{max_attempts})")
                                continue
                        
                        # All keys exhausted
                        logger.error(f"[ERROR] All {len(config.OPENROUTER_API_KEYS)} API keys exhausted")
                        return []
                    
                    # For other errors, use exponential backoff
                    if attempt < max_attempts:
                        wait_time = min(2 ** attempt, 30)
                        logger.warning(f"Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"All {max_attempts} attempts failed")
                        raise last_error
            
            if response is None or response.status_code != 200:
                logger.error("[ERROR] No successful response received from API")
                return []
            
            # Parse JSON response with improved recovery
            json_text = response_text.strip()
            
            # Remove markdown code blocks if present
            if json_text.startswith('```'):
                json_text = json_text.replace('```json', '').replace('```', '').strip()
            
            # Parse JSON with multiple recovery strategies
            extracted_data = self._parse_json_with_recovery(json_text)
            
            # Validate response is a list
            if not isinstance(extracted_data, list):
                logger.error(f"Expected list, got {type(extracted_data)}")
                return []
            
            logger.info(f"Successfully extracted {len(extracted_data)} items")
            return extracted_data
            
        except KeyboardInterrupt:
            logger.warning("Batch processing interrupted by user")
            raise
            
        except Exception as e:
            logger.error(f"Unexpected error: {type(e).__name__}: {str(e)[:100]}")
            return []
