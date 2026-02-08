
import mysql.connector
from database import get_db_connection

def seed_saduni_data():
    conn = get_db_connection()
    if not conn:
        print("Failed to connect to DB")
        return

    try:
        cursor = conn.cursor(dictionary=True)
        
        # 1. Find User 'saduni_1'
        cursor.execute("SELECT UserID FROM User WHERE Username = 'saduni_1'")
        user = cursor.fetchone()
        
        if not user:
            print("User saduni_1 not found. Creating user...")
            from werkzeug.security import generate_password_hash
            cursor.execute("INSERT INTO User (Username, PasswordHash, Role) VALUES (%s, %s, %s)", 
                         ('saduni_1', generate_password_hash('password123'), 'Child'))
            user_id = cursor.lastrowid
            
            # Create Child Profile
            cursor.execute("SELECT UserID FROM User WHERE Role = 'Guardian' LIMIT 1")
            guardian = cursor.fetchone()
            g_id = guardian['UserID'] if guardian else 1
            
            cursor.execute("INSERT INTO Child_Profile (UserID, GuardianID, Name, Age) VALUES (%s, %s, %s, %s)",
                         (user_id, g_id, 'Saduni', 6))
            child_id = cursor.lastrowid
            print(f"Created Saduni with ChildID: {child_id}")
        else:
            user_id = user['UserID']
            cursor.execute("SELECT ChildID FROM Child_Profile WHERE UserID = %s", (user_id,))
            child = cursor.fetchone()
            child_id = child['ChildID']
            print(f"Found Saduni with ChildID: {child_id}")

        # 2. Add Completed Letters
        # Let's mark Letters 1, 2, 3 as completed for testing
        letters_to_complete = [1, 2, 3]
        for l_id in letters_to_complete:
            cursor.execute("""
                INSERT IGNORE INTO Session_Log (ChildID, LetterID, AccuracyScore, StarsEarned)
                VALUES (%s, %s, %s, %s)
            """, (child_id, l_id, 90, 3))
        
        # Update Stars
        cursor.execute("""
            UPDATE Child_Profile 
            SET TotalStars = (SELECT SUM(StarsEarned) FROM Session_Log WHERE ChildID = %s)
            WHERE ChildID = %s
        """, (child_id, child_id))
        
        conn.commit()
        print("Seeding successful!")
        
    except Exception as e:
        print(f"Error seeding data: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    seed_saduni_data()
