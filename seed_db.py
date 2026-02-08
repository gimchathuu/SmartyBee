import mysql.connector
from config import Config
from werkzeug.security import generate_password_hash

def seed_database():
    """
    Seed the database with initial test data:
    - Admin & Guardian users
    - Child profiles
    - Sinhala letters (අ, ආ, ඇ, ඈ, ඉ)
    """
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = conn.cursor()
        
        # Clear existing data (for re-seeding)
        print("Clearing existing data...")
        cursor.execute("DELETE FROM session_log;")
        cursor.execute("DELETE FROM child_profile;")
        cursor.execute("DELETE FROM guardian_profile;")
        cursor.execute("DELETE FROM user;")
        cursor.execute("DELETE FROM letter_template;")
        
        # Insert Users
        print("Inserting users...")
        users = [
            ('admin', generate_password_hash('admin123'), 'Admin'),
            ('guardian1', generate_password_hash('123'), 'Guardian'),
            ('child1', generate_password_hash('123'), 'Child'),
        ]
        cursor.executemany(
            "INSERT INTO user (Username, PasswordHash, Role) VALUES (%s, %s, %s)",
            users
        )
        
        # Get User IDs
        cursor.execute("SELECT UserID, Username FROM user")
        user_map = {row[1]: row[0] for row in cursor.fetchall()}
        
        # Insert Guardian Profile
        print("Inserting guardian profile...")
        cursor.execute(
            "INSERT INTO guardian_profile (UserID, User_Name) VALUES (%s, %s)",
            (user_map['guardian1'], 'guardian1')
        )
        
        # Insert Child Profile
        print("Inserting child profile...")
        cursor.execute(
            "INSERT INTO child_profile (UserID, Name, Age, TotalStars) VALUES (%s, %s, %s, %s)",
            (user_map['child1'], 'දිනුකා', 6, 0)
        )
        
        # Insert Sinhala Letters (with mock stroke paths)
        print("Inserting Sinhala letters...")
        letters = [
            ('අ', 'Easy', '[{"x": 0.3, "y": 0.2}, {"x": 0.7, "y": 0.2}, {"x": 0.5, "y": 0.8}]'),
            ('ආ', 'Easy', '[{"x": 0.2, "y": 0.3}, {"x": 0.8, "y": 0.3}, {"x": 0.5, "y": 0.7}]'),
            ('ඇ', 'Medium', '[{"x": 0.4, "y": 0.2}, {"x": 0.6, "y": 0.5}, {"x": 0.4, "y": 0.8}]'),
            ('ඈ', 'Medium', '[{"x": 0.3, "y": 0.3}, {"x": 0.7, "y": 0.4}, {"x": 0.5, "y": 0.7}]'),
            ('ඉ', 'Hard', '[{"x": 0.5, "y": 0.2}, {"x": 0.6, "y": 0.5}, {"x": 0.4, "y": 0.8}]'),
        ]
        cursor.executemany(
            "INSERT INTO letter_template (SinhalaChar, DifficultyLevel, StrokePathJSON) VALUES (%s, %s, %s)",
            letters
        )
        
        conn.commit()
        print("\n✅ Database seeded successfully!")
        print("\nTest Credentials:")
        print("  Guardian: guardian1 / 123")
        print("  Child: child1 / 123")
        
        cursor.close()
        conn.close()
        
    except mysql.connector.Error as err:
        print(f"❌ Error: {err}")

if __name__ == "__main__":
    seed_database()
