"""
Script to check and add ExampleWords column to letter_template table
"""
from database import get_db_connection

def add_example_words_column():
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return False
    
    try:
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'smartybee_db' 
            AND TABLE_NAME = 'Letter_Template' 
            AND COLUMN_NAME = 'ExampleWords'
        """)
        
        result = cursor.fetchone()
        
        if result:
            print("✅ ExampleWords column already exists in Letter_Template table")
            return True
        
        # Add the column
        print("📝 Adding ExampleWords column to Letter_Template table...")
        cursor.execute("""
            ALTER TABLE Letter_Template 
            ADD COLUMN ExampleWords JSON NULL
        """)
        conn.commit()
        
        print("✅ Successfully added ExampleWords column (JSON type)")
        return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("🔧 Adding ExampleWords Column\n")
    print("=" * 50)
    
    result = add_example_words_column()
    
    print("=" * 50)
    if result:
        print("\n✅ Done! The ExampleWords column is ready to use.")
    else:
        print("\n❌ Operation failed.")
