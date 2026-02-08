import mysql.connector
from config import Config
from werkzeug.security import generate_password_hash

def migrate_admin():
    print("Starting Admin Schema Migration...")
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = conn.cursor()

        # 1. Create Admin_User Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Admin_User (
            AdminID INT AUTO_INCREMENT PRIMARY KEY,
            Username VARCHAR(50) NOT NULL UNIQUE,
            PasswordHash VARCHAR(255) NOT NULL,
            Role ENUM('SuperAdmin', 'Editor') DEFAULT 'SuperAdmin',
            CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        print("Created Admin_User table.")

        # 2. Create System_Log Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS System_Log (
            LogID INT AUTO_INCREMENT PRIMARY KEY,
            Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            Level VARCHAR(20),
            Message TEXT
        )
        """)
        print("Created System_Log table.")

        # 3. Create Feedback Table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS Feedback (
            FeedbackID INT AUTO_INCREMENT PRIMARY KEY,
            GuardianID INT,
            Message TEXT,
            SubmittedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (GuardianID) REFERENCES User(UserID) ON DELETE SET NULL
        )
        """)
        print("Created Feedback table.")

        # 4. Create Default Admin (if not exists)
        cursor.execute("SELECT * FROM Admin_User WHERE Username = 'admin'")
        if not cursor.fetchone():
            pw_hash = generate_password_hash("admin123")
            cursor.execute("INSERT INTO Admin_User (Username, PasswordHash, Role) VALUES (%s, %s, 'SuperAdmin')", ('admin', pw_hash))
            print("Created default admin user (user: admin, pass: admin123)")
        
        conn.commit()
        conn.close()
        print("Admin Migration Complete.")
    
    except mysql.connector.Error as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    migrate_admin()
