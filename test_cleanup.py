"""Test cleanup script"""
import os
import psycopg2
from dotenv import load_dotenv
from datetime import date

load_dotenv('config/.env')
DATABASE_URL = os.getenv('DATABASE_URL')

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Test stats query
print("Testing stats query...")
cursor.execute("""
    SELECT 
        COUNT(CASE WHEN status = 'active' THEN 1 END) as active_count,
        COUNT(CASE WHEN status = 'expired' THEN 1 END) as expired_count,
        COUNT(CASE WHEN status = 'expired' AND auto_expired = true THEN 1 END) as auto_expired_count,
        COUNT(CASE WHEN status = 'active' AND deadline_date < CURRENT_DATE THEN 1 END) as should_expire_count
    FROM opportunities
""")

result = cursor.fetchone()
print(f"Active: {result[0]}")
print(f"Expired: {result[1]}")
print(f"Auto-expired: {result[2]}")
print(f"Should expire: {result[3]}")

# Test cleanup query (dry run)
print("\nTesting cleanup query (SELECT only)...")
cursor.execute("""
    SELECT id, title, deadline_date, post_id, status
    FROM opportunities
    WHERE 
        status = 'active'
        AND deadline_date IS NOT NULL
        AND deadline_date < %s
    LIMIT 5
""", (date.today(),))

results = cursor.fetchall()
print(f"Found {len(results)} opportunities that should be expired:")
for r in results:
    print(f"  - {r[1][:50]} (deadline: {r[2]}, status: {r[4]})")

cursor.close()
conn.close()
