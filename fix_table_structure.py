"""
Script to check table structure and add missing columns
"""
from database import get_db_connection

def check_and_add_columns():
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return False
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Check current table structure
        print("📊 Current table structure:")
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'smartybee_db' 
            AND TABLE_NAME = 'Letter_Template'
            ORDER BY ORDINAL_POSITION
        """)
        
        columns = cursor.fetchall()
        existing_columns = []
        
        for col in columns:
            print(f"  - {col['COLUMN_NAME']} ({col['DATA_TYPE']})")
            existing_columns.append(col['COLUMN_NAME'])
        
        print()
        
        # Add ImageURL if missing
        if 'ImageURL' not in existing_columns:
            print("➕ Adding ImageURL column...")
            cursor.execute("""
                ALTER TABLE Letter_Template 
                ADD COLUMN ImageURL VARCHAR(255) NULL
            """)
            print("✅ Added ImageURL column")
        else:
            print("✅ ImageURL column already exists")
        
        # Add ExampleWords if missing
        if 'ExampleWords' not in existing_columns:
            print("➕ Adding ExampleWords column...")
            cursor.execute("""
                ALTER TABLE Letter_Template 
                ADD COLUMN ExampleWords JSON NULL
            """)
            print("✅ Added ExampleWords column")
        else:
            print("✅ ExampleWords column already exists")
        
        conn.commit()
        
        # Show final structure
        print("\n📊 Final table structure:")
        cursor.execute("""
            SELECT COLUMN_NAME, DATA_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'smartybee_db' 
            AND TABLE_NAME = 'Letter_Template'
            ORDER BY ORDINAL_POSITION
        """)
        
        final_columns = cursor.fetchall()
        for col in final_columns:
            print(f"  - {col['COLUMN_NAME']} ({col['DATA_TYPE']})")
        
        return True
            
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("🔧 Letter Template Table Structure Check\n")
    print("=" * 60)
    
    result = check_and_add_columns()
    
    print("=" * 60)
    if result:
        print("\n✅ Done! All required columns are now in the table.")
    else:
        print("\n❌ Operation failed.")
