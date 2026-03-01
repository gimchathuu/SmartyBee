"""
Seed Stroke Templates into Database
====================================
Updates Letter_Template.StrokePathJSON for all 32 Sinhala letters
using the reference strokes from stroke_templates.py.
"""

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import get_db_connection
from stroke_templates import get_all_templates


def seed_templates():
    """Populate StrokePathJSON for all letters in Letter_Template."""
    templates = get_all_templates()
    conn = get_db_connection()
    if not conn:
        print("ERROR: Could not connect to database.")
        return False

    try:
        cursor = conn.cursor(dictionary=True)

        # Fetch all existing letters
        cursor.execute("SELECT LetterID, SinhalaChar FROM Letter_Template ORDER BY LetterID")
        rows = cursor.fetchall()

        updated = 0
        skipped = 0
        for row in rows:
            char = row['SinhalaChar']
            lid = row['LetterID']

            if char in templates:
                path_json = json.dumps(templates[char], ensure_ascii=False)
                cursor.execute(
                    "UPDATE Letter_Template SET StrokePathJSON = %s WHERE LetterID = %s",
                    (path_json, lid)
                )
                updated += 1
                print(f"  ✓  LetterID {lid:2d}  {char}  →  {len(templates[char])} points")
            else:
                skipped += 1
                print(f"  ✗  LetterID {lid:2d}  {char}  →  No template found")

        conn.commit()
        print(f"\nDone: {updated} updated, {skipped} skipped out of {len(rows)} total.")
        return True

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    print("Seeding Sinhala stroke templates into Letter_Template...\n")
    seed_templates()
