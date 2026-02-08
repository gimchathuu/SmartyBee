import mysql.connector
import json
from config import Config

def seed_alphabet():
    print("Seeding Sinhala Alphabet...")
    
    # Full Sinhala Alphabet Data
    # Grouped by Difficulty for the game logic
    letters = [
        # --- Easy (Basic Shapes) ---
        {"char": "අ", "diff": "Easy"},
        {"char": "ආ", "diff": "Easy"},
        {"char": "ඇ", "diff": "Easy"},
        {"char": "ඈ", "diff": "Easy"},
        {"char": "ඉ", "diff": "Easy"},
        {"char": "ඊ", "diff": "Easy"},
        {"char": "උ", "diff": "Easy"},
        {"char": "ඌ", "diff": "Easy"},
        {"char": "එ", "diff": "Easy"},
        {"char": "ඒ", "diff": "Easy"},
        {"char": "ඔ", "diff": "Easy"},
        {"char": "ඕ", "diff": "Easy"},
        
        # --- Medium (Simple Curves) ---
        {"char": "ක", "diff": "Medium"},
        {"char": "ග", "diff": "Medium"},
        {"char": "ට", "diff": "Medium"},
        {"char": "ඩ", "diff": "Medium"},
        {"char": "ණ", "diff": "Medium"},
        {"char": "ත", "diff": "Medium"},
        {"char": "ද", "diff": "Medium"},
        {"char": "න", "diff": "Medium"},
        {"char": "ප", "diff": "Medium"},
        {"char": "බ", "diff": "Medium"},
        {"char": "ම", "diff": "Medium"},
        {"char": "ය", "diff": "Medium"},
        {"char": "ර", "diff": "Medium"},
        {"char": "ල", "diff": "Medium"},
        {"char": "ව", "diff": "Medium"},
        {"char": "ස", "diff": "Medium"},
        {"char": "හ", "diff": "Medium"},
        {"char": "ළ", "diff": "Medium"},
        
        # --- Hard (Complex Strokes) ---
        {"char": "ඛ", "diff": "Hard"},
        {"char": "ඝ", "diff": "Hard"},
        {"char": "ඞ", "diff": "Hard"},
        {"char": "ච", "diff": "Hard"},
        {"char": "ඡ", "diff": "Hard"},
        {"char": "ජ", "diff": "Hard"},
        {"char": "ඣ", "diff": "Hard"},
        {"char": "ඤ", "diff": "Hard"},
        {"char": "ඨ", "diff": "Hard"},
        {"char": "ඪ", "diff": "Hard"},
        {"char": "ථ", "diff": "Hard"},
        {"char": "ධ", "diff": "Hard"},
        {"char": "ඵ", "diff": "Hard"},
        {"char": "භ", "diff": "Hard"},
        {"char": "ශ", "diff": "Hard"},
        {"char": "ෂ", "diff": "Hard"},
        {"char": "ෆ", "diff": "Hard"}
    ]

    # Placeholder Path (Vertical Line) to prevent null errors in detailed view
    # In a real scenario, you'd update this via the Admin Panel with actual drawing data
    dummy_path = json.dumps([{"x": 0.5, "y": 0.2}, {"x": 0.5, "y": 0.8}])

    try:
        conn = mysql.connector.connect(
            host=Config.DB_HOST,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME
        )
        cursor = conn.cursor()

        # Optional: Clear existing letters to avoid duplicates during dev
        # cursor.execute("TRUNCATE TABLE Letter_Template") 

        for l in letters:
            # Check if exists
            cursor.execute("SELECT LetterID FROM Letter_Template WHERE SinhalaChar = %s", (l['char'],))
            if not cursor.fetchone():
                cursor.execute(
                    "INSERT INTO Letter_Template (SinhalaChar, DifficultyLevel, StrokePathJSON) VALUES (%s, %s, %s)",
                    (l['char'], l['diff'], dummy_path)
                )
                print(f"Added: {l['char']}")
            else:
                print(f"Skipped (Exists): {l['char']}")

        conn.commit()
        conn.close()
        print("Alphabet Seeding Complete!")

    except mysql.connector.Error as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    seed_alphabet()
