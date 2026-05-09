"""
Download Images from Neon Database
===================================

This script downloads all images from Instagram URLs stored in Neon DB.
This is a ONE-TIME migration script to prepare for R2 upload.

Usage:
    python scripts/download_images_from_db.py

Output:
    - Downloads images to: scraper/instagram_images/
    - Creates mapping file: data/processed/image_mapping.json
    - Logs progress to: logs/download_images.log

Requirements:
    - DATABASE_URL in config/.env
    - Internet connection
    - ~500MB disk space
"""

import os
import sys
import json
import time
import requests
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.client import DatabaseClient
from src.extraction.utils.config import config
from src.extraction.utils.logger import setup_logger

logger = setup_logger('download_images')

class ImageDownloader:
    def __init__(self, db_client: DatabaseClient, output_dir: Path):
        self.db_client = db_client
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Statistics
        self.stats = {
            'total_opportunities': 0,
            'with_image_url': 0,
            'already_downloaded': 0,
            'download_success': 0,
            'download_failed': 0,
            'invalid_url': 0,
            'total_bytes': 0
        }
        
        # Mapping: post_id -> local_filename
        self.image_mapping = {}
    
    def get_opportunities_with_images(self) -> List[Dict]:
        """
        Query all opportunities with image_url from database
        """
        logger.info("[QUERY] Fetching opportunities with image URLs from database...")
        
        query = """
            SELECT 
                id,
                post_id,
                slug,
                title,
                image_url,
                source_url
            FROM opportunities
            WHERE image_url IS NOT NULL
              AND image_url != ''
              AND status = 'active'
            ORDER BY created_at DESC
        """
        
        cursor = self.db_client.conn.cursor()
        cursor.execute(query)
        
        columns = [desc[0] for desc in cursor.description]
        results = []
        
        for row in cursor.fetchall():
            results.append(dict(zip(columns, row)))
        
        cursor.close()
        
        logger.info(f"[SUCCESS] Found {len(results)} opportunities with images")
        return results
    
    def generate_filename(self, image_url: str, post_id: str) -> str:
        """
        Generate local filename from image URL
        
        Strategy:
        1. Try to extract Instagram post ID from URL
        2. Use post_id as fallback
        3. Preserve extension (.jpg, .webp, etc.)
        """
        # Parse URL
        parsed = urlparse(image_url)
        path = parsed.path
        
        # Get extension
        ext = Path(path).suffix
        if not ext or ext not in ['.jpg', '.jpeg', '.png', '.webp']:
            ext = '.jpg'  # Default to .jpg
        
        # Try to extract Instagram post ID from URL
        # Example: https://scontent.cdninstagram.com/v/t51.2885-15/123456789_123456789_n.jpg
        # We want: 123456789_123456789_n.jpg
        
        filename_from_url = Path(path).name
        
        # If filename looks valid (has Instagram pattern), use it
        if filename_from_url and len(filename_from_url) > 5:
            # Remove query parameters
            filename = filename_from_url.split('?')[0]
            return filename
        
        # Fallback: use post_id
        return f"{post_id}{ext}"
    
    def download_image(self, image_url: str, output_path: Path) -> Tuple[bool, int]:
        """
        Download single image from URL
        
        Returns:
            (success: bool, bytes_downloaded: int)
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
            response = requests.get(
                image_url,
                headers=headers,
                timeout=30,
                stream=True
            )
            
            # Check status
            if response.status_code != 200:
                logger.warning(f"[DOWNLOAD] HTTP {response.status_code}: {image_url}")
                return False, 0
            
            # Check content type
            content_type = response.headers.get('Content-Type', '')
            if not content_type.startswith('image/'):
                logger.warning(f"[DOWNLOAD] Invalid content type '{content_type}': {image_url}")
                return False, 0
            
            # Write to file
            bytes_downloaded = 0
            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
            
            return True, bytes_downloaded
            
        except requests.exceptions.Timeout:
            logger.error(f"[TIMEOUT] Download timeout: {image_url}")
            return False, 0
        except requests.exceptions.RequestException as e:
            logger.error(f"[ERROR] Download failed: {e}")
            return False, 0
        except Exception as e:
            logger.error(f"[ERROR] Unexpected error: {e}")
            return False, 0
    
    def process_all(self) -> Dict:
        """
        Main processing function
        """
        logger.info(f"\n{'='*60}")
        logger.info("[START] IMAGE DOWNLOAD FROM DATABASE")
        logger.info('='*60)
        
        # Get opportunities
        opportunities = self.get_opportunities_with_images()
        self.stats['total_opportunities'] = len(opportunities)
        
        if not opportunities:
            logger.warning("[WARNING] No opportunities with images found!")
            return self.stats
        
        logger.info(f"\n[PROCESS] Processing {len(opportunities)} opportunities...")
        logger.info(f"[OUTPUT] Saving to: {self.output_dir}")
        
        # Process each opportunity
        for i, opp in enumerate(opportunities, 1):
            opp_id = opp['id']
            post_id = opp['post_id']
            slug = opp['slug']
            title = opp['title'][:50]
            image_url = opp['image_url']
            
            # Progress log every 10 items
            if i % 10 == 0 or i == 1:
                logger.info(f"\n[PROGRESS] {i}/{len(opportunities)} ({i/len(opportunities)*100:.1f}%)")
            
            # Validate URL
            if not image_url or not image_url.startswith('http'):
                logger.warning(f"  [{i}] Invalid URL: {title}")
                self.stats['invalid_url'] += 1
                continue
            
            self.stats['with_image_url'] += 1
            
            # Generate filename
            filename = self.generate_filename(image_url, post_id or slug)
            output_path = self.output_dir / filename
            
            # Check if already downloaded
            if output_path.exists():
                logger.debug(f"  [{i}] Already exists: {filename}")
                self.stats['already_downloaded'] += 1
                self.image_mapping[post_id or slug] = filename
                continue
            
            # Download image
            logger.info(f"  [{i}] Downloading: {title}")
            logger.debug(f"       URL: {image_url}")
            logger.debug(f"       File: {filename}")
            
            success, bytes_downloaded = self.download_image(image_url, output_path)
            
            if success:
                self.stats['download_success'] += 1
                self.stats['total_bytes'] += bytes_downloaded
                self.image_mapping[post_id or slug] = filename
                logger.info(f"       ✅ Success ({bytes_downloaded/1024:.1f} KB)")
            else:
                self.stats['download_failed'] += 1
                logger.error(f"       ❌ Failed")
            
            # Rate limiting (be nice to Instagram)
            if i < len(opportunities):
                time.sleep(0.5)  # 500ms delay between downloads
        
        # Save mapping
        self.save_mapping()
        
        # Print summary
        self.print_summary()
        
        return self.stats
    
    def save_mapping(self):
        """
        Save image mapping to JSON file
        """
        mapping_file = config.PROCESSED_DIR / 'image_mapping.json'
        
        with open(mapping_file, 'w', encoding='utf-8') as f:
            json.dump(self.image_mapping, f, indent=2, ensure_ascii=False)
        
        logger.info(f"\n[SAVE] Image mapping saved to: {mapping_file}")
        logger.info(f"       Total mappings: {len(self.image_mapping)}")
    
    def print_summary(self):
        """
        Print download summary
        """
        logger.info(f"\n{'='*60}")
        logger.info("[SUMMARY] IMAGE DOWNLOAD COMPLETE")
        logger.info('='*60)
        logger.info(f"Total opportunities:     {self.stats['total_opportunities']}")
        logger.info(f"With image URL:          {self.stats['with_image_url']}")
        logger.info(f"Already downloaded:      {self.stats['already_downloaded']}")
        logger.info(f"Download success:        {self.stats['download_success']}")
        logger.info(f"Download failed:         {self.stats['download_failed']}")
        logger.info(f"Invalid URL:             {self.stats['invalid_url']}")
        logger.info(f"")
        
        total_mb = self.stats['total_bytes'] / (1024 * 1024)
        logger.info(f"Total downloaded:        {total_mb:.2f} MB")
        
        success_rate = (self.stats['download_success'] / self.stats['with_image_url'] * 100) if self.stats['with_image_url'] > 0 else 0
        logger.info(f"Success rate:            {success_rate:.1f}%")
        logger.info('='*60)

def main():
    """
    Main execution function
    """
    logger.info('[START] Image Download Script Starting...\n')
    
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
        
        # Create output directory
        output_dir = Path(__file__).parent.parent / 'scraper' / 'instagram_images'
        
        # Initialize downloader
        downloader = ImageDownloader(db_client, output_dir)
        
        # Process all images
        stats = downloader.process_all()
        
        # Exit with appropriate code
        if stats['download_failed'] > 0:
            logger.warning(f"\n[WARNING] {stats['download_failed']} downloads failed")
            logger.info("[INFO] You can re-run this script to retry failed downloads")
            sys.exit(1)
        else:
            logger.info("\n[SUCCESS] All images downloaded successfully!")
            sys.exit(0)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        db_client.close()

if __name__ == '__main__':
    main()
