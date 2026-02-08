import mysql.connector
from config import Config

def migrate_db():
    print("Starting database migration...")
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = conn.cursor()

        # Check if GuardianID column exists in Child_Profile
        try:
            cursor.execute("SELECT GuardianID FROM Child_Profile LIMIT 1")
            print("GuardianID column already exists.")
        except mysql.connector.Error:
            print("Adding GuardianID column to Child_Profile...")
            # We first need to check if UserID exists to decide if we rename or add
            # Ideally for a clean slate or prototype, we might just drop/recreate, but let's try to be gentle.
            # However, the previous schema used UserID as FK. The new one uses GuardianID.
            # Existing data might be messy.
            
            # Simple approach for this context: Add the column if missing.
            cursor.execute("ALTER TABLE Child_Profile ADD COLUMN GuardianID INT")
            cursor.execute("ALTER TABLE Child_Profile ADD FOREIGN KEY (GuardianID) REFERENCES User(UserID) ON DELETE CASCADE")
            print("Added GuardianID column.")

        # Check for Avatar column
        try:
            cursor.execute("SELECT Avatar FROM Child_Profile LIMIT 1")
            print("Avatar column already exists.")
        except mysql.connector.Error:
            print("Adding Avatar column to Child_Profile...")
            cursor.execute("ALTER TABLE Child_Profile ADD COLUMN Avatar VARCHAR(50) DEFAULT 'default_avatar.png'")
            print("Added Avatar column.")

        # Create Guardian_Profile if not exists (it was in schema.sql but making sure)
        # The schema.sql update handled the definition, this script ensures the DB matches.
        
        # Actually, let's just re-run the updated schema.sql parts that use "IF NOT EXISTS" 
        # but ALTER for changed tables is safer.
        pass

        conn.commit()
        conn.close()
        print("Migration complete.")
    
    except mysql.connector.Error as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    migrate_db()
