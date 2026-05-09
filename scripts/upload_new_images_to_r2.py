"""
Upload New Images to Cloudflare R2 (Daily Workflow)
====================================================

This script uploads newly scraped images to Cloudflare R2 bucket.
This is part of the DAILY automated workflow (GitHub Actions).

Differences from upload_to_r2.py:
- This script is for DAILY workflow (new images only)
- upload_to_r2.py is for ONE-TIME migration (all existing images)

Usage:
    python scripts/upload_new_images_to_r2.py <extracted_data_file>

Requirements:
    - R2 credentials in environment variables
    - Extracted data JSON file with instagram_image_url field
    - Internet connection

Output:
    - Uploads images to R2
    - Creates upload report: data/processed/r2_daily_upload_report_*.json
    - Logs progress to: logs/upload_new_images_to_r2.log
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extraction.utils.config import config
from src.extraction.utils.logger import setup_logger

# Import AWS SDK for S3 (R2 is S3-compatible)
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("ERROR: boto3 not installed!")
    print("Install with: pip install boto3")
    sys.exit(1)

logger = setup_logger('upload_new_images_r2')

class NewImageUploader:
    def __init__(self, extracted_data_file: Path):
        self.extracted_data_file = extracted_data_file
        
        # Get R2 credentials from environment
        self.account_id = os.getenv('R2_ACCOUNT_ID')
        self.access_key_id = os.getenv('R2_ACCESS_KEY_ID')
        self.secret_access_key = os.getenv('R2_SECRET_ACCESS_KEY')
        self.bucket_name = os.getenv('R2_BUCKET_NAME', 'infortic-images')
        self.public_url = os.getenv('R2_PUBLIC_URL', '')
        
        # Validate credentials
        self.validate_credentials()
        
        # Initialize S3 client for R2
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f'https://{self.account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name='auto'
        )
        
        # Statistics
        self.stats = {
            'total_opportunities': 0,
            'with_instagram_url': 0,
            'already_uploaded': 0,
            'download_success': 0,
            'download_failed': 0,
            'upload_success': 0,
            'upload_failed': 0,
            'total_bytes': 0
        }
        
        # Upload results
        self.upload_results = []
    
    def validate_credentials(self):
        """Validate R2 credentials"""
        missing = []
        
        if not self.account_id:
            missing.append('R2_ACCOUNT_ID')
        if not self.access_key_id:
            missing.append('R2_ACCESS_KEY_ID')
        if not self.secret_access_key:
            missing.append('R2_SECRET_ACCESS_KEY')
        
        if missing:
            logger.error(f"[ERROR] Missing R2 credentials: {', '.join(missing)}")
            logger.info("[INFO] Set these environment variables:")
            for var in missing:
                logger.info(f"  export {var}=<value>")
            sys.exit(1)
        
        logger.info("[SUCCESS] R2 credentials validated")
        logger.info(f"  Account ID: {self.account_id[:8]}...")
        logger.info(f"  Bucket: {self.bucket_name}")
        logger.info(f"  Public URL: {self.public_url}")
    
    def load_extracted_data(self) -> List[Dict]:
        """Load extracted data from JSON file"""
        if not self.extracted_data_file.exists():
            logger.error(f"[ERROR] File not found: {self.extracted_data_file}")
            sys.exit(1)
        
        with open(self.extracted_data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        logger.info(f"[LOAD] Loaded {len(data)} opportunities")
        return data
    
    def get_content_type(self, filename: str) -> str:
        """Get content type from filename extension"""
        ext = Path(filename).suffix.lower()
        
        content_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.webp': 'image/webp',
            '.gif': 'image/gif'
        }
        
        return content_types.get(ext, 'application/octet-stream')
    
    def extract_filename_from_url(self, url: str) -> str:
        """Extract filename from Instagram URL"""
        parsed = urlparse(url)
        path = parsed.path
        
        # Get filename from path
        filename = Path(path).name
        
        # Remove query parameters
        filename = filename.split('?')[0]
        
        return filename
    
    def check_if_exists(self, key: str) -> bool:
        """Check if object already exists in R2"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.warning(f"[WARNING] Error checking existence: {e}")
                return False
    
    def download_image(self, url: str) -> Tuple[bool, bytes, str]:
        """
        Download image from Instagram URL
        
        Returns:
            (success: bool, image_bytes: bytes, error_message: str)
        """
        try:
            # Set headers to mimic browser
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://www.instagram.com/',
                'Sec-Fetch-Dest': 'image',
                'Sec-Fetch-Mode': 'no-cors',
                'Sec-Fetch-Site': 'cross-site'
            }
            
            # Download with timeout
            response = requests.get(url, headers=headers, timeout=30)
            
            # Check status
            if response.status_code != 200:
                return False, b'', f"HTTP {response.status_code}"
            
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                return False, b'', f"Invalid content type: {content_type}"
            
            return True, response.content, ""
            
        except requests.exceptions.Timeout:
            return False, b'', "Timeout"
        except requests.exceptions.RequestException as e:
            return False, b'', str(e)
        except Exception as e:
            return False, b'', str(e)
    
    def upload_to_r2(self, key: str, image_bytes: bytes) -> Tuple[bool, str]:
        """
        Upload image bytes to R2
        
        Returns:
            (success: bool, error_message: str)
        """
        try:
            content_type = self.get_content_type(key)
            
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=image_bytes,
                ContentType=content_type,
                CacheControl='public, max-age=31536000',  # 1 year cache
                Metadata={
                    'uploaded-by': 'infortic-daily-workflow',
                    'upload-date': time.strftime('%Y-%m-%d')
                }
            )
            
            return True, ""
            
        except NoCredentialsError:
            return False, "Invalid R2 credentials"
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            return False, f"{error_code}: {error_message}"
        except Exception as e:
            return False, str(e)
    
    def process_single(self, opportunity: Dict, index: int, total: int) -> Dict:
        """Process single opportunity (download + upload)"""
        
        result = {
            'post_id': opportunity.get('post_id'),
            'title': opportunity.get('title', '')[:50],
            'instagram_url': opportunity.get('instagram_image_url'),
            'r2_url': opportunity.get('image_url'),
            'success': False,
            'bytes': 0,
            'error': None
        }
        
        # Check if has instagram_image_url
        instagram_url = opportunity.get('instagram_image_url')
        if not instagram_url:
            result['error'] = "No instagram_image_url field"
            logger.debug(f"  [{index}/{total}] ⏭️  Skipped: {result['title']} (no Instagram URL)")
            return result
        
        # Extract filename from R2 URL (pre-generated)
        r2_url = opportunity.get('image_url', '')
        if not r2_url:
            result['error'] = "No image_url field (R2 URL)"
            logger.warning(f"  [{index}/{total}] ⚠️  No R2 URL: {result['title']}")
            return result
        
        # Extract key from R2 URL
        # Example: https://pub-xxxxx.r2.dev/filename.jpg -> filename.jpg
        key = r2_url.split('/')[-1]
        
        # Check if already uploaded
        if self.check_if_exists(key):
            result['success'] = True
            result['already_uploaded'] = True
            logger.debug(f"  [{index}/{total}] ⏭️  Already uploaded: {key}")
            return result
        
        # Download from Instagram
        logger.info(f"  [{index}/{total}] ⬇️  Downloading: {result['title']}")
        logger.debug(f"       Instagram URL: {instagram_url}")
        
        download_success, image_bytes, download_error = self.download_image(instagram_url)
        
        if not download_success:
            result['error'] = f"Download failed: {download_error}"
            logger.error(f"       ❌ Download failed: {download_error}")
            return result
        
        result['bytes'] = len(image_bytes)
        logger.debug(f"       ✅ Downloaded ({len(image_bytes)/1024:.1f} KB)")
        
        # Upload to R2
        logger.info(f"       ⬆️  Uploading to R2: {key}")
        
        upload_success, upload_error = self.upload_to_r2(key, image_bytes)
        
        if not upload_success:
            result['error'] = f"Upload failed: {upload_error}"
            logger.error(f"       ❌ Upload failed: {upload_error}")
            return result
        
        result['success'] = True
        result['already_uploaded'] = False
        logger.info(f"       ✅ Upload success")
        
        return result
    
    def process_all(self, max_workers: int = 5) -> Dict:
        """
        Main processing function with parallel uploads
        
        Args:
            max_workers: Number of parallel workers (default: 5)
        """
        logger.info(f"\n{'='*60}")
        logger.info("[START] DAILY R2 IMAGE UPLOAD")
        logger.info('='*60)
        
        # Load extracted data
        opportunities = self.load_extracted_data()
        self.stats['total_opportunities'] = len(opportunities)
        
        # Filter opportunities with instagram_image_url
        opportunities_with_images = [
            opp for opp in opportunities
            if opp.get('instagram_image_url')
        ]
        
        self.stats['with_instagram_url'] = len(opportunities_with_images)
        
        if not opportunities_with_images:
            logger.warning("[WARNING] No opportunities with instagram_image_url found!")
            return self.stats
        
        logger.info(f"\n[PROCESS] Processing {len(opportunities_with_images)} opportunities...")
        logger.info(f"[PARALLEL] Using {max_workers} parallel workers")
        logger.info(f"[DESTINATION] R2 bucket: {self.bucket_name}")
        
        # Process with parallel workers
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(self.process_single, opp, i+1, len(opportunities_with_images)): opp
                for i, opp in enumerate(opportunities_with_images)
            }
            
            # Process results as they complete
            for future in as_completed(futures):
                result = future.result()
                self.upload_results.append(result)
                
                # Update statistics
                if result.get('instagram_url'):
                    if result['success']:
                        if result.get('already_uploaded'):
                            self.stats['already_uploaded'] += 1
                        else:
                            self.stats['upload_success'] += 1
                            self.stats['download_success'] += 1
                        self.stats['total_bytes'] += result['bytes']
                    else:
                        if 'Download failed' in result.get('error', ''):
                            self.stats['download_failed'] += 1
                        elif 'Upload failed' in result.get('error', ''):
                            self.stats['upload_failed'] += 1
                            self.stats['download_success'] += 1
        
        # Save upload report
        self.save_report()
        
        # Print summary
        self.print_summary()
        
        return self.stats
    
    def save_report(self):
        """Save upload report to JSON file"""
        from src.extraction.utils.helpers import get_timestamp
        
        report_file = config.PROCESSED_DIR / f'r2_daily_upload_report_{get_timestamp()}.json'
        
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'bucket': self.bucket_name,
            'public_url': self.public_url,
            'statistics': self.stats,
            'results': self.upload_results
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n[SAVE] Upload report saved to: {report_file}")
    
    def print_summary(self):
        """Print upload summary"""
        logger.info(f"\n{'='*60}")
        logger.info("[SUMMARY] DAILY R2 UPLOAD COMPLETE")
        logger.info('='*60)
        logger.info(f"Total opportunities:     {self.stats['total_opportunities']}")
        logger.info(f"With Instagram URL:      {self.stats['with_instagram_url']}")
        logger.info(f"Already uploaded:        {self.stats['already_uploaded']}")
        logger.info(f"Download success:        {self.stats['download_success']}")
        logger.info(f"Download failed:         {self.stats['download_failed']}")
        logger.info(f"Upload success:          {self.stats['upload_success']}")
        logger.info(f"Upload failed:           {self.stats['upload_failed']}")
        logger.info(f"")
        
        total_mb = self.stats['total_bytes'] / (1024 * 1024)
        logger.info(f"Total uploaded:          {total_mb:.2f} MB")
        
        total_processed = self.stats['upload_success'] + self.stats['already_uploaded']
        success_rate = (total_processed / self.stats['with_instagram_url'] * 100) if self.stats['with_instagram_url'] > 0 else 0
        logger.info(f"Success rate:            {success_rate:.1f}%")
        logger.info('='*60)
        
        # Show failed uploads if any
        if self.stats['download_failed'] > 0 or self.stats['upload_failed'] > 0:
            logger.warning(f"\n[FAILED OPERATIONS]")
            for result in self.upload_results:
                if not result['success'] and result.get('error'):
                    logger.warning(f"  - {result['title']}: {result['error']}")

def main():
    """Main execution function"""
    logger.info('[START] Daily R2 Upload Script Starting...\n')
    
    # Get input file from command line
    if len(sys.argv) < 2:
        logger.error("[ERROR] No input file specified!")
        logger.info("Usage: python scripts/upload_new_images_to_r2.py <extracted_data_file>")
        logger.info("Example: python scripts/upload_new_images_to_r2.py data/processed/extracted_data_20260503_100000.json")
        sys.exit(1)
    
    input_file = Path(sys.argv[1])
    
    # Validate input file
    if not input_file.exists():
        logger.error(f"[ERROR] File not found: {input_file}")
        sys.exit(1)
    
    # Initialize uploader
    try:
        uploader = NewImageUploader(input_file)
        
        # Process all images
        stats = uploader.process_all(max_workers=5)
        
        # Exit with appropriate code
        if stats['download_failed'] > 0 or stats['upload_failed'] > 0:
            logger.warning(f"\n[WARNING] Some uploads failed")
            logger.info(f"  Download failures: {stats['download_failed']}")
            logger.info(f"  Upload failures: {stats['upload_failed']}")
            logger.info("[INFO] This is normal for Instagram rate limiting")
            logger.info("[INFO] Failed images will be retried in next run")
            sys.exit(0)  # Exit 0 to not fail the workflow
        else:
            logger.info("\n[SUCCESS] All images uploaded successfully!")
            sys.exit(0)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
