"""Check actual database schema"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.database.client import DatabaseClient
from src.extraction.utils.config import config

db = DatabaseClient(config.DATABASE_URL)
db.connect()

# Get opportunities table schema
print("\n" + "="*60)
print("OPPORTUNITIES TABLE SCHEMA")
print("="*60)
result = db.execute_query("""
    SELECT column_name, data_type, is_nullable
    FROM information_schema.columns 
    WHERE table_name = 'opportunities' 
    ORDER BY ordinal_position
""")

for row in result:
    nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
    print(f"{row['column_name']:30} {row['data_type']:20} {nullable}")

# Check all tables
print("\n" + "="*60)
print("ALL TABLES IN DATABASE")
print("="*60)
tables = db.execute_query("""
    SELECT table_name 
    FROM information_schema.tables 
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")

for row in tables:
    print(f"  - {row['table_name']}")

db.close()
