import mysql.connector
from config import Config

def migrate_guardian_profile():
    print("Starting Guardian Profile Migration...")
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = conn.cursor()

        # Check if ProfilePicture column exists
        try:
            cursor.execute("SELECT ProfilePicture FROM Guardian_Profile LIMIT 1")
            cursor.fetchall()
            print("ProfilePicture column already exists.")
        except mysql.connector.Error:
            print("Adding ProfilePicture column to Guardian_Profile...")
            cursor.execute("ALTER TABLE Guardian_Profile ADD COLUMN ProfilePicture VARCHAR(255) DEFAULT 'default_guardian.png'")
            print("Added ProfilePicture column.")
        
        conn.commit()
        conn.close()
        print("Migration Complete.")
    
    except mysql.connector.Error as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    migrate_guardian_profile()
