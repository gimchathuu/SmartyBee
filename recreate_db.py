import mysql.connector
from config import Config
import sys

def recreate_database():
    print("Recreating database...")
    try:
        # Connect to MySQL server (no database selected)
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD
        )
        cursor = conn.cursor()

        # Create database
        db_name = Config.DB_NAME
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        print(f"✓ Database '{db_name}' created or already exists.")
        
        # Select the database
        cursor.execute(f"USE {db_name}")

        # Read schema.sql
        try:
            with open('schema.sql', 'r', encoding='utf-8') as f:
                sql_commands = f.read()
            
            # Split by semicolon and execute each statement
            statements = [s.strip() for s in sql_commands.split(';') if s.strip()]
            
            for statement in statements:
                if statement.startswith('USE') or statement.startswith('CREATE DATABASE'):
                    continue  # We already did this
                try:
                    cursor.execute(statement)
                    # print(f"✓ Executed: {statement[:50]}...")
                except mysql.connector.Error as err:
                    if err.errno == 1050:  # Table already exists
                        print(f"⚠ Table already exists: {statement[:30]}...")
                    else:
                        print(f"❌ Error executing statement: {statement[:50]}...\n{err}")
                        raise

            print("✅ Schema setup complete!")

        except FileNotFoundError:
            print("❌ schema.sql file not found!")
            sys.exit(1)

        conn.commit()
        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"❌ Connection Error: {err}")
        sys.exit(1)

if __name__ == "__main__":
    recreate_database()
