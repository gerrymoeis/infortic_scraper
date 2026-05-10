"""
Upload Images to R2 Before Database Insertion
==============================================

This script runs BEFORE database insertion to ensure
database is populated with R2 URLs from the start.

Workflow:
1. Read extracted_data_TIMESTAMP.json
2. For each record:
   - Read local image from scraper/instagram_images/
   - Optimize to WebP Q70
   - Upload to R2 (update if exists)
   - Replace image_url: Instagram URL → R2 URL
3. Save modified JSON: extracted_data_TIMESTAMP_r2.json

Usage:
    python scripts/upload_to_r2_before_db.py data/processed/extracted_data_20260510_120000.json
"""

import os
import sys
import json
import io
from pathlib import Path
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from PIL import Image
import boto3
from botocore.exceptions import ClientError

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extraction.utils.config import config
from src.extraction.utils.logger import setup_logger

logger = setup_logger('r2_upload')

class R2Uploader:
    def __init__(self):
        # R2 credentials
        self.account_id = os.getenv('R2_ACCOUNT_ID')
        self.access_key = os.getenv('R2_ACCESS_KEY_ID')
        self.secret_key = os.getenv('R2_SECRET_ACCESS_KEY')
        self.bucket_name = os.getenv('R2_BUCKET_NAME', 'infortic-images')
        self.public_url = os.getenv('R2_PUBLIC_URL', '')
        
        self._validate_credentials()
        
        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f'https://{self.account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name='auto'
        )
        
        # Statistics
        self.stats = {
            'total_records': 0,
            'upload_success': 0,
            'upload_failed': 0,
            'already_exists': 0,
            'no_local_image': 0,
            'optimize_failed': 0
        }
    
    def _validate_credentials(self):
        """Validate R2 credentials"""
        missing = []
        if not self.account_id: missing.append('R2_ACCOUNT_ID')
        if not self.access_key: missing.append('R2_ACCESS_KEY_ID')
        if not self.secret_key: missing.append('R2_SECRET_ACCESS_KEY')
        
        if missing:
            logger.error(f"Missing R2 credentials: {', '.join(missing)}")
            sys.exit(1)
        
        logger.info(f"✓ R2 credentials validated")
        logger.info(f"  Bucket: {self.bucket_name}")
        logger.info(f"  Public URL: {self.public_url}")
    
    def check_exists_in_r2(self, key: str) -> bool:
        """Check if image exists in R2"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise
    
    def optimize_to_webp(self, image_path: Path) -> Tuple[bool, bytes, str]:
        """Optimize image to WebP Q70"""
        try:
            img = Image.open(image_path)
            
            # Convert to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                if 'A' in img.mode:
                    background.paste(img, mask=img.split()[-1])
                    img = background
                else:
                    img = img.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Save as WebP Q70
            output = io.BytesIO()
            img.save(output, 'WEBP', quality=70, method=6, lossless=False)
            
            return True, output.getvalue(), ""
        except Exception as e:
            return False, b'', str(e)
    
    def upload_to_r2(self, key: str, image_bytes: bytes) -> Tuple[bool, str]:
        """Upload image to R2"""
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=image_bytes,
                ContentType='image/webp',
                CacheControl='public, max-age=31536000, immutable'
            )
            return True, ""
        except Exception as e:
            return False, str(e)
    
    def process_single(self, record: Dict, index: int, total: int) -> Dict:
        """Process single record"""
        post_id = record.get('post_id', '')
        downloaded_image = record.get('downloaded_image', '')
        
        # Generate R2 key
        r2_key = f"{post_id}.webp"
        r2_url = f"{self.public_url}/{r2_key}"
        
        # Check if already in R2
        if self.check_exists_in_r2(r2_key):
            logger.debug(f"[{index}/{total}] ⏭️  Already in R2: {r2_key}")
            self.stats['already_exists'] += 1
            record['image_url'] = r2_url  # Update URL anyway
            return record
        
        # Check local image
        image_path = Path(__file__).parent.parent / 'scraper' / 'instagram_images' / downloaded_image
        
        if not image_path.exists():
            logger.warning(f"[{index}/{total}] ❌ Local image not found: {downloaded_image}")
            self.stats['no_local_image'] += 1
            return record  # Keep original Instagram URL
        
        # Optimize
        logger.info(f"[{index}/{total}] 🔄 Processing: {post_id}")
        success, optimized_bytes, error = self.optimize_to_webp(image_path)
        
        if not success:
            logger.error(f"  ❌ Optimize failed: {error}")
            self.stats['optimize_failed'] += 1
            return record
        
        # Upload
        success, error = self.upload_to_r2(r2_key, optimized_bytes)
        
        if not success:
            logger.error(f"  ❌ Upload failed: {error}")
            self.stats['upload_failed'] += 1
            return record
        
        # Update URL
        record['image_url'] = r2_url
        self.stats['upload_success'] += 1
        logger.info(f"  ✅ Uploaded: {r2_key}")
        
        return record
    
    def process_all(self, input_file: Path, max_workers: int = 3) -> Path:
        """Process all records"""
        logger.info(f"\n{'='*60}")
        logger.info("[START] R2 Upload Before Database")
        logger.info('='*60)
        logger.info(f"Input: {input_file.name}")
        
        # Load data
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.stats['total_records'] = len(data)
        logger.info(f"Total records: {len(data)}")
        logger.info(f"Parallel workers: {max_workers}")
        
        # Process with parallel workers
        modified_data = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.process_single, record, i+1, len(data)): record
                for i, record in enumerate(data)
            }
            
            for future in as_completed(futures):
                modified_record = future.result()
                modified_data.append(modified_record)
        
        # Save modified JSON
        output_file = input_file.parent / input_file.name.replace('.json', '_r2.json')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(modified_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n{'='*60}")
        logger.info("[COMPLETE] R2 Upload Summary")
        logger.info('='*60)
        logger.info(f"Total records:     {self.stats['total_records']}")
        logger.info(f"Upload success:    {self.stats['upload_success']}")
        logger.info(f"Already exists:    {self.stats['already_exists']}")
        logger.info(f"Upload failed:     {self.stats['upload_failed']}")
        logger.info(f"No local image:    {self.stats['no_local_image']}")
        logger.info(f"Optimize failed:   {self.stats['optimize_failed']}")
        logger.info(f"")
        logger.info(f"Output: {output_file.name}")
        logger.info('='*60)
        
        return output_file

def main():
    """Main execution"""
    if len(sys.argv) < 2:
        logger.error("Usage: python scripts/upload_to_r2_before_db.py <input_file>")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    
    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        sys.exit(1)
    
    uploader = R2Uploader()
    output_file = uploader.process_all(input_file, max_workers=3)
    
    logger.info(f"\n✅ SUCCESS: Modified JSON ready for database insertion")
    logger.info(f"   {output_file}")

if __name__ == '__main__':
    main()
