import mysql.connector
from config import Config

conn = mysql.connector.connect(
    host=Config.DB_HOST,
    user=Config.DB_USER,
    password=Config.DB_PASSWORD,
    database=Config.DB_NAME
)
cursor = conn.cursor()

print("guardian_profile table structure:")
cursor.execute("DESCRIBE guardian_profile;")
for row in cursor.fetchall():
    print(f"  {row[0]} - {row[1]}")

print("\nchild_profile table structure:")
cursor.execute("DESCRIBE child_profile;")
for row in cursor.fetchall():
    print(f"  {row[0]} - {row[1]}")

conn.close()
