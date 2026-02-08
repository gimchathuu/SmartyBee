"""
Script to clear all data from the letter_template table
WARNING: This will delete ALL letters from the database!
"""
from database import get_db_connection

def clear_letter_template():
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return False
    
    try:
        cursor = conn.cursor()
        
        # First, check how many records exist
        cursor.execute("SELECT COUNT(*) FROM Letter_Template")
        count = cursor.fetchone()[0]
        print(f"📊 Current records in Letter_Template: {count}")
        
        if count == 0:
            print("✅ Table is already empty")
            conn.close()
            return True
        
        # Confirm deletion
        print(f"\n⚠️  WARNING: This will delete {count} letter records!")
        print("This action cannot be undone.")
        
        # Delete all records
        cursor.execute("DELETE FROM Letter_Template")
        conn.commit()
        
        # Verify deletion
        cursor.execute("SELECT COUNT(*) FROM Letter_Template")
        remaining = cursor.fetchone()[0]
        
        if remaining == 0:
            print(f"✅ Successfully deleted all {count} records from Letter_Template")
            print("📝 The table structure remains intact and ready for new data")
            return True
        else:
            print(f"⚠️  Warning: {remaining} records still remain")
            return False
            
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("🗑️  Letter Template Table Cleanup\n")
    print("=" * 50)
    
    result = clear_letter_template()
    
    print("=" * 50)
    if result:
        print("\n✅ Done! The Letter_Template table is now empty.")
        print("You can now insert new letter data.")
    else:
        print("\n❌ Operation failed or incomplete.")
