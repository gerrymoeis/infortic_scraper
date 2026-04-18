"""
Quick script to check actual database schema
"""
import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv('config/.env')

DATABASE_URL = os.getenv('DATABASE_URL')

print("Connecting to database...")
print(f"URL: {DATABASE_URL[:50]}...")

try:
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Get all columns from opportunities table
    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default 
        FROM information_schema.columns 
        WHERE table_name = 'opportunities' 
        ORDER BY ordinal_position;
    """)
    
    columns = cursor.fetchall()
    
    print(f"\n{'='*80}")
    print(f"OPPORTUNITIES TABLE SCHEMA ({len(columns)} columns)")
    print(f"{'='*80}\n")
    
    for col in columns:
        col_name, data_type, nullable, default = col
        nullable_str = "NULL" if nullable == "YES" else "NOT NULL"
        default_str = f"DEFAULT {default}" if default else ""
        print(f"  {col_name:25} {data_type:20} {nullable_str:10} {default_str}")
    
    # Get all indexes
    cursor.execute("""
        SELECT indexname, indexdef 
        FROM pg_indexes 
        WHERE tablename = 'opportunities' 
        ORDER BY indexname;
    """)
    
    indexes = cursor.fetchall()
    
    print(f"\n{'='*80}")
    print(f"INDEXES ({len(indexes)} indexes)")
    print(f"{'='*80}\n")
    
    for idx in indexes:
        print(f"  {idx[0]}")
    
    # Get all constraints
    cursor.execute("""
        SELECT conname, pg_get_constraintdef(oid) as definition 
        FROM pg_constraint 
        WHERE conrelid = 'opportunities'::regclass 
        ORDER BY conname;
    """)
    
    constraints = cursor.fetchall()
    
    print(f"\n{'='*80}")
    print(f"CONSTRAINTS ({len(constraints)} constraints)")
    print(f"{'='*80}\n")
    
    for con in constraints:
        print(f"  {con[0]}: {con[1][:80]}")
    
    # Get all tables in database
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name;
    """)
    
    tables = cursor.fetchall()
    
    print(f"\n{'='*80}")
    print(f"ALL TABLES IN DATABASE ({len(tables)} tables)")
    print(f"{'='*80}\n")
    
    for table in tables:
        print(f"  - {table[0]}")
    
    cursor.close()
    conn.close()
    
    print(f"\n{'='*80}")
    print("SUCCESS: Schema check complete!")
    print(f"{'='*80}\n")
    
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
