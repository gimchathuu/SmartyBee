import mysql.connector
from config import Config

conn = mysql.connector.connect(
    host=Config.DB_HOST,
    user=Config.DB_USER,
    password=Config.DB_PASSWORD,
    database=Config.DB_NAME
)
cursor = conn.cursor()

# Check tables
cursor.execute("SHOW TABLES;")
print("Tables:")
for table in cursor.fetchall():
    print(f"  - {table[0]}")

# Check User table structure
print("\nUser table structure:")
cursor.execute("DESCRIBE User;")
for row in cursor.fetchall():
    print(f"  {row[0]} - {row[1]}")

conn.close()
