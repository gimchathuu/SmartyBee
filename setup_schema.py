import mysql.connector
from config import Config

def setup_schema():
    """Create database tables from schema.sql"""
    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = conn.cursor()
        
        # Read schema.sql
        with open('schema.sql', 'r', encoding='utf-8') as f:
            sql_commands = f.read()
        
        # Split by semicolon and execute each statement
        statements = [s.strip() for s in sql_commands.split(';') if s.strip()]
        
        for statement in statements:
            if statement.startswith('USE') or statement.startswith('CREATE DATABASE'):
                continue  # Skip database creation commands
            try:
                cursor.execute(statement)
                print(f"✓ Executed: {statement[:50]}...")
            except mysql.connector.Error as err:
                if err.errno == 1050:  # Table already exists
                    print(f"⚠ Table already exists, skipping...")
                else:
                    raise
        
        conn.commit()
        print("\n✅ Schema setup complete!")
        
        cursor.close()
        conn.close()
        
    except mysql.connector.Error as err:
        print(f"❌ Error: {err}")
    except FileNotFoundError:
        print("❌ schema.sql file not found!")

if __name__ == "__main__":
    setup_schema()
