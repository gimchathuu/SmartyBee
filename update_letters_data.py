"""
Update existing letters with example words and placeholder images
"""

from database import get_db_connection
import json

def update_letters_data():
    # Sinhala alphabet with example words
    letters_data = [
        {"letter": "අ", "words": ["අඹ", "අම්මා", "අප්පා"], "image": "/static/images/letters/a.png"},
        {"letter": "ආ", "words": ["ආච්චි", "ආපු"], "image": "/static/images/letters/aa.png"},
        {"letter": "ඇ", "words": ["ඇති", "ඇඳ"], "image":" /static/images/letters/ae.png"},
        {"letter": "ඈ", "words": ["ඈත", "ඈඳ"], "image": "/static/images/letters/aae.png"},
        {"letter": "ඉ", "words": ["ඉස්සා", "ඉඳුරා"], "image": "/static/images/letters/i.png"},
    ]
    
    conn = get_db_connection()
    if not conn:
        print("❌ Database connection failed")
        return
    
    try:
        cursor = conn.cursor()
        
        print("📝 Updating letters with example words and images...")
        
        for data in letters_data:
            # Convert words list to JSON string
            example_words_json = json.dumps(data["words"], ensure_ascii=False)
            
            cursor.execute("""
                UPDATE letter_template 
                SET ExampleWords = %s, ImageURL = %s
                WHERE SinhalaChar = %s
            """, (example_words_json, data["image"], data["letter"]))
            
            print(f"  ✅ Updated {data['letter']}")
        
        conn.commit()
        
        print("\n✅ All letters updated successfully!")
        print("\n📋 Verifying data:")
        cursor.execute("SELECT LetterID, SinhalaChar, ImageURL, ExampleWords FROM letter_template LIMIT 5")
        letters = cursor.fetchall()
        for letter in letters:
            print(f"  - Letter: {letter[1]}, Image: {letter[2]}, Words: {letter[3]}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error updating letters: {e}")
        if conn:
            conn.close()

if __name__ == "__main__":
    update_letters_data()
