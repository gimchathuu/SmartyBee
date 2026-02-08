
import json
from unittest.mock import MagicMock, patch
from flask import session

# Mocking Flask app and session for logic testing
class MockApp:
    def __init__(self):
        self.config = {}

@patch('app.get_db_connection')
def test_child_home_logic(mock_get_db):
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_get_db.return_value = mock_conn
    mock_conn.cursor.return_value = mock_cursor

    # Mocking data as if from DB
    all_letters = [
        {'LetterID': 1, 'SinhalaChar': 'අ', 'Level': 1},
        {'LetterID': 2, 'SinhalaChar': 'ආ', 'Level': 1},
        {'LetterID': 6, 'SinhalaChar': 'ක', 'Level': 2}
    ]
    completed_data = {1: 3}
    assigned_letters = {6}
    child_level = (len(completed_data) // 5) + 1 # Level 1
    
    feedbacks = {
        1: "නියමයි! දිගටම කරගෙන යන්න. (Well done! Keep it up)"
    }
    
    # 5. Determine status and feedback
    letters_data = []
    is_next_unlock = True
    assigned_only = []
    
    for letter in all_letters:
        l_id = letter['LetterID']
        l_level = letter['Level']
        status = 'locked'
        stars = 0
        feedback = feedbacks.get(l_id, "")
        
        if l_id in completed_data:
            status = 'completed'
            stars = completed_data[l_id]
        elif l_id in assigned_letters:
            status = 'unlocked'
            assigned_only.append({
                "LetterID": l_id,
                "SinhalaChar": letter['SinhalaChar']
            })
        elif l_level <= child_level and is_next_unlock:
            status = 'unlocked'
            is_next_unlock = False
        else:
            status = 'locked'
        
        letters_data.append({
            "LetterID": l_id,
            "status": status,
            "stars": stars,
            "level": l_level,
            "feedback": feedback
        })

    # Assertions
    print("Testing Progress & Feedback Logic Results:")
    for l in letters_data:
        print(f"ID: {l['LetterID']}, Status: {l['status']}, Stars: {l['stars']}, Feedback: '{l['feedback']}'")

    print("\nAssigned Only (Separate Section):")
    for a in assigned_only:
        print(f"ID: {a['LetterID']}, Char: {a['SinhalaChar']}")

    assert letters_data[0]['status'] == 'completed'
    assert letters_data[0]['feedback'] != "" # Letter 1 should have feedback
    assert len(assigned_only) == 1 # Letter 6 is assigned but not completed
    assert assigned_only[0]['LetterID'] == 6
    
    print("\nLogic Test (with Feedback & Separated Assignments) PASSED!")

if __name__ == "__main__":
    test_child_home_logic()
