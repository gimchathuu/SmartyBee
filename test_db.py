import mysql.connector
from config import Config
import sys

try:
    print(f"Attempting to connect to {Config.DB_HOST} as {Config.DB_USER}...")
    conn = mysql.connector.connect(
        host=Config.DB_HOST,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD
    )
    if conn.is_connected():
        print("SUCCESS: Connected to MySQL Server!")
        cursor = conn.cursor()
        cursor.execute("SHOW DATABASES;")
        dbs = [d[0] for d in cursor.fetchall()]
        print(f"Databases found: {dbs}")
        
        if Config.DB_NAME in dbs:
            print(f"SUCCESS: Database '{Config.DB_NAME}' exists.")
        else:
            print(f"WARNING: Database '{Config.DB_NAME}' NOT found.")
        
        conn.close()
    else:
        print("FAILED: Connection established but is_connected() returned False.")

except mysql.connector.Error as err:
    print(f"ERROR: {err}")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
