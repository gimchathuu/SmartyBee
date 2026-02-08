"""
Quick test to verify letters are in database and being fetched correctly
"""
from database import get_db_connection

conn = get_db_connection()
if conn:
    cursor = cursor.fetchall()
    
    print(f"Total letters in database: {len(letters)}")
    print("\nFirst 5 letters:")
    for letter in letters[:5]:
        print(f"  ID {letter['LetterID']}: {letter['SinhalaChar']} ({letter['DifficultyLevel']})")
    
    conn.close()
else:
    print("Failed to connect to database")
