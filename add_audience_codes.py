"""
Add missing audience codes to production database
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent / 'src'))
from extraction.utils.config import Config

def add_audience_codes():
    """Add sd, smk, d2 audience codes to database"""
    conn = psycopg2.connect(Config.DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    
    try:
        print("Adding missing audience codes...")
        
        # Step 1: Create i18n labels
        print("\n1. Creating i18n labels...")
        
        cur.execute("""
            INSERT INTO i18n_labels (language, value) 
            VALUES ('id', 'SD') 
            ON CONFLICT (language, value) DO NOTHING
            RETURNING id
        """)
        sd_label = cur.fetchone()
        if not sd_label:
            cur.execute("SELECT id FROM i18n_labels WHERE language = 'id' AND value = 'SD'")
            sd_label = cur.fetchone()
        print(f"   SD label ID: {sd_label['id']}")
        
        cur.execute("""
            INSERT INTO i18n_labels (language, value) 
            VALUES ('id', 'SMK') 
            ON CONFLICT (language, value) DO NOTHING
            RETURNING id
        """)
        smk_label = cur.fetchone()
        if not smk_label:
            cur.execute("SELECT id FROM i18n_labels WHERE language = 'id' AND value = 'SMK'")
            smk_label = cur.fetchone()
        print(f"   SMK label ID: {smk_label['id']}")
        
        cur.execute("""
            INSERT INTO i18n_labels (language, value) 
            VALUES ('id', 'D2') 
            ON CONFLICT (language, value) DO NOTHING
            RETURNING id
        """)
        d2_label = cur.fetchone()
        if not d2_label:
            cur.execute("SELECT id FROM i18n_labels WHERE language = 'id' AND value = 'D2'")
            d2_label = cur.fetchone()
        print(f"   D2 label ID: {d2_label['id']}")
        
        # Step 2: Create audience codes
        print("\n2. Creating audience codes...")
        
        cur.execute("""
            INSERT INTO audiences (code, label_id) 
            VALUES ('sd', %s) 
            ON CONFLICT (code) DO NOTHING
        """, (sd_label['id'],))
        print("   Added: sd")
        
        cur.execute("""
            INSERT INTO audiences (code, label_id) 
            VALUES ('smk', %s) 
            ON CONFLICT (code) DO NOTHING
        """, (smk_label['id'],))
        print("   Added: smk")
        
        cur.execute("""
            INSERT INTO audiences (code, label_id) 
            VALUES ('d2', %s) 
            ON CONFLICT (code) DO NOTHING
        """, (d2_label['id'],))
        print("   Added: d2")
        
        conn.commit()
        
        # Step 3: Verify
        print("\n3. Verifying audience codes...")
        cur.execute("""
            SELECT a.code, il.value as label 
            FROM audiences a 
            JOIN i18n_labels il ON a.label_id = il.id 
            WHERE il.language = 'id' 
            ORDER BY a.code
        """)
        codes = cur.fetchall()
        print(f"\n   Total audience codes: {len(codes)}")
        for row in codes:
            print(f"   - {row['code']}: {row['label']}")
        
        print("\n✅ Migration complete!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error: {e}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == '__main__':
    add_audience_codes()
