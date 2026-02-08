"""Check how many letters are in the database"""
from database import get_db_connection

conn = get_db_connection()
if conn:
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) as count FROM Letter_Template")
    result = cursor.fetchone()
    print(f"Total letters in database: {result['count']}")
    
    cursor.execute("SELECT LetterID, SinhalaChar, DifficultyLevel FROM Letter_Template ORDER BY LetterID")
    letters = cursor.fetchall()
    
    print("\nAll letters:")
    for letter in letters:
        print(f"  ID {letter['LetterID']}: {letter['SinhalaChar']} ({letter['DifficultyLevel']})")
    
    conn.close()
else:
    print("Failed to connect to database")
