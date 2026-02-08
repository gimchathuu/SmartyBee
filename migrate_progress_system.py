
import mysql.connector
from config import Config

def migrate():
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = conn.cursor()

        # 1. Add Level column to Letter_Template if not exists
        try:
            cursor.execute("ALTER TABLE Letter_Template ADD COLUMN Level INT DEFAULT 1")
            print("Added Level column to Letter_Template")
        except mysql.connector.Error as err:
            print(f"Level column already exists or error: {err}")

        # 2. Add ImageURL and ExampleWords if they don't exist (saw them in my schema update)
        try:
            cursor.execute("ALTER TABLE Letter_Template ADD COLUMN ImageURL VARCHAR(255)")
            print("Added ImageURL column to Letter_Template")
        except mysql.connector.Error as err:
            print(f"ImageURL column already exists or error: {err}")

        try:
            cursor.execute("ALTER TABLE Letter_Template ADD COLUMN ExampleWords JSON")
            print("Added ExampleWords column to Letter_Template")
        except mysql.connector.Error as err:
            print(f"ExampleWords column already exists or error: {err}")

        # 3. Create Child_Letter_Assignment table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Child_Letter_Assignment (
                AssignmentID INT AUTO_INCREMENT PRIMARY KEY,
                ChildID INT,
                LetterID INT,
                AssignedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ChildID) REFERENCES Child_Profile(ChildID) ON DELETE CASCADE,
                FOREIGN KEY (LetterID) REFERENCES Letter_Template(LetterID) ON DELETE CASCADE,
                UNIQUE KEY (ChildID, LetterID)
            )
        """)
        print("Created Child_Letter_Assignment table")

        # 4. Add StarsEarned to Session_Log if not exists
        try:
            cursor.execute("ALTER TABLE Session_Log ADD COLUMN StarsEarned INT DEFAULT 0")
            print("Added StarsEarned column to Session_Log")
        except mysql.connector.Error as err:
            print(f"StarsEarned column already exists or error: {err}")

        conn.commit()
        cursor.close()
        conn.close()
        print("Migration completed successfully!")

    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate()
