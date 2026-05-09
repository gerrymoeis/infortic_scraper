"""
Migrate Images to Cloudflare R2
================================

Enhanced migration script that:
1. Downloads images from Instagram URLs in database
2. Optimizes to WebP format (70% quality, ~60% size reduction)
3. Uploads directly to R2 (no local storage)
4. Tracks progress with detailed statistics

Usage:
    python scripts/migrate_images_to_r2.py

Requirements:
    - DATABASE_URL in config/.env
    - R2 credentials in config/.env
    - Internet connection
"""

import os
import sys
import json
import time
import requests
import io
from pathlib import Path
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.client import DatabaseClient
from src.extraction.utils.config import config
from src.extraction.utils.logger import setup_logger
from PIL import Image
import boto3
from botocore.exceptions import ClientError

logger = setup_logger('migrate_r2')

class R2ImageMigrator:
    def __init__(self, db_client: DatabaseClient):
        self.db_client = db_client
        
        # Get R2 credentials
        self.account_id = os.getenv('R2_ACCOUNT_ID')
        self.access_key = os.getenv('R2_ACCESS_KEY_ID')
        self.secret_key = os.getenv('R2_SECRET_ACCESS_KEY')
        self.bucket_name = os.getenv('R2_BUCKET_NAME', 'infortic-images')
        self.public_url = os.getenv('R2_PUBLIC_URL', '')
        
        # Validate credentials
        self._validate_credentials()
        
        # Initialize S3 client for R2
        self.s3_client = boto3.client(
            's3',
            endpoint_url=f'https://{self.account_id}.r2.cloudflarestorage.com',
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            region_name='auto'
        )
        
        # Statistics
        self.stats = {
            'total_opportunities': 0,
            'with_image_url': 0,
            'already_in_r2': 0,
            'download_success': 0,
            'download_failed': 0,
            'optimize_success': 0,
            'optimize_failed': 0,
            'upload_success': 0,
            'upload_failed': 0,
            'invalid_url': 0,
            'total_bytes_original': 0,
            'total_bytes_optimized': 0
        }
        
        # Migration results
        self.results = []
    
    def _validate_credentials(self):
        """Validate R2 credentials"""
        missing = []
        
        if not self.account_id:
            missing.append('R2_ACCOUNT_ID')
        if not self.access_key:
            missing.append('R2_ACCESS_KEY_ID')
        if not self.secret_key:
            missing.append('R2_SECRET_ACCESS_KEY')
        
        if missing:
            logger.error(f"[ERROR] Missing R2 credentials: {', '.join(missing)}")
            logger.info("[INFO] Set these in config/.env")
            sys.exit(1)
        
        logger.info("[SUCCESS] R2 credentials validated")
        logger.info(f"  Account ID: {self.account_id[:8]}...")
        logger.info(f"  Bucket: {self.bucket_name}")
    
    def get_opportunities_with_images(self) -> List[Dict]:
        """Query all opportunities with Instagram image URLs"""
        logger.info("[QUERY] Fetching opportunities from database...")
        
        opportunities = self.db_client.execute_query("""
            SELECT 
                id,
                post_id,
                slug,
                title,
                image_url
            FROM opportunities
            WHERE image_url IS NOT NULL
              AND image_url != ''
              AND status = 'active'
              AND image_url LIKE '%instagram%'
            ORDER BY created_at DESC
        """)
        
        logger.info(f"[SUCCESS] Found {len(opportunities)} opportunities with Instagram images")
        return opportunities
    
    def check_if_exists_in_r2(self, key: str) -> bool:
        """Check if image already exists in R2"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            else:
                logger.warning(f"[WARNING] Error checking R2: {e}")
                return False
    
    def download_image(self, image_url: str) -> Tuple[bool, bytes, str]:
        """
        Download image from Instagram
        
        Returns:
            (success: bool, image_bytes: bytes, error_message: str)
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/*',
                'Referer': 'https://www.instagram.com/'
            }
            
            response = requests.get(image_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                return False, b'', f"HTTP {response.status_code}"
            
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                return False, b'', f"Invalid content type: {content_type}"
            
            return True, response.content, ""
            
        except requests.exceptions.Timeout:
            return False, b'', "Timeout"
        except Exception as e:
            return False, b'', str(e)
    
    def optimize_to_webp(self, image_bytes: bytes) -> Tuple[bool, bytes, str]:
        """
        Optimize image to WebP format (70% quality, ~60% reduction)
        
        Returns:
            (success: bool, optimized_bytes: bytes, error_message: str)
        """
        try:
            # Load image
            img = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB if needed (WebP doesn't support RGBA well)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background
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
            
            # Save as WebP
            output = io.BytesIO()
            img.save(
                output,
                'WEBP',
                quality=70,        # 70% quality (optimal for web, ~60% reduction)
                method=6,          # Max compression effort
                lossless=False
            )
            
            optimized_bytes = output.getvalue()
            
            return True, optimized_bytes, ""
            
        except Exception as e:
            return False, b'', str(e)
    
    def upload_to_r2(self, key: str, image_bytes: bytes) -> Tuple[bool, str]:
        """
        Upload image to R2
        
        Returns:
            (success: bool, error_message: str)
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=image_bytes,
                ContentType='image/webp',
                CacheControl='public, max-age=31536000, immutable',  # 1 year
                Metadata={
                    'uploaded-by': 'infortic-migration-script',
                    'upload-date': time.strftime('%Y-%m-%d')
                }
            )
            
            return True, ""
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            return False, f"{error_code}: {error_message}"
        except Exception as e:
            return False, str(e)
    
    def process_single(self, opp: Dict, index: int, total: int) -> Dict:
        """Process single opportunity (download + optimize + upload)"""
        
        result = {
            'id': opp['id'],
            'post_id': opp['post_id'],
            'slug': opp['slug'],
            'title': opp['title'][:50],
            'instagram_url': opp['image_url'],
            'r2_key': None,
            'r2_url': None,
            'success': False,
            'bytes_original': 0,
            'bytes_optimized': 0,
            'error': None,
            'skipped': False
        }
        
        # Generate R2 key (filename)
        post_id = opp['post_id'] or opp['slug']
        r2_key = f"{post_id}.webp"
        result['r2_key'] = r2_key
        result['r2_url'] = f"{self.public_url}/{r2_key}" if self.public_url else None
        
        # Check if already in R2
        if self.check_if_exists_in_r2(r2_key):
            result['success'] = True
            result['skipped'] = True
            logger.debug(f"  [{index}/{total}] ⏭️  Already in R2: {r2_key}")
            return result
        
        # Download from Instagram
        logger.info(f"  [{index}/{total}] ⬇️  Downloading: {result['title']}")
        download_success, image_bytes, download_error = self.download_image(opp['image_url'])
        
        if not download_success:
            result['error'] = f"Download failed: {download_error}"
            logger.error(f"       ❌ {download_error}")
            return result
        
        result['bytes_original'] = len(image_bytes)
        logger.debug(f"       ✅ Downloaded ({len(image_bytes)/1024:.1f} KB)")
        
        # Optimize to WebP
        logger.debug(f"       🔄 Optimizing to WebP...")
        optimize_success, optimized_bytes, optimize_error = self.optimize_to_webp(image_bytes)
        
        if not optimize_success:
            result['error'] = f"Optimization failed: {optimize_error}"
            logger.error(f"       ❌ {optimize_error}")
            return result
        
        result['bytes_optimized'] = len(optimized_bytes)
        reduction = (1 - len(optimized_bytes) / len(image_bytes)) * 100
        logger.info(f"       ✅ Optimized ({len(optimized_bytes)/1024:.1f} KB, {reduction:.1f}% reduction)")
        
        # Upload to R2
        logger.debug(f"       ⬆️  Uploading to R2...")
        upload_success, upload_error = self.upload_to_r2(r2_key, optimized_bytes)
        
        if not upload_success:
            result['error'] = f"Upload failed: {upload_error}"
            logger.error(f"       ❌ {upload_error}")
            return result
        
        result['success'] = True
        logger.info(f"       ✅ Uploaded to R2: {r2_key}")
        
        return result
    
    def process_all(self, max_workers: int = 3) -> Dict:
        """
        Main processing function with parallel execution
        
        Args:
            max_workers: Number of parallel workers (default: 3, be nice to Instagram)
        """
        logger.info(f"\n{'='*60}")
        logger.info("[START] R2 IMAGE MIGRATION")
        logger.info('='*60)
        
        # Get opportunities
        opportunities = self.get_opportunities_with_images()
        self.stats['total_opportunities'] = len(opportunities)
        self.stats['with_image_url'] = len(opportunities)
        
        if not opportunities:
            logger.warning("[WARNING] No opportunities with Instagram images found!")
            return self.stats
        
        logger.info(f"\n[PROCESS] Migrating {len(opportunities)} images...")
        logger.info(f"[PARALLEL] Using {max_workers} parallel workers")
        logger.info(f"[DESTINATION] R2 bucket: {self.bucket_name}")
        
        # Process with parallel workers
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(self.process_single, opp, i+1, len(opportunities)): opp
                for i, opp in enumerate(opportunities)
            }
            
            # Process results as they complete
            for future in as_completed(futures):
                result = future.result()
                self.results.append(result)
                
                # Update statistics
                if result['skipped']:
                    self.stats['already_in_r2'] += 1
                elif result['success']:
                    self.stats['download_success'] += 1
                    self.stats['optimize_success'] += 1
                    self.stats['upload_success'] += 1
                    self.stats['total_bytes_original'] += result['bytes_original']
                    self.stats['total_bytes_optimized'] += result['bytes_optimized']
                else:
                    if 'Download failed' in result.get('error', ''):
                        self.stats['download_failed'] += 1
                    elif 'Optimization failed' in result.get('error', ''):
                        self.stats['optimize_failed'] += 1
                    elif 'Upload failed' in result.get('error', ''):
                        self.stats['upload_failed'] += 1
        
        # Save migration report
        self.save_report()
        
        # Print summary
        self.print_summary()
        
        return self.stats
    
    def save_report(self):
        """Save migration report to JSON file"""
        from src.extraction.utils.helpers import get_timestamp
        
        report_file = config.PROCESSED_DIR / f'r2_migration_report_{get_timestamp()}.json'
        
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'bucket': self.bucket_name,
            'public_url': self.public_url,
            'statistics': self.stats,
            'results': self.results
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n[SAVE] Migration report saved to: {report_file}")
    
    def print_summary(self):
        """Print migration summary"""
        logger.info(f"\n{'='*60}")
        logger.info("[SUMMARY] R2 MIGRATION COMPLETE")
        logger.info('='*60)
        logger.info(f"Total opportunities:     {self.stats['total_opportunities']}")
        logger.info(f"Already in R2:           {self.stats['already_in_r2']}")
        logger.info(f"Download success:        {self.stats['download_success']}")
        logger.info(f"Download failed:         {self.stats['download_failed']}")
        logger.info(f"Optimize success:        {self.stats['optimize_success']}")
        logger.info(f"Optimize failed:         {self.stats['optimize_failed']}")
        logger.info(f"Upload success:          {self.stats['upload_success']}")
        logger.info(f"Upload failed:           {self.stats['upload_failed']}")
        logger.info(f"")
        
        if self.stats['total_bytes_original'] > 0:
            original_mb = self.stats['total_bytes_original'] / (1024 * 1024)
            optimized_mb = self.stats['total_bytes_optimized'] / (1024 * 1024)
            reduction = (1 - self.stats['total_bytes_optimized'] / self.stats['total_bytes_original']) * 100
            
            logger.info(f"Total original size:     {original_mb:.2f} MB")
            logger.info(f"Total optimized size:    {optimized_mb:.2f} MB")
            logger.info(f"Total reduction:         {reduction:.1f}%")
        
        total_success = self.stats['upload_success'] + self.stats['already_in_r2']
        success_rate = (total_success / self.stats['total_opportunities'] * 100) if self.stats['total_opportunities'] > 0 else 0
        logger.info(f"Success rate:            {success_rate:.1f}%")
        logger.info('='*60)

def main():
    """Main execution function"""
    logger.info('[START] R2 Migration Script Starting...\n')
    
    # Validate database configuration
    if not config.DATABASE_URL:
        logger.error("DATABASE_URL not set in environment!")
        logger.info("Please set DATABASE_URL in config/.env")
        sys.exit(1)
    
    # Initialize database client
    logger.info("[CONNECT] Connecting to database...")
    db_client = DatabaseClient(config.DATABASE_URL)
    
    try:
        db_client.connect()
        logger.info("[SUCCESS] Database connected")
        
        # Initialize migrator
        migrator = R2ImageMigrator(db_client)
        
        # Process all images
        stats = migrator.process_all(max_workers=3)
        
        # Exit with appropriate code
        if stats['download_failed'] > 0 or stats['upload_failed'] > 0:
            logger.warning(f"\n[WARNING] Some migrations failed")
            logger.info(f"  Download failures: {stats['download_failed']}")
            logger.info(f"  Upload failures: {stats['upload_failed']}")
            logger.info("[INFO] You can re-run this script to retry failed migrations")
            sys.exit(1)
        else:
            logger.info("\n[SUCCESS] All images migrated successfully!")
            sys.exit(0)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db_client.close()

if __name__ == '__main__':
    main()
