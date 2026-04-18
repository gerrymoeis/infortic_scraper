"""
Gemini API Client for data extraction
"""

import json
import sys
import time
from pathlib import Path
from typing import List, Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from google import genai
from google.genai import types

from src.extraction.utils.config import config
from src.extraction.utils.logger import setup_logger

logger = setup_logger('gemini')

class GeminiClient:
    def __init__(self):
        """Initialize Gemini client with API key rotation support"""
        self._initialize_client(config.GEMINI_API_KEY)
    
    def _initialize_client(self, api_key: str):
        """Initialize or reinitialize client with given API key"""
        self.client = genai.Client(api_key=api_key)
        logger.info(f"Initialized Gemini client with model: {config.GEMINI_MODEL}")
    
    def _parse_json_with_recovery(self, json_text: str) -> List[Dict]:
        """
        Parse JSON with multiple recovery strategies
        
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
            # Remove trailing commas before closing brackets
            fixed_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
            
            # Fix unescaped quotes in strings (common issue)
            # This is tricky - only fix quotes that are clearly inside string values
            # Pattern: "key": "value with "quote" inside"
            # We'll try to escape quotes that appear between ": " and next "
            
            # Fix missing commas between objects
            fixed_text = re.sub(r'}\s*{', '},{', fixed_text)
            
            # Try parsing fixed text
            data = json.loads(fixed_text)
            logger.info("[OK] JSON recovered (formatting fixes)")
            return data
        except Exception as e:
            logger.warning(f"Formatting fixes failed: {str(e)[:100]}")
        
        # Strategy 4: Extract individual objects and rebuild array
        try:
            # Find all complete JSON objects
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
            # If JSON ends abruptly, try to close it properly
            if json_text.strip().endswith(','):
                json_text = json_text.strip()[:-1]  # Remove trailing comma
            
            # Count brackets and add missing closing brackets
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
        if len(config.GEMINI_API_KEYS) <= 1:
            return False
        
        # Try next key
        new_key = config.get_next_api_key()
        logger.info(f"Rotating to API key #{config.CURRENT_KEY_INDEX + 1}")
        self._initialize_client(new_key)
        
        return True
    
    def _rotate_model(self):
        """
        Rotate to next fallback model
        
        Returns:
            True if successfully rotated to a new model, False if all models exhausted
        """
        if len(config.FALLBACK_MODELS) <= 1:
            return False
        
        # Try next model
        new_model = config.get_next_model()
        logger.info(f"Rotating to model: {new_model}")
        self._initialize_client(config.GEMINI_API_KEY)
        
        return True
    
    def _create_multimodal_content(self, captions_batch: List[Dict], ocr_texts: Dict[str, tuple] = None):
        """
        Create multimodal content with images for Gemini Vision API
        
        Args:
            captions_batch: List of caption dictionaries
            ocr_texts: Optional dict mapping post_id to (ocr_text, confidence) tuples
            
        Returns:
            List of content parts (text + images) for Gemini API
        """
        from PIL import Image
        from pathlib import Path
        import base64
        import io
        
        # Start with the instruction prompt
        instruction = """
You are extracting structured data from Indonesian competition/opportunity announcements from Instagram.

CRITICAL: You will receive BOTH caption text AND poster images for each post.

EXTRACTION PRIORITY:
- DATES (registration_date): Extract from IMAGE first (dates are usually in the poster)
- CONTACT (phone): Extract from IMAGE first
- URLS (registration_url): Extract from IMAGE first
- TITLE: Caption first, then IMAGE if needed
- ORGANIZER: Caption @mentions first, then IMAGE

Process these posts and return a JSON array with one object per post.

EXTRACTION RULES:

1. TITLE: Extract the main event/program title exactly as stated
   - Keep original language, max 100 characters

2. DESCRIPTION: Create a brief description IN BAHASA INDONESIA
   - ALWAYS write in Bahasa Indonesia
   - Max 200 characters

3. CATEGORY: ONE of: competition, scholarship, internship, job, freelance, training, tryout, workshop, festival, hackathon

4. AUDIENCES: Target audiences ["sd", "smp", "sma", "smk", "d2", "d3", "d4", "s1", "umum"]

5. REGISTRATION_DATE: Extract registration period in Indonesian format
   - Format: "DD Month YYYY - DD Month YYYY"
   - Example: "1 Maret 2026 - 31 Maret 2026"
   - ⚠️ CRITICAL: Look at the IMAGE first! Dates are usually in the poster.
   - Look for keywords: "Pendaftaran", "Registrasi", "Daftar", "Deadline", "Batas", "Tutup"
   - If only one date: "DD Month YYYY"
   - If no date found: null

6. CONTACT: Extract PRIMARY contact phone number (just ONE)
   - ⚠️ CRITICAL: Look at the IMAGE first! Contact info is usually in the poster.
   - Remove all spaces and dashes
   - Format: numbers only (e.g., "081234567890")
   - Look for: "CP:", "Contact:", "WA:", "Narahubung:", phone numbers, wa.me links
   - If no phone found: null

7. EVENT_TYPE: "online", "offline", or "hybrid"

8. FEE_TYPE: "gratis" or "berbayar"

9. ORGANIZER: Extract the ACTUAL organization/institution name
   - Look for @mentions, "by [name]", "dari [name]" patterns
   - DO NOT extract generic phrases or transition words
   - If no clear organizer: null

10. REGISTRATION_URL: Extract PRIMARY registration link (just ONE)
    - ⚠️ CRITICAL: Look at the IMAGE first! URLs are usually in the poster.
    - Look for: bit.ly, forms.gle, linktr.ee, or any https link
    - If no link found: null

Return ONLY a JSON array with this structure:
[
  {
    "post_id": "string",
    "title": "string",
    "description": "string (max 200 chars)",
    "category": "competition|scholarship|internship|job|freelance|training|tryout|workshop|festival|hackathon",
    "audiences": ["smp", "sma", "smk", "d3", "d4", "s1", "umum"],
    "registration_date": "DD Month YYYY - DD Month YYYY or null",
    "contact": "string (numbers only) or null",
    "event_type": "online|offline|hybrid",
    "fee_type": "gratis|berbayar",
    "organizer": "string or null",
    "registration_url": "string or null"
  }
]

Now processing the posts:
"""
        
        # Build content parts: instruction + (caption + image) for each post
        content_parts = [instruction]
        
        project_root = Path(__file__).parent.parent.parent
        image_dir = project_root / 'data' / 'images'
        
        images_loaded = 0
        images_failed = 0
        
        for i, item in enumerate(captions_batch, 1):
            post_id = item['post_id']
            caption = item['caption']
            
            # Add caption text
            caption_text = f"\n\n=== POST {i}/{len(captions_batch)} ===\nID: {post_id}\nCaption: {caption}\n"
            content_parts.append(caption_text)
            
            # Try to load and add image
            if 'downloaded_image' in item:
                image_filename = item['downloaded_image']
                image_path = image_dir / image_filename
                
                if image_path.exists():
                    try:
                        # Load image
                        img = Image.open(image_path)
                        
                        # Convert to RGB if needed (remove alpha channel)
                        if img.mode in ('RGBA', 'LA', 'P'):
                            img = img.convert('RGB')
                        
                        # Resize if too large (max 1024x1024 to save tokens)
                        max_size = 1024
                        if img.width > max_size or img.height > max_size:
                            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                        
                        # Convert to bytes
                        img_byte_arr = io.BytesIO()
                        img.save(img_byte_arr, format='JPEG', quality=85)
                        img_bytes = img_byte_arr.getvalue()
                        
                        # Add image to content
                        content_parts.append({
                            'mime_type': 'image/jpeg',
                            'data': base64.b64encode(img_bytes).decode('utf-8')
                        })
                        
                        images_loaded += 1
                        logger.debug(f"[IMAGE] Loaded {image_filename} ({img.width}x{img.height})")
                        
                    except Exception as e:
                        images_failed += 1
                        logger.warning(f"[IMAGE] Failed to load {image_filename}: {e}")
                        content_parts.append(f"[Image {image_filename} could not be loaded]\n")
                else:
                    images_failed += 1
                    logger.warning(f"[IMAGE] Not found: {image_filename}")
                    content_parts.append(f"[Image {image_filename} not found]\n")
            else:
                images_failed += 1
                content_parts.append(f"[No image available for this post]\n")
        
        logger.info(f"[IMAGES] Loaded {images_loaded}/{len(captions_batch)} images successfully ({images_failed} failed)")
        
        return content_parts
    
    def create_batch_prompt(self, captions_batch: List[Dict], ocr_texts: Dict[str, tuple] = None) -> str:
        """
        Create optimized prompt for batch processing with simplified output
        
        Args:
            captions_batch: List of caption dictionaries
            ocr_texts: Optional dict mapping post_id to (ocr_text, confidence) tuples
        """
        
        captions_text = []
        for item in captions_batch:
            post_id = item['post_id']
            caption_preview = item['caption'][:500]
            
            # Build caption entry
            entry = f"ID: {post_id}\nCaption: {caption_preview}..."
            
            # Add OCR text if available (PHASE C PART 3 STAGE 3)
            if ocr_texts and post_id in ocr_texts:
                ocr_text, ocr_confidence = ocr_texts[post_id]
                # Limit OCR text to 1000 chars to manage token usage
                ocr_preview = ocr_text[:1000] if ocr_text else ""
                if ocr_preview:
                    entry += f"\nImage Text (OCR, {ocr_confidence}% confidence): {ocr_preview}..."
            
            captions_text.append(entry)
        
        captions_string = "\n\n---\n\n".join(captions_text)
        
        prompt = f"""
You are extracting structured data from Indonesian competition/opportunity announcements from Instagram.

IMPORTANT: Keep output simple and focused on essential information only.

=== CRITICAL: TWO TEXT SOURCES ===

You will receive TWO sources of text for each post:
1. CAPTION: The Instagram caption text
2. IMAGE TEXT (OCR): Text extracted from the poster/image (when available)

EXTRACTION PRIORITY BY FIELD:
- DATES (registration_date): Check IMAGE TEXT first, then caption
- CONTACT (phone): Check IMAGE TEXT first, then caption  
- URLS (registration_url): Check IMAGE TEXT first, then caption
- TITLE: Caption first, then IMAGE TEXT if needed
- DESCRIPTION: Caption first, supplement with IMAGE TEXT
- ORGANIZER: Caption @mentions first, then IMAGE TEXT, then caption text

WHY? Event details (dates, contacts, URLs) are USUALLY in the poster image, not the caption!

TRIGGER PHRASES - If caption says:
- "Lihat poster" / "Cek poster" / "Detail di poster" / "Info lengkap di poster"
- "Swipe untuk info" / "Slide untuk detail"
→ Extract EVERYTHING from IMAGE TEXT!

===================================

Process these {len(captions_batch)} captions and return a JSON array with one object per caption.

CAPTIONS:
{captions_string}

EXTRACTION RULES:

1. TITLE: Extract the main event/program title exactly as stated
   - Use the exact title from the caption (keep original language)
   - Example: "Program English For Trainer" → keep as "Program English For Trainer"
   - Example: "LNGSHOT" → keep as "LNGSHOT"
   - Keep it clean, without emojis
   - Max 100 characters

2. DESCRIPTION: Create a brief, accurate description IN BAHASA INDONESIA
   - CRITICAL: ALWAYS write in Bahasa Indonesia, regardless of caption language
   - If caption has clear details: Summarize key benefits and requirements
   - If caption is vague/ambiguous: Write "Informasi [category] terkait [topic]. Lihat poster untuk detail lengkap."
   - Examples:
     * Clear caption → "Program pelatihan bahasa Inggris gratis selama 6 bulan dengan OJT dan peluang kerja"
     * Vague caption → "Informasi lomba terkait UKM. Lihat poster untuk detail lengkap."
   - Use natural, conversational Indonesian
   - Max 200 characters

3. CATEGORY: Identify using ONE of these:
   - "competition" (lomba, kompetisi, turnamen)
   - "scholarship" (beasiswa)
   - "internship" (magang)
   - "job" (lowongan kerja)
   - "freelance" (freelance)
   - "training" (pelatihan, kursus)
   - "tryout" (try out, simulasi)
   - "workshop" (workshop, seminar)
   - "festival" (festival, pameran)
   - "hackathon" (hackathon)

4. AUDIENCES: Extract target audiences ["sd", "smp", "sma", "smk", "d2", "d3", "d4", "s1", "umum"]
   - sd: Sekolah Dasar (Elementary School)
   - smp: Sekolah Menengah Pertama (Junior High School)
   - sma: Sekolah Menengah Atas (Senior High School)
   - smk: Sekolah Menengah Kejuruan (Vocational High School)
   - d2: Diploma 2
   - d3: Diploma 3
   - d4: Diploma 4
   - s1: Sarjana/Bachelor
   - umum: General/Public (all ages)

5. REGISTRATION_DATE: Extract registration period in Indonesian format
   
   ⚠️ CRITICAL: Check IMAGE TEXT first! Dates are usually in the poster.
   
   - Format: "DD Month YYYY - DD Month YYYY"
   - Example: "1 Maret 2026 - 31 Maret 2026"
   - If only one date: "DD Month YYYY"
   - Look for keywords: "Pendaftaran", "Registrasi", "Daftar", "Deadline", "Batas"
   - Check IMAGE TEXT before caption
   - If no date in either source: null

6. CONTACT: Extract PRIMARY contact phone number (just ONE)
   
   ⚠️ CRITICAL: Check IMAGE TEXT first! Contact info is usually in the poster.
   
   - Remove all spaces and dashes
   - Format: numbers only (e.g., "081234567890")
   - Look for: "CP:", "Contact:", "WA:", "Narahubung:", phone numbers
   - Check for wa.me links in IMAGE TEXT
   - Check IMAGE TEXT before caption
   - Pick the first/main contact person
   - If no phone found in either source: null

7. EVENT_TYPE: Determine event format
   - "online" if mentions: Online, Daring, Virtual, Zoom, Google Meet
   - "offline" if mentions: city name, venue, location
   - "hybrid" if mentions both online and offline
   - Default to "online" if unclear

8. FEE_TYPE: Simple classification
   - "gratis" if mentions: GRATIS, FREE, Tanpa Biaya
   - "berbayar" if mentions any fee amount
   - Default to "gratis" if unclear

9. ORGANIZER: Extract the ACTUAL organization/institution name
   
   CRITICAL RULES:
   - Extract ONLY the real organization/institution name
   - DO NOT extract generic phrases like: "para expert", "sekolah yang sama", "kreativitas", "adu logika", "inovasi masa depan"
   - DO NOT extract caption fragments or transition phrases: "oleh karena itu", "karena itu", "oleh sebab itu"
   - DO NOT use the Instagram source account (infolomba, lomba.it) as organizer
   - DO NOT extract descriptive text, adjectives, or filler words
   - If caption mentions location/venue but no organizer → return null
   
   LOOK FOR (in priority order):
   1. Instagram account tags (@mentions) - MOST RELIABLE SOURCE
      - Look for @mentions that appear AFTER the event description
      - Common patterns: "@organizationname" at the end of caption
      - Examples:
        * @almuhajirin3_purwakarta → "Pondok Pesantren Al-Muhajirin 3 Purwakarta"
        * @smptiga_almuhajirinpurwakarta → "SMP Tiga Al-Muhajirin Purwakarta"
        * @parekampunginggris → "Pare Kampung Inggris"
      - SKIP these accounts (they are info/source accounts, NOT organizers):
        * @infolomba, @lomba.it, @lomba_id, @info_lomba
   
   2. "by [name]", "dari [name]", "presented by [name]", "proudly presents" patterns
      - "by Excelraya" → "Excelraya" ✓
      - "MPK & OSIS SMA Negeri 63 Jakarta Mempersembahkan" → "SMA Negeri 63 Jakarta" ✓
      - "Oleh karena itu" → null (transition phrase, NOT organizer) ✗
      - "Oleh sebab itu" → null (transition phrase, NOT organizer) ✗
   
   3. Hashtags with organization names
      - #PareKampungInggris → "Pare Kampung Inggris"
      - #UniversitasBrawijaya → "Universitas Brawijaya"
   
   4. Organization names in specific contexts
      - "MPK & OSIS SMA Negeri 63", "Universitas Indonesia", "Pondok Pesantren X"
   
   SIMPLIFICATION RULES:
   - If "BEM Fakultas X Universitas Y" → use "Universitas Y"
   - If "Himpunan Mahasiswa X ITERA" → use "ITERA"
   - If "Departemen X Institut Y" → use "Institut Y"
   - Prefer shorter, cleaner names (max 50 characters)
   
   VALIDATION - Return null if:
   - Text is a generic phrase, adjective, or filler word
   - Text is a caption fragment or transition phrase
   - Text is the source Instagram account
   - Text describes the event type rather than organizer
   - No clear organizer is mentioned in the caption
   
   Examples:
   - Caption: "...@almuhajirin3_purwakarta @smptiga..." → "Pondok Pesantren Al-Muhajirin 3 Purwakarta" ✓
   - Caption: "Math Challenge by Excelraya" → "Excelraya" ✓
   - Caption: "BEM Fakultas Ilmu Komputer Universitas Katolik Soegijapranata" → "Universitas Katolik Soegijapranata" ✓
   - Caption: "Himpunan Mahasiswa Informatika ITERA" → "ITERA" ✓
   - Caption: "Oleh karena itu, kami mengajak..." → null (transition phrase) ✗
   - Caption: "para expert di bidang..." → null (generic phrase) ✗
   - Caption: "sekolah yang sama" → null (generic phrase) ✗
   - Caption: "Posted by @infolomba" → null (source account) ✗
   - Caption: "Lokasi: Pondok Pesantren Al-Muhajirin" (no organizer mentioned) → null ✗

10. REGISTRATION_URL: Extract PRIMARY registration link (just ONE)
    
    ⚠️ CRITICAL: Check IMAGE TEXT first! URLs are usually in the poster.
    
    - Pick the main registration URL
    - Look for: bit.ly, forms.gle, linktr.ee, or any https link
    - Prefer links near "Daftar", "Pendaftaran", "Registration"
    - Check IMAGE TEXT before caption
    - If multiple links, pick the first one
    - If no link found in either source: null

Return ONLY a JSON array with this EXACT structure:
[
  {{
    "post_id": "string",
    "title": "string",
    "description": "string (max 200 chars)",
    "category": "competition|scholarship|internship|job|freelance|training|tryout|workshop|festival|hackathon",
    "audiences": ["smp", "sma", "smk", "d3", "d4", "s1", "umum"],
    "registration_date": "DD Month YYYY - DD Month YYYY or null",
    "contact": "string (numbers only) or null",
    "event_type": "online|offline|hybrid",
    "fee_type": "gratis|berbayar",
    "organizer": "string or null",
    "registration_url": "string or null"
  }}
]

EXAMPLE 1 (Clear caption):
Input: "MATH CHALLENGE 2026\\nPendaftaran: 1-31 Maret 2026\\nCP: 0812-3456-7890\\nBiaya: Rp 50.000\\nOnline via Zoom\\nDaftar: https://bit.ly/mathchallenge"
Output: {{
  "post_id": "ABC123",
  "title": "MATH CHALLENGE 2026",
  "description": "Kompetisi matematika online dengan biaya pendaftaran Rp 50.000 dan total hadiah menarik",
  "category": "competition",
  "audiences": ["umum"],
  "registration_date": "1 Maret 2026 - 31 Maret 2026",
  "contact": "081234567890",
  "event_type": "online",
  "fee_type": "berbayar",
  "organizer": null,
  "registration_url": "https://bit.ly/mathchallenge"
}}

EXAMPLE 2 (Vague/ambiguous caption):
Input: "Ada yang satu UKM nggak nih? 👀\\n#infolomba #lngshot #ukm"
Output: {{
  "post_id": "XYZ789",
  "title": "LNGSHOT",
  "description": "Informasi lomba terkait UKM. Lihat poster untuk detail lengkap.",
  "category": "competition",
  "audiences": ["s1"],
  "registration_date": null,
  "contact": null,
  "event_type": "online",
  "fee_type": "gratis",
  "organizer": null,
  "registration_url": null
}}

EXAMPLE 3 (English caption):
Input: "English Training Program\\nFREE 100%\\n6 months intensive + 2 months OJT\\nJob opportunities"
Output: {{
  "post_id": "DEF456",
  "title": "English Training Program",
  "description": "Program pelatihan bahasa Inggris gratis selama 6 bulan dengan OJT dan peluang kerja",
  "category": "training",
  "audiences": ["umum"],
  "registration_date": null,
  "contact": null,
  "event_type": "online",
  "fee_type": "gratis",
  "organizer": null,
  "registration_url": null
}}

EXAMPLE 4 (OCR-heavy - details in image):
Input Caption: "LOMBA DESAIN POSTER 2026 🎨\\nLihat poster untuk detail lengkap!\\n#lomba #desain"
Input Image Text (OCR, 85% confidence): "LOMBA DESAIN POSTER NASIONAL 2026\\nPendaftaran: 15-30 April 2026\\nCP: 0812-3456-7890\\nLink: bit.ly/desainposter2026\\nOrganizer: Universitas Indonesia\\nGRATIS"
Output: {{
  "post_id": "OCR123",
  "title": "LOMBA DESAIN POSTER 2026",
  "description": "Lomba desain poster tingkat nasional. Lihat poster untuk detail lengkap.",
  "category": "competition",
  "audiences": ["sma", "s1"],
  "registration_date": "15 April 2026 - 30 April 2026",
  "contact": "081234567890",
  "event_type": "online",
  "fee_type": "gratis",
  "organizer": "Universitas Indonesia",
  "registration_url": "bit.ly/desainposter2026"
}}

NOTE: Caption says "Lihat poster untuk detail lengkap" - this means check IMAGE TEXT!
All details (dates, contact, URL, organizer) were extracted from IMAGE TEXT, not caption.

CRITICAL REMINDERS:
- Title: Keep original language from caption
- Description: ALWAYS in Bahasa Indonesia
- For vague captions: Use "Informasi [category] terkait [topic]. Lihat poster untuk detail lengkap."

Return ONLY the JSON array, no other text.
"""
        
        return prompt
    
    def process_batch(self, captions_batch: List[Dict], ocr_texts: Dict[str, tuple] = None, send_images: bool = True) -> List[Dict]:
        """
        Process a batch of captions using Gemini API with comprehensive error handling
        
        Args:
            captions_batch: List of caption dictionaries
            ocr_texts: Optional dict mapping post_id to (ocr_text, confidence) tuples
            send_images: If True, send actual images to Gemini Vision API (RECOMMENDED for better accuracy)
        """
        
        logger.info(f"[BATCH] Processing {len(captions_batch)} captions...")
        
        # Check if we should send images to Gemini
        if send_images:
            logger.info(f"[IMAGES] Preparing to send {len(captions_batch)} images to Gemini Vision API...")
        
        # PROACTIVE KEY ROTATION: Rotate to next key before each request
        # This distributes load evenly across all 5 projects
        if len(config.GEMINI_API_KEYS) > 1:
            config.get_next_api_key()
            self._initialize_client(config.GEMINI_API_KEY)
            logger.info(f"[KEY ROTATION] Using API key #{config.CURRENT_KEY_INDEX + 1}/{len(config.GEMINI_API_KEYS)}")
        
        logger.info(f"[API] Sending request to Gemini API (this may take 30-60 seconds)...")
        
        try:
            import time
            from PIL import Image
            import io
            api_start_time = time.time()
            
            # Prepare multimodal content if images are enabled
            if send_images:
                contents = self._create_multimodal_content(captions_batch, ocr_texts)
            else:
                # Text-only mode (legacy)
                prompt = self.create_batch_prompt(captions_batch, ocr_texts)
                contents = prompt
            
            # Call Gemini API with retry logic
            response = None
            last_error = None
            
            # Track which API keys we've tried
            tried_combinations = set()
            tried_combinations.add((config.CURRENT_KEY_INDEX, config.CURRENT_MODEL_INDEX))
            
            # Maximum attempts: all keys (no model rotation since we only have 1 model)
            max_attempts = len(config.GEMINI_API_KEYS) * 2  # 2 attempts per key
            
            for attempt in range(1, max_attempts + 1):
                try:
                    # Log progress for attempts after the first
                    if attempt > 1:
                        logger.info(f"[RETRY] Attempt {attempt}/{max_attempts} with key #{config.CURRENT_KEY_INDEX + 1}, model: {config.GEMINI_MODEL}")
                    
                    # New API call
                    response = self.client.models.generate_content(
                        model=config.GEMINI_MODEL,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            temperature=config.TEMPERATURE,
                        )
                    )
                    response_text = response.text
                    
                    # Success - break retry loop
                    api_duration = time.time() - api_start_time
                    logger.info(f"[SUCCESS] Response received in {api_duration:.1f}s with key #{config.CURRENT_KEY_INDEX + 1}, model: {config.GEMINI_MODEL}")
                    break
                    
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
                    is_auth_error = 'api key' in error_msg or 'authentication' in error_msg or '403' in error_msg or 'forbidden' in error_msg
                    is_model_error = 'model' in error_msg and '403' in error_msg
                    is_region_error = ('region' in error_msg or 'location' in error_msg or 'country' in error_msg) and '403' in error_msg
                    is_tos_error = 'terms of service' in error_msg or 'tos' in error_msg or 'violation' in error_msg
                    is_server_error = '503' in error_msg or 'service unavailable' in error_msg or '500' in error_msg or '502' in error_msg
                    
                    # Log error details
                    if is_server_error:
                        # Server overload - wait and retry with exponential backoff
                        wait_time = min(2 ** attempt, 60)  # Max 60 seconds
                        logger.warning(f"[WARNING] Server error (503/500) - waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                        logger.info(f"[RETRY] Retrying with key #{config.CURRENT_KEY_INDEX + 1}, model: {config.GEMINI_MODEL} (attempt {attempt}/{max_attempts})")
                        continue
                    elif is_model_error:
                        logger.warning(f"[WARNING] Model access denied for {config.GEMINI_MODEL} on key #{config.CURRENT_KEY_INDEX + 1}")
                    elif is_region_error:
                        logger.error(f"[ERROR] Geographic restriction detected - API not available in this region")
                        return []
                    elif is_tos_error:
                        logger.error(f"[ERROR] Terms of Service violation detected on key #{config.CURRENT_KEY_INDEX + 1}")
                        # Try next key, this one is flagged
                    elif is_quota_error:
                        logger.warning(f"[WARNING] Quota exceeded on key #{config.CURRENT_KEY_INDEX + 1}")
                    elif is_auth_error:
                        logger.warning(f"[WARNING] Authentication failed on key #{config.CURRENT_KEY_INDEX + 1}")
                    else:
                        logger.warning(f"[WARNING] Error: {str(e)[:100]}")
                    
                    # Determine next action
                    should_rotate_key = is_quota_error or is_auth_error or is_tos_error
                    
                    # Try rotating key if needed
                    if should_rotate_key:
                        # Check if we have more keys to try
                        if len(tried_combinations) < len(config.GEMINI_API_KEYS):
                            if self._rotate_api_key():
                                tried_combinations.add((config.CURRENT_KEY_INDEX, config.CURRENT_MODEL_INDEX))
                                logger.info(f"[RETRY] Retrying with key #{config.CURRENT_KEY_INDEX + 1}, model: {config.GEMINI_MODEL} (attempt {attempt}/{max_attempts})")
                                continue
                        
                        # All keys exhausted
                        logger.error(f"[ERROR] All {len(config.GEMINI_API_KEYS)} API keys exhausted")
                        return []
                    
                    # For other errors, use exponential backoff
                    if attempt < max_attempts:
                        wait_time = min(2 ** attempt, 30)  # Cap at 30 seconds
                        logger.warning(f"Retrying in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"All {max_attempts} attempts failed")
                        raise last_error
            
            if response is None:
                logger.error("[ERROR] No response received from API")
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
