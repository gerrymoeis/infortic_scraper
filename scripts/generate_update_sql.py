"""
Generate SQL Update Query from Migration Report
Generates SQL to update image URLs in database after successful R2 migration
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.extraction.utils.config import config

def generate_update_sql(report_file: Path, output_file: Path):
    """Generate SQL update query from migration report"""
    
    print(f"Reading migration report: {report_file}")
    
    with open(report_file, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    # Get successful migrations
    successful = [
        r for r in report['results'] 
        if r['success'] and not r.get('skipped', False)
    ]
    
    print(f"Found {len(successful)} successful migrations")
    
    if not successful:
        print("No successful migrations found!")
        return
    
    # Get public URL from report
    public_url = report.get('public_url', 'https://infortic-images.gerrymoeis.workers.dev')
    
    # Generate SQL
    sql_lines = [
        "-- Update Image URLs to R2 CDN",
        f"-- Generated from: {report_file.name}",
        f"-- Total images: {len(successful)}",
        f"-- Worker URL: {public_url}",
        "-- Date: " + report['timestamp'],
        "",
        "UPDATE opportunities",
        "SET image_url = CASE post_id"
    ]
    
    # Add CASE statements for each image
    for result in successful:
        post_id = result['post_id']
        r2_url = result['r2_url']
        sql_lines.append(f"  WHEN '{post_id}' THEN '{r2_url}'")
    
    # Close CASE and add WHERE clause
    sql_lines.extend([
        "  ELSE image_url",
        "END",
        "WHERE post_id IN ("
    ])
    
    # Add post_ids
    post_ids = [f"  '{r['post_id']}'" for r in successful]
    sql_lines.append(",\n".join(post_ids))
    
    sql_lines.extend([
        ");",
        "",
        "-- Verify update",
        "SELECT COUNT(*) as updated_count",
        "FROM opportunities",
        "WHERE image_url LIKE '%infortic-images.gerrymoeis.workers.dev%';",
        "",
        f"-- Expected: {len(successful)} rows updated"
    ])
    
    # Write to file
    sql_content = "\n".join(sql_lines)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(sql_content)
    
    print(f"\n✅ SQL generated successfully!")
    print(f"Output: {output_file}")
    print(f"\nTo apply:")
    print(f"1. Review the SQL file")
    print(f"2. Run in Neon SQL Editor")
    print(f"3. Verify {len(successful)} rows updated")

def main():
    """Main execution"""
    
    # Find latest migration report
    processed_dir = config.PROCESSED_DIR
    reports = list(processed_dir.glob('r2_migration_report_*.json'))
    
    if not reports:
        print("No migration reports found!")
        print(f"Looking in: {processed_dir}")
        sys.exit(1)
    
    # Get latest report
    latest_report = max(reports, key=lambda p: p.stat().st_mtime)
    
    # Output SQL file
    scripts_dir = Path(__file__).parent
    output_file = scripts_dir / 'update_image_urls.sql'
    
    # Generate SQL
    generate_update_sql(latest_report, output_file)

if __name__ == '__main__':
    main()
