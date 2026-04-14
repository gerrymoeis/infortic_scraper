"""Check all table schemas"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.database.client import DatabaseClient
from src.extraction.utils.config import config

db = DatabaseClient(config.DATABASE_URL)
db.connect()

tables = ['opportunities', 'opportunity_types', 'audiences', 'organizers', 'opportunity_audiences', 'i18n_labels']

for table in tables:
    print("\n" + "="*60)
    print(f"{table.upper()} TABLE")
    print("="*60)
    result = db.execute_query(f"""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = '{table}' 
        ORDER BY ordinal_position
    """)
    
    for row in result:
        nullable = "NULL" if row['is_nullable'] == 'YES' else "NOT NULL"
        print(f"{row['column_name']:30} {row['data_type']:20} {nullable}")

db.close()
