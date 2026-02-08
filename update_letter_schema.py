"""
Script to update the letter_template table schema for Learn pages
Adds ImageURL and ExampleWords columns
"""

from database import get_db_connection

def update_schema():
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return False
    
    try:
        cursor = conn.cursor()
        
        print("📝 Adding ImageURL column...")
        cursor.execute("""
            ALTER TABLE letter_template 
            ADD COLUMN IF NOT EXISTS ImageURL VARCHAR(255)
        """)
        
        print("📝 Adding ExampleWords column...")
        cursor.execute("""
            ALTER TABLE letter_template 
            ADD COLUMN IF NOT EXISTS ExampleWords TEXT
        """)
        
        conn.commit()
        
        print("\n✅ Schema updated successfully!")
        print("\n📋 Updated table structure:")
        cursor.execute("DESCRIBE letter_template")
        columns = cursor.fetchall()
        for col in columns:
            print(f"  - {col}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error updating schema: {e}")
        if conn:
            conn.close()
        return False

if __name__ == "__main__":
    update_schema()
