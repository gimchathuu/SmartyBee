"""
Script to insert Sinhala letters into the database
"""
from database import get_db_connection
import json

# Letter data with all fields
letters = [
    # VOWELS
    (3, 'අ', '[]', 'Easy', '/static/images/letters/a.png', '["අම්මා", "අලියා", "අත"]'),
    (4, 'ආ', '[]', 'Easy', '/static/images/letters/aa.png', '["ආත්තම්මා", "ආතා", "ආලෝකය"]'),
    (5, 'ඇ', '[]', 'Medium', '/static/images/letters/ae.png', '["ඇස", "ඇඟිල්ල", "ඇතුළ"]'),
    (6, 'ඈ', '[]', 'Medium', '/static/images/letters/aae.png', '["ඈයා", "ඈනුම", "ඈත"]'),
    (7, 'ඉ', '[]', 'Hard', '/static/images/letters/i.png', '["ඉර", "ඉබ්බා", "ඉණිමඟ"]'),
    (8, 'ඊ', '[]', 'Easy', '/static/images/letters/ii.png', '["ඊතලය", "ඊයම්", "ඊයා"]'),
    (9, 'උ', '[]', 'Easy', '/static/images/letters/u.png', '["උයන", "උදැල්ල", "උගුල"]'),
    (10, 'ඌ', '[]', 'Easy', '/static/images/letters/uu.png', '["ඌරා", "ඌරුමීයා", "ඌෂ්ණකය"]'),
    (11, 'එ', '[]', 'Easy', '/static/images/letters/e.png', '["එළුවා", "එළිය", "එළවළු"]'),
    (12, 'ඒ', '[]', 'Easy', '/static/images/letters/ee.png', '["ඒකා", "ඒක", "ඒණියා"]'),
    (13, 'ඔ', '[]', 'Easy', '/static/images/letters/o.png', '["ඔරුව", "ඔරලෝසුව", "ඔළුව"]'),
    (14, 'ඕ', '[]', 'Easy', '/static/images/letters/oo.png', '["ඕලු", "ඕවිට", "ඕනෑ"]'),
    
    # CONSONANTS
    (15, 'ක', '[]', 'Medium', '/static/images/letters/ka.png', '["කලය", "කතුර", "කෑම"]'),
    (16, 'ග', '[]', 'Medium', '/static/images/letters/ga.png', '["ගස", "ගෙදර", "ගල"]'),
    (17, 'ට', '[]', 'Medium', '/static/images/letters/ta.png', '["ටකරන්", "ටිකට්", "ටක්"]'),
    (18, 'ඩ', '[]', 'Medium', '/static/images/letters/da.png', '["ඩෝං", "ඩබල්", "ඩොක්ටර්"]'),
    (19, 'ණ', '[]', 'Medium', '/static/images/letters/na_mur.png', '["වීණාව", "මුහුණ", "ගුණය"]'),
    (20, 'ත', '[]', 'Medium', '/static/images/letters/tha.png', '["තරුව", "තල", "තනකොළ"]'),
    (21, 'ද', '[]', 'Medium', '/static/images/letters/dha.png', '["දත", "දොර", "දඩයම"]'),
    (22, 'න', '[]', 'Medium', '/static/images/letters/na.png', '["නළල", "නරියා", "නළුවා"]'),
    (23, 'ප', '[]', 'Medium', '/static/images/letters/pa.png', '["පෑන", "පළතුර", "පනාව"]'),
    (24, 'බ', '[]', 'Medium', '/static/images/letters/ba.png', '["බෝලය", "බල්ලා", "බබාලා"]'),
    (25, 'ම', '[]', 'Medium', '/static/images/letters/ma.png', '["මල", "මහත", "මහත්තයා"]'),
    (26, 'ය', '[]', 'Medium', '/static/images/letters/ya.png', '["යතුර", "යහන", "යව"]'),
    (27, 'ර', '[]', 'Medium', '/static/images/letters/ra.png', '["රස", "රජා", "රබර්"]'),
    (28, 'ච', '[]', 'Medium', '/static/images/letters/cha.png', '["චිත්රය", "චූටි", "චතුරස්රය"]'),
    (29, 'ජ', '[]', 'Medium', '/static/images/letters/ja.png', '["ජලය", "ජනේලය", "ජම්බු"]'),
    (30, 'ල', '[]', 'Medium', '/static/images/letters/la.png', '["ලපය", "ළමයා", "ලියුම"]'),
    (31, 'ව', '[]', 'Medium', '/static/images/letters/va.png', '["වතුර", "වඳුරා", "වත්ත"]'),
    (32, 'ස', '[]', 'Medium', '/static/images/letters/sa.png', '["සමනලයා", "සතා", "සබන්"]'),
    (33, 'හ', '[]', 'Medium', '/static/images/letters/ha.png', '["හඳ", "හාවා", "හැන්ද"]'),
    (34, 'ළ', '[]', 'Hard', '/static/images/letters/lla.png', '["ළිඳ", "ළමයා", "ළැම"]'),
]

def insert_letters():
    conn = get_db_connection()
    if not conn:
        print("❌ Failed to connect to database")
        return
    
    try:
        cursor = conn.cursor()
        
        inserted = 0
        skipped = 0
        errors = 0
        
        for letter in letters:
            try:
                cursor.execute("""
                    INSERT INTO Letter_Template 
                    (LetterID, SinhalaChar, StrokePathJSON, DifficultyLevel, ImageURL, ExampleWords)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, letter)
                inserted += 1
                print(f"✓ Inserted: {letter[1]} (ID: {letter[0]}) - {letter[3]}")
            except Exception as e:
                if "Duplicate entry" in str(e):
                    skipped += 1
                    print(f"⊘ Skipped (already exists): {letter[1]} (ID: {letter[0]})")
                else:
                    errors += 1
                    print(f"✗ Error inserting {letter[1]}: {e}")
        
        conn.commit()
        
        print("\n" + "=" * 60)
        print(f"📊 Summary:")
        print(f"  ✅ Inserted: {inserted}")
        print(f"  ⊘ Skipped: {skipped}")
        print(f"  ✗ Errors: {errors}")
        print(f"  📝 Total: {len(letters)} letters")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("📝 Inserting Sinhala Letters into Database\n")
    print("=" * 60)
    insert_letters()
    print("\n✅ Done!")
