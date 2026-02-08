import mysql.connector
from config import Config

def migrate_db():
    print("Starting database migration (Step 2)...")
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = conn.cursor()

        # Check if UserID column exists in Child_Profile
        try:
            cursor.execute("SELECT UserID FROM Child_Profile LIMIT 1")
            cursor.fetchall() # Consume result
            print("UserID column already exists.")
        except mysql.connector.Error:
            print("Adding UserID column to Child_Profile...")
            cursor.execute("ALTER TABLE Child_Profile ADD COLUMN UserID INT")
            cursor.execute("ALTER TABLE Child_Profile ADD FOREIGN KEY (UserID) REFERENCES User(UserID) ON DELETE CASCADE")
            print("Added UserID column.")

        conn.commit()
        conn.close()
        print("Migration Step 2 complete.")
    
    except mysql.connector.Error as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    migrate_db()
