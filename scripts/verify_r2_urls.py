"""
Verify R2 URLs in Database
Test that updated URLs are working correctly
"""

import sys
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.database.client import DatabaseClient
from src.extraction.utils.config import config

def test_url(url: str, timeout: int = 10) -> tuple[bool, str]:
    """Test if URL returns valid image"""
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        
        if response.status_code == 200:
            content_type = response.headers.get('Content-Type', '')
            if 'image' in content_type:
                return True, f"OK ({content_type})"
            else:
                return False, f"Invalid content-type: {content_type}"
        else:
            return False, f"HTTP {response.status_code}"
            
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def main():
    """Main verification function"""
    
    print("="*70)
    print("R2 URL VERIFICATION")
    print("="*70)
    
    # Connect to database
    db = DatabaseClient(config.DATABASE_URL)
    db.connect()
    
    # Get R2 URLs count
    result = db.execute_query("""
        SELECT COUNT(*) as count
        FROM opportunities
        WHERE image_url LIKE '%infortic-images.gerrymoeis.workers.dev%'
    """)
    
    total_r2_urls = result[0]['count']
    print(f"\nTotal R2 URLs in database: {total_r2_urls}")
    
    # Get sample URLs for testing
    print("\nFetching sample URLs for testing...")
    samples = db.execute_query("""
        SELECT post_id, title, image_url
        FROM opportunities
        WHERE image_url LIKE '%infortic-images.gerrymoeis.workers.dev%'
        ORDER BY RANDOM()
        LIMIT 10
    """)
    
    print(f"Testing {len(samples)} random URLs...\n")
    
    # Test each URL
    success_count = 0
    failed_urls = []
    
    for i, sample in enumerate(samples, 1):
        url = sample['image_url']
        title = sample['title'][:40]
        
        print(f"[{i}/10] Testing: {title}...")
        success, message = test_url(url)
        
        if success:
            print(f"        ✅ {message}")
            success_count += 1
        else:
            print(f"        ❌ {message}")
            failed_urls.append({
                'post_id': sample['post_id'],
                'title': title,
                'url': url,
                'error': message
            })
    
    # Summary
    print(f"\n{'='*70}")
    print("VERIFICATION SUMMARY")
    print('='*70)
    print(f"Total R2 URLs in DB:  {total_r2_urls}")
    print(f"Sample tested:        {len(samples)}")
    print(f"Success:              {success_count}/{len(samples)}")
    print(f"Failed:               {len(failed_urls)}/{len(samples)}")
    
    if failed_urls:
        print(f"\n⚠️  Failed URLs:")
        for fail in failed_urls:
            print(f"  - {fail['post_id']}: {fail['error']}")
    else:
        print(f"\n✅ All sample URLs working correctly!")
    
    print('='*70)
    
    db.close()
    
    # Exit code
    sys.exit(0 if len(failed_urls) == 0 else 1)

if __name__ == '__main__':
    main()
