from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
from config import Config
from database import get_db_connection
from vision_engine import evaluate_stroke, calculate_stars as vision_calculate_stars
import json
import traceback

# ML Pipeline (optional — loads trained model if available)
try:
    from ml_pipeline.predict import get_ml_predictor, hybrid_score, ml_only_evaluate
    from ml_pipeline.collect_data import save_training_sample
    from ml_pipeline.recognize_letter import get_recognizer
    from ml_pipeline.ml_config import (
        FOLDER_TO_LETTER, CLASS_TO_FOLDER, CLASS_TO_LETTER,
        LETTER_TO_CLASS, FOLDER_TO_CLASS,
    )
    from ml_pipeline.db_integration import (
        log_prediction, log_score, log_error_feedback,
        log_stroke_data, log_ml_error,
    )
    ML_AVAILABLE = True
    print("[ML Pipeline] Successfully loaded all components.")
except ImportError as e:
    print(f"[ML Pipeline] Not loaded: {e}")
    ML_AVAILABLE = False

# ML gatekeeper reliability flag — validated at first request
ML_GATEKEEPER_RELIABLE = None   # None = not yet tested, True/False after validation
ML_VALIDATION_MIN_ACCURACY = 0.40  # model must correctly identify at least 40% of templates

def validate_ml_model():
    """Test the ML model against DB templates to check if it's reliable.
    
    Feeds each ML-supported letter's template back into the model and checks
    whether the model correctly identifies it. If accuracy is too low,
    the gatekeeper is disabled to prevent blocking correct attempts.
    
    Returns:
        bool — True if model is reliable enough for gating, False otherwise
    """
    global ML_GATEKEEPER_RELIABLE
    if not ML_AVAILABLE:
        ML_GATEKEEPER_RELIABLE = False
        return False
    
    try:
        predictor = get_ml_predictor()
        if predictor.model is None:
            print("[ML Validation] No model loaded — disabling gatekeeper.")
            ML_GATEKEEPER_RELIABLE = False
            return False
        
        conn = get_db_connection()
        if not conn:
            print("[ML Validation] No DB connection — skipping validation.")
            ML_GATEKEEPER_RELIABLE = False
            return False
        
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT LetterID, SinhalaChar, StrokePathJSON FROM Letter_Template ORDER BY LetterID")
        rows = cursor.fetchall()
        conn.close()
        
        correct = 0
        tested = 0
        results_log = []
        
        for row in rows:
            ch = row['SinhalaChar']
            if ch not in LETTER_TO_CLASS:
                continue
            
            raw_json = row['StrokePathJSON']
            if not raw_json:
                continue
            
            template = json.loads(raw_json)
            if len(template) < 2:
                continue
            
            tested += 1
            result = predictor.predict(template)
            predicted = result.get('letter', '?')
            is_correct = (predicted == ch)
            if is_correct:
                correct += 1
            results_log.append(f"  {ch} → {predicted} ({'✓' if is_correct else '✗'}) conf={result.get('confidence', 0):.2f}")
        
        accuracy = correct / tested if tested > 0 else 0
        ML_GATEKEEPER_RELIABLE = accuracy >= ML_VALIDATION_MIN_ACCURACY
        
        status = "ENABLED" if ML_GATEKEEPER_RELIABLE else "DISABLED"
        print(f"[ML Validation] Model accuracy on templates: {correct}/{tested} ({accuracy:.0%}) — Gatekeeper {status}")
        for line in results_log:
            print(line)
        
        return ML_GATEKEEPER_RELIABLE
        
    except Exception as e:
        print(f"[ML Validation] Error during validation: {e}")
        ML_GATEKEEPER_RELIABLE = False
        return False

app = Flask(__name__)
app.config.from_object(Config)

# --- Helpers ---
def calculate_stars(score):
    """Convert accuracy score (0-100) into stars (1-5). Only for CORRECT_LETTER."""
    if score >= 90: return 5
    if score >= 75: return 4
    if score >= 60: return 3
    if score >= 40: return 2
    return 1


def get_wrong_letter_message(predicted_letter, target_letter):
    """Generate an encouraging bilingual message when a wrong letter is detected."""
    import random
    messages = [
        f"You wrote '{predicted_letter}', but we are learning '{target_letter}' \U0001f41d Let's try again!",
        f"Good try! \U0001f4aa That looks like '{predicted_letter}' — let's practice '{target_letter}' together!",
        f"Almost! \u2728 You drew '{predicted_letter}' instead of '{target_letter}'. Give it another go!",
        f"\u0d94\u0dba\u0dcf \u0dbd\u0dd2\u0dc0\u0dca\u0dc0\u0dda '{predicted_letter}' \u2014 \u0dc4\u0dd0\u0db6\u0dd0\u0dba\u0dd2 \u0d85\u0db4\u0dd2 \u0dbd\u0dd2\u0dba \u0d9c\u0db1\u0dca\u0db1\u0dda '{target_letter}' ! \u0db1\u0dd0\u0dc0\u0dad \u0d8b\u0dad\u0dca\u0dc3\u0dcf\u0dc4 \u0d9a\u0dbb\u0db8\u0dd4! \U0001f31f",
        f"\u0d86\u0dc3\u0db1\u0dca\u0db1\u0dba\u0dd2! \u0d91\u0d9a '{predicted_letter}' \u0dc0\u0d9c\u0dda \u2014 \u0d91\u0dad\u0dca '{target_letter}' \u0dbd\u0dd2\u0dba \u0d9c\u0db1\u0dca\u0db1\u0da7 \u0d8b\u0dad\u0dca\u0dc3\u0dcf\u0dc4 \u0d9a\u0dbb\u0db1\u0dca\u0db1! \U0001f4aa",
        f"Nice effort! \U0001f31f You recognised a letter — just not the right one. Let's try '{target_letter}'!",
    ]
    return random.choice(messages)


def get_scribble_message(target_letter):
    """Generate an encouraging message when the child draws random scribbles instead of a letter."""
    import random
    messages = [
        f"That looks like practice lines 😊 Let's try drawing '{target_letter}' again!",
        f"Nice effort! ✨ Try writing the letter '{target_letter}' shape carefully.",
        f"Let's try again! Look carefully at '{target_letter}' and trace it slowly. You can do it! 💪",
        f"Almost! Focus on the shape of '{target_letter}'. Slow and steady wins the race! 🐝",
        f"Keep going! 🌟 Look at '{target_letter}' on the right and try to copy its shape.",
        f"\u0dc4\u0dbb\u0dd2\u0dba\u0da7 \u0dbd\u0dd2\u0dba\u0db1\u0dca\u0db1 '{target_letter}' \u0d85\u0d9a\u0dca\u0dc2\u0dbb\u0dba \u0db6\u0dbd\u0db1\u0dca\u0db1! Keep trying! 🌈",
    ]
    return random.choice(messages)


# Scribble detection thresholds
SCRIBBLE_SCORE_THRESHOLD = 18      # Below this geometric score → likely scribble
SCRIBBLE_COVERAGE_THRESHOLD = 25   # Below this coverage % → not tracing template
MINIMUM_VALID_SCORE = 12           # Absolute minimum to accept any scoring


def detect_scribble(geo_result):
    """Check if the stroke data looks like random scribbles rather than a letter attempt.
    
    Uses geometric metrics to determine if the child actually tried to write a letter
    or just drew random lines/scribbles.
    
    Returns:
        dict with 'is_scribble' (bool) and 'reason' (str)
    """
    score = geo_result.get('score', 0)
    breakdown = geo_result.get('breakdown', {})
    coverage = breakdown.get('coverage', 0)
    hausdorff = breakdown.get('hausdorff', 1.0)
    chamfer = breakdown.get('chamfer', 1.0)
    procrustes = breakdown.get('procrustes', 1.0)
    
    # Case 1: Extremely low score — almost certainly a scribble or random lines
    if score < MINIMUM_VALID_SCORE:
        return {
            'is_scribble': True,
            'reason': 'very_low_score',
            'detail': f'Score {score:.1f} is too low — input does not resemble any letter shape.'
        }
    
    # Case 2: Low score AND very low coverage — didn't trace the template at all
    if score < SCRIBBLE_SCORE_THRESHOLD and coverage < SCRIBBLE_COVERAGE_THRESHOLD:
        return {
            'is_scribble': True,
            'reason': 'low_score_no_coverage',
            'detail': f'Score {score:.1f}, coverage {coverage:.1f}% — shape does not match the letter.'
        }
    
    # Case 3: All distance metrics are very high — shape is completely wrong
    if hausdorff > 0.45 and chamfer > 0.30 and procrustes > 0.50:
        return {
            'is_scribble': True,
            'reason': 'extreme_distance',
            'detail': 'All shape metrics indicate the drawing is unrelated to the target letter.'
        }
    
    return {'is_scribble': False, 'reason': None, 'detail': None}


def classify_attempt_ml(recognition_result, target_letter):
    """ML-first AI Evaluation Agent — classification with canvas-awareness.

    Uses the SAME ML model as the Recognition Test page.
    ALL letter identification comes from ML model output.
    NO heuristic overrides or geometric cross-checks.

    Canvas strokes (from stroke_to_image) naturally produce lower ML confidence
    than scanned handwriting images the model was trained on (domain gap).
    Therefore classification uses a TWO-TIER threshold approach:
      - If ML's top prediction MATCHES the target: accept with a lenient
        threshold (CANVAS_ACCEPT_THRESHOLD = 0.12) since matching is itself
        strong evidence of correctness.
      - If ML's top prediction DIFFERS from the target: require the standard
        REJECT_THRESHOLD (0.35) before calling it a wrong letter vs scribble.

    Returns:
        dict with classification, predicted_letter, target_letter, confidence,
        give_score, give_stars, score, stars, show_try_again, update_progress, message
    """
    # Lenient threshold when ML already agrees with target letter.
    # Canvas strokes yield ~0.2-0.6 confidence even for correct drawings.
    CANVAS_ACCEPT_THRESHOLD = 0.12

    if not recognition_result:
        return {
            'classification': 'SCRIBBLE_OR_INVALID',
            'predicted_letter': None,
            'target_letter': target_letter or '?',
            'confidence': 0,
            'give_score': False,
            'give_stars': False,
            'score': None,
            'stars': None,
            'show_try_again': True,
            'update_progress': False,
            'message': get_scribble_message(target_letter or '?'),
        }

    predicted_letter = recognition_result.get('letter', '?')
    confidence = recognition_result.get('confidence', 0.0)

    # ── CHECK: Does the ML top prediction match the target? ──
    matches_target = (predicted_letter == target_letter)

    # ── STEP 1: CORRECT LETTER (check first — lenient threshold) ──
    # If ML's best guess IS the target letter and confidence is above the
    # lenient canvas threshold, accept it as correct.
    if matches_target and confidence >= CANVAS_ACCEPT_THRESHOLD:
        return {
            'classification': 'CORRECT_LETTER',
            'predicted_letter': predicted_letter,
            'target_letter': target_letter or '?',
            'confidence': confidence,
            'give_score': True,
            'give_stars': True,
            'score': None,   # filled by caller after quality scoring
            'stars': None,   # filled by caller after star calc
            'show_try_again': False,
            'update_progress': True,
            'message': None,  # filled by get_child_message()
        }

    # ── STEP 2: SCRIBBLE / INVALID ──
    # Confidence too low to identify ANY letter reliably
    if confidence < CANVAS_ACCEPT_THRESHOLD:
        return {
            'classification': 'SCRIBBLE_OR_INVALID',
            'predicted_letter': None,
            'target_letter': target_letter or '?',
            'confidence': confidence,
            'give_score': False,
            'give_stars': False,
            'score': None,
            'stars': None,
            'show_try_again': True,
            'update_progress': False,
            'message': get_scribble_message(target_letter or '?'),
        }

    # ── STEP 3: WRONG LETTER ──
    # ML confidently sees a DIFFERENT letter than the target
    return {
        'classification': 'WRONG_LETTER',
        'predicted_letter': predicted_letter,
        'target_letter': target_letter or '?',
        'confidence': confidence,
        'give_score': False,
        'give_stars': False,
        'score': None,
        'stars': None,
        'show_try_again': True,
        'update_progress': False,
        'message': get_wrong_letter_message(predicted_letter, target_letter or '?'),
    }


def get_child_message(stars, score, error_types):
    """Generate an age-appropriate encouragement message based on performance."""
    import random
    if stars == 5:
        messages = [
            "Wow! Perfect! You're a superstar! 🌟🌟🌟🌟🌟",
            "Amazing! That's beautiful writing! ✨✨✨✨✨",
            "Super! You did it perfectly! 🎉",
        ]
    elif stars == 4:
        messages = [
            "Great job! Almost perfect — keep trying! 🌟🌟🌟🌟",
            "Very good! One more try to get 5 stars! ✨✨✨✨",
            "Well done! You're getting so good! 💪",
        ]
    elif stars == 3:
        messages = [
            "Good try! A bit more practice! 🌟🌟🌟",
            "You can do it! Try once more! ✨✨✨",
            "Getting better! Keep going! 😊",
        ]
    elif stars == 2:
        messages = [
            "Nice effort! Keep practicing! 🌟🌟",
            "You're learning! Try tracing slower! ✨✨",
        ]
    elif stars == 1:
        messages = [
            "Every try makes you better! 🌟",
            "Don't give up! Try again! 💪",
        ]
    else:
        if error_types and error_types.get('wrong_start'):
            messages = ["Try starting from the top of the letter! 👆"]
        elif error_types and error_types.get('missing_stroke'):
            messages = ["Make sure to draw all parts of the letter! ✏️"]
        else:
            messages = [
                "Let's try again — you can do it! 💪",
                "Don't give up! Practice makes perfect! 🌈",
                "Almost! Try one more time! ⭐",
            ]
    return random.choice(messages)

def save_session(child_id, letter_id, score, stars, time_taken=0):
    """Save session log to DB — only updates TotalStars using BEST score per letter"""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO Session_Log (ChildID, LetterID, AccuracyScore, StarsEarned, TimeTakenSeconds)
                VALUES (%s, %s, %s, %s, %s)
            """, (child_id, letter_id, score, stars, time_taken))
            
            # Update TotalStars using MAX stars per letter (best attempt counts)
            cursor.execute("""
                UPDATE Child_Profile 
                SET TotalStars = (
                    SELECT COALESCE(SUM(best_stars), 0) FROM (
                        SELECT MAX(StarsEarned) as best_stars
                        FROM Session_Log WHERE ChildID = %s
                        GROUP BY LetterID
                    ) as best_per_letter
                )
                WHERE ChildID = %s
            """, (child_id, child_id))
            
            conn.commit()
        except Exception as e:
            print(f"Error saving session: {e}")
        finally:
            conn.close()


def generate_correction_guidance(result):
    """Generate child-friendly correction guidance from evaluation result."""
    guidance = []
    error_types = result.get('error_types', {})
    score = result.get('score', 0)
    feedback_text = result.get('feedback_text', '')

    # If the vision engine already produced a feedback sentence, use it
    if feedback_text:
        guidance.append(feedback_text)
        return guidance

    if score >= 90:
        return ["🌟 Excellent work! Your letter looks perfect! Keep it up!"]
    
    if error_types.get('wrong_start'):
        guidance.append("📍 Start from the correct position. Look at where the letter begins in the example.")
    if error_types.get('wrong_direction'):
        guidance.append("↩️ Check your stroke direction. Follow the flow shown in the example letter.")
    if error_types.get('extra_stroke'):
        guidance.append("✂️ You drew some extra lines. Try to follow only the letter shape.")
    if error_types.get('missing_stroke'):
        guidance.append("📝 Some parts of the letter are missing. Make sure to complete all strokes.")
    if error_types.get('poor_shape') and len(error_types['poor_shape']) > 5:
        guidance.append("🔄 The overall shape needs improvement. Practice tracing the letter slowly.")
    elif error_types.get('poor_shape'):
        guidance.append("✏️ Some parts of the shape could be smoother. Try writing a bit more carefully.")
    
    if score >= 75 and not guidance:
        guidance.append("👍 Great job! Just a few small improvements needed.")
    elif not guidance:
        guidance.append("💪 Keep practicing! Look at the example letter carefully and try again.")
    
    return guidance

# --- Routes ---

@app.route('/')
def loading_page():
    return render_template('loading.html')

@app.route('/select-role')
def select_role():
    return render_template('role_selection.html')

@app.route('/guardian-login')
def guardian_login():
    return render_template('login.html', role='guardian')

@app.route('/child-login')
def child_login():
    return render_template('login.html', role='child')

# --- Auth Helpers ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('select_role'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['POST'])
def login_logic():
    from werkzeug.security import check_password_hash
    
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({"success": False, "message": "Please enter both username and password"})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed"})
    
    try:
        cursor = conn.cursor(dictionary=True)
        # Fetch user AND profile name if possible
        cursor.execute("""
            SELECT u.UserID, u.Username, u.PasswordHash, u.Role, g.User_Name as GuardianName 
            FROM user u 
            LEFT JOIN guardian_profile g ON u.UserID = g.UserID 
            WHERE u.Username = %s
        """, (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user['PasswordHash'], password):
            session['user_id'] = user['UserID']
            session['username'] = user['Username']
            session['role'] = user['Role']
            
            # Guardian Login
            if user['Role'] == 'Guardian':
                session['name'] = user['GuardianName'] if user['GuardianName'] else user['Username']
                return jsonify({"success": True, "redirect_url": "/guardian-dashboard"})
            
            # Child Login
            elif user['Role'] == 'Child':
                 # Use INNER JOIN to ensure child profile exists
                conn = get_db_connection()
                c_cursor = conn.cursor(dictionary=True)
                c_cursor.execute("SELECT ChildID, Name, TotalStars FROM Child_Profile WHERE UserID = %s", (user['UserID'],))
                child_profile = c_cursor.fetchone()
                conn.close()
                
                if child_profile:
                    session['child_id'] = child_profile['ChildID']
                    session['child_name'] = child_profile['Name']
                    session['child_stars'] = child_profile['TotalStars']
                    return jsonify({"success": True, "redirect_url": "/home"})
                else:
                    return jsonify({"success": False, "message": "Child Profile not found"})

            return jsonify({"success": True, "redirect_url": "/"})
        else:
            return jsonify({"success": False, "message": "Invalid credentials"})
            
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"success": False, "message": "Server error"})

# --- Signup Routes ---

@app.route('/guardian-signup')
def guardian_signup():
    return render_template('guardian_signup.html')

# Child Signup Template Route Removed

@app.route('/api/guardian-signup', methods=['POST'])
def guardian_signup_logic():
    from werkzeug.security import generate_password_hash
    
    data = request.get_json()
    username = data.get('username')
    fullname = data.get('fullname')
    password = data.get('password')
    
    if not username or not fullname or not password:
        return jsonify({"success": False, "message": "All fields are required"})
    
    if len(password) < 6:
        return jsonify({"success": False, "message": "Password must be at least 6 characters long"})
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed"})
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Check if username already exists
        cursor.execute("SELECT UserID FROM user WHERE Username = %s", (username,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "message": "Username already taken"})
        
        # Create user
        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO user (Username, PasswordHash, Role) VALUES (%s, %s, 'Guardian')",
            (username, password_hash)
        )
        user_id = cursor.lastrowid
        
        # Create guardian profile
        cursor.execute(
            "INSERT INTO guardian_profile (UserID, User_Name) VALUES (%s, %s)",
            (user_id, fullname)
        )
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Account created successfully"})
        
    except Exception as e:
        print(f"Guardian signup error: {e}")
        if conn:
            conn.close()
        return jsonify({"success": False, "message": "Registration failed"})

# Child Signup API Removed (Deprecated)

# --- Logout Route ---

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('select_role'))

# --- Learn Alphabet Pages ---

@app.route('/learn')
@login_required
def learn():
    """Alphabet grid page"""
    return render_template('learn.html')

@app.route('/learn/<int:letter_id>')
@login_required
def letter_detail(letter_id):
    """Letter detail page"""
    return render_template('letter_detail.html', letter_id=letter_id)

# --- API Endpoints for Letters ---

@app.route('/api/letters')
def get_all_letters():
    """Get all letters for alphabet grid"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed"})
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT LetterID, SinhalaChar, DifficultyLevel FROM letter_template ORDER BY LetterID")
        letters = cursor.fetchall()
        conn.close()
        return jsonify({"success": True, "letters": letters})
    except Exception as e:
        print(f"Error fetching letters: {e}")
        if conn:
            conn.close()
        return jsonify({"success": False, "message": "Error fetching letters"})

@app.route('/api/letters/<int:letter_id>')
def get_letter_detail(letter_id):
    """Get detailed info for a specific letter"""
    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed"})
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "SELECT LetterID, SinhalaChar, ImageURL, ExampleWords, DifficultyLevel FROM letter_template WHERE LetterID = %s",
            (letter_id,)
        )
        letter = cursor.fetchone()
        conn.close()
        
        if letter:
            # Parse ExampleWords JSON if it's a string
            if letter['ExampleWords']:
                import json
                try:
                    letter['ExampleWords'] = json.loads(letter['ExampleWords'])
                except:
                    letter['ExampleWords'] = []
            return jsonify({"success": True, "letter": letter})
        else:
            return jsonify({"success": False, "message": "Letter not found"})
    except Exception as e:
        print(f"Error fetching letter detail: {e}")
        if conn:
            conn.close()
        return jsonify({"success": False, "message": "Error fetching letter detail"})

@app.route('/home')
def home():
    # Get child stats if logged in as child
    total_stars = 0
    child_level = 1
    
    if session.get('role') == 'Child' and session.get('child_id'):
        child_id = session.get('child_id')
        conn = get_db_connection()
        
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                
                # Calculate Total Stars
                cursor.execute("""
                    SELECT SUM(StarsEarned) as TotalStars
                    FROM Session_Log
                    WHERE ChildID = %s
                """, (child_id,))
                stars_result = cursor.fetchone()
                total_stars = stars_result['TotalStars'] if stars_result and stars_result['TotalStars'] else 0
                
                # Calculate Level (based on completed letters)
                cursor.execute("""
                    SELECT COUNT(DISTINCT LetterID) as CompletedCount
                    FROM Session_Log
                    WHERE ChildID = %s AND AccuracyScore > 0
                """, (child_id,))
                level_result = cursor.fetchone()
                num_completed = level_result['CompletedCount'] if level_result else 0
                child_level = (num_completed // 5) + 1
                
            except Exception as e:
                print(f"Error fetching child stats for home: {e}")
            finally:
                conn.close()
    
    return render_template('index.html', 
                         total_stars=total_stars,
                         child_level=child_level)

@app.route('/guardian-dashboard')
@login_required
def guardian_dashboard():
    if session.get('role') != 'Guardian':
        return redirect(url_for('select_role'))
        
    conn = get_db_connection()
    children = []
    letters = []
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            # 1. Fetch children
            cursor.execute("""
                SELECT cp.ChildID, cp.Name, cp.Age, cp.TotalStars, u.Username 
                FROM Child_Profile cp
                LEFT JOIN User u ON cp.UserID = u.UserID
                WHERE cp.GuardianID = %s
            """, (session['user_id'],))
            children_data = cursor.fetchall()
            
            children = []
            for child in children_data:
                # Fetch completed letters for feedback tool
                cursor.execute("""
                    SELECT DISTINCT lt.LetterID, lt.SinhalaChar 
                    FROM Session_Log sl
                    JOIN Letter_Template lt ON sl.LetterID = lt.LetterID
                    WHERE sl.ChildID = %s AND sl.StarsEarned > 0
                """, (child['ChildID'],))
                child['completed_letters'] = cursor.fetchall()
                
                # Fetch currently assigned (and NOT yet completed) letters
                cursor.execute("""
                    SELECT lt.LetterID, lt.SinhalaChar 
                    FROM Child_Letter_Assignment cla
                    JOIN Letter_Template lt ON cla.LetterID = lt.LetterID
                    WHERE cla.ChildID = %s 
                    AND cla.LetterID NOT IN (
                        SELECT LetterID FROM Session_Log WHERE ChildID = %s AND StarsEarned > 0
                    )
                """, (child['ChildID'], child['ChildID']))
                child['assigned_not_completed'] = cursor.fetchall()
                
                children.append(child)
            
            # 2. Fetch all letters for assignment
            cursor.execute("SELECT LetterID, SinhalaChar FROM Letter_Template ORDER BY Level, LetterID")
            letters = cursor.fetchall()
        except Exception as e:
            print(f"Error in guardian dashboard: {e}")
        finally:
            conn.close()
    
    return render_template('guardian_dashboard.html', 
                         guardian_name=session.get('name'),
                         children=children,
                         all_letters=letters)

@app.route('/api/add-child', methods=['POST'])
@login_required
def add_child():
    from werkzeug.security import generate_password_hash
    
    data = request.get_json()
    name = data.get('childname')
    age = data.get('age')
    username = data.get('username')
    password = data.get('password')
    
    if not name or not age or not username or not password:
        return jsonify({"success": False, "message": "Missing fields"})
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Create User Account for Child
        password_hash = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO user (Username, PasswordHash, Role) VALUES (%s, %s, 'Child')",
            (username, password_hash)
        )
        new_user_id = cursor.lastrowid
        
        # 2. Create Child Profile linked to Guardian AND Child User
        cursor.execute(
            "INSERT INTO Child_Profile (GuardianID, UserID, Name, Age) VALUES (%s, %s, %s, %s)",
            (session['user_id'], new_user_id, name, age)
        )
        conn.commit()
        conn.close()
        return jsonify({"success": True})
    except Exception as e:
        print(e)
        if conn: conn.close()
        return jsonify({"success": False, "message": "Error adding child (Username taken?)"})

@app.route('/api/delete-child', methods=['POST'])
@login_required
def delete_child():
    data = request.get_json()
    child_id = data.get('child_id')

    if not child_id:
        return jsonify({"success": False, "message": "Missing child ID"})

    conn = get_db_connection()
    try:
        cursor = conn.cursor(dictionary=True)
        # Verify ownership AND fetch UserID to delete the User account (Cascade will handle profile)
        cursor.execute("SELECT UserID FROM Child_Profile WHERE ChildID = %s AND GuardianID = %s", (child_id, session['user_id']))
        child = cursor.fetchone()
        
        if child:
            # Delete the Child's USER account. 
            # ON DELETE CASCADE in schema ensures Child_Profile is also deleted.
            cursor.execute("DELETE FROM User WHERE UserID = %s", (child['UserID'],))
            conn.commit()
            conn.close()
            return jsonify({"success": True})
        else:
            conn.close()
            return jsonify({"success": False, "message": "Unauthorized or Child Not Found"})
            
    except Exception as e:
        print(f"Error deleting child: {e}")
        if conn: conn.close()
        return jsonify({"success": False, "message": "Server Error"})

@app.route('/child-home')
@login_required
def child_home():
    if session.get('role') != 'Child':
        return redirect(url_for('guardian_login')) # Or generic login
    
    child_id = session.get('child_id')
    
    # Fetch Letters and Progress
    conn = get_db_connection()
    letters_data = []
    total_stars = 0
    child_level = 1
    
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            
            # 1. Get All Letters with Level info
            cursor.execute("SELECT LetterID, SinhalaChar, DifficultyLevel, Level FROM Letter_Template ORDER BY Level, LetterID")
            all_letters = cursor.fetchall()
            
            # 2. Get Completed Letters (only those with at least 1 star earned)
            cursor.execute("""
                SELECT LetterID, MAX(StarsEarned) as MaxStars 
                FROM Session_Log 
                WHERE ChildID = %s AND StarsEarned > 0
                GROUP BY LetterID
            """, (child_id,))
            completed_data = {row['LetterID']: row['MaxStars'] for row in cursor.fetchall()}
            
            # 3. Get Guardian Assigned Letters
            cursor.execute("SELECT LetterID FROM Child_Letter_Assignment WHERE ChildID = %s", (child_id,))
            assigned_letters = {row['LetterID'] for row in cursor.fetchall()}
            
            # 4. Fetch Child Stats
            cursor.execute("SELECT TotalStars FROM Child_Profile WHERE ChildID = %s", (child_id,))
            profile_stats = cursor.fetchone()
            total_stars = profile_stats['TotalStars'] if profile_stats else 0
            
            # 5. Get Latest Feedbacks for this child
            cursor.execute("""
                SELECT f.LetterID, f.Message, f.CreatedAt 
                FROM Letter_Progress_Feedback f
                INNER JOIN (
                    SELECT LetterID, MAX(CreatedAt) as MaxDate
                    FROM Letter_Progress_Feedback
                    WHERE ChildID = %s
                    GROUP BY LetterID
                ) latest ON f.LetterID = latest.LetterID AND f.CreatedAt = latest.MaxDate
                WHERE f.ChildID = %s
            """, (child_id, child_id))
            feedbacks = {row['LetterID']: row['Message'] for row in cursor.fetchall()}
            
            # 6. Determine Level & Sequential Progress
            child_level = (total_stars // 5) + 1
            if child_level > 5: child_level = 5 # Max 5 levels for now
            
            is_next_unlock = True # First uncompleted letter in current level
            
            assigned_only = [] # Letters assigned but not completed
            
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
                    # Sequential unlock within or up to current level
                    status = 'unlocked'
                    is_next_unlock = False
                else:
                    status = 'locked'
                
                letters_data.append({
                    "LetterID": l_id,
                    "SinhalaChar": letter['SinhalaChar'],
                    "status": status,
                    "stars": stars,
                    "level": l_level,
                    "difficulty": letter['DifficultyLevel'],
                    "feedback": feedback
                })
                
            session['assigned_only'] = assigned_only # Store for separate display
                
        except Exception as e:
            print(f"Error fetching child progress: {e}")
        finally:
            conn.close()
            
    return render_template('child_home.html', 
                         child_name=session.get('child_name'),
                         total_stars=total_stars,
                         child_level=child_level,
                         letters=letters_data,
                         assigned_letters=session.get('assigned_only', []))

@app.route('/dashboard')
def dashboard_redirect():
    # Redirect legacy /dashboard to guardian dashboard or logic
    if session.get('role') == 'Child':
        return redirect(url_for('child_home'))
    return redirect(url_for('guardian_dashboard'))

@app.route('/write/<int:letter_id>')
@login_required
def write(letter_id):
    if session.get('role') != 'Child' and session.get('role') != 'Guardian':
        return redirect(url_for('select_role'))
        
    conn = get_db_connection()
    letter_char = "අ" # Default fallback
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT SinhalaChar FROM Letter_Template WHERE LetterID = %s", (letter_id,))
            result = cursor.fetchone()
            if result:
                letter_char = result['SinhalaChar']
        except Exception as e:
            print(f"Error fetching letter for write page: {e}")
        finally:
            conn.close()
            
    return render_template('write.html', letter_id=letter_id, letter_char=letter_char)

# --- Profile Management Routes ---

@app.route('/guardian-settings')
@login_required
def guardian_settings():
    if session.get('role') != 'Guardian':
        return redirect(url_for('guardian_dashboard'))
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Fetch current details
    cursor.execute("""
        SELECT u.Username, g.User_Name, g.ProfilePicture 
        FROM User u 
        JOIN Guardian_Profile g ON u.UserID = g.UserID 
        WHERE u.UserID = %s
    """, (session['user_id'],))
    profile = cursor.fetchone()
    conn.close()
    
    return render_template('guardian_settings.html', 
                         username=profile['Username'], 
                         name=profile['User_Name'],
                         avatar=profile['ProfilePicture'])

@app.route('/api/update-profile', methods=['POST'])
@login_required
def update_profile():
    data = request.get_json()
    new_name = data.get('name')
    new_username = data.get('username')
    
    if not new_name or not new_username:
        return jsonify({"success": False, "message": "Fields cannot be empty"})
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        
        # 1. Update Guardian Profile Name
        cursor.execute("UPDATE Guardian_Profile SET User_Name = %s WHERE UserID = %s", (new_name, session['user_id']))
        
        # 2. Update User Username (Check duplicate handled by DB Constraint, but good to catch)
        cursor.execute("UPDATE User SET Username = %s WHERE UserID = %s", (new_username, session['user_id']))
        
        conn.commit()
        conn.close()
        
        # Update Session
        session['name'] = new_name
        session['username'] = new_username
        
        return jsonify({"success": True, "message": "Profile Updated"})
    except Exception as e:
        if conn: conn.close()
        return jsonify({"success": False, "message": "Error (Username taken?)"})

@app.route('/api/change-password', methods=['POST'])
@login_required
def change_password():
    from werkzeug.security import generate_password_hash, check_password_hash
    data = request.get_json()
    old_pass = data.get('old_password')
    new_pass = data.get('new_password')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT PasswordHash FROM User WHERE UserID = %s", (session['user_id'],))
    user = cursor.fetchone()
    
    if user and check_password_hash(user['PasswordHash'], old_pass):
        new_hash = generate_password_hash(new_pass)
        cursor.execute("UPDATE User SET PasswordHash = %s WHERE UserID = %s", (new_hash, session['user_id']))
        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Password Changed"})
    else:
        conn.close()
        return jsonify({"success": False, "message": "Incorrect Current Password"})

@app.route('/profile')
@login_required
def profile():
    role = session.get('role')
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if role == 'Guardian':
        cursor.execute("""
            SELECT u.Username, g.User_Name, g.ProfilePicture 
            FROM User u 
            JOIN Guardian_Profile g ON u.UserID = g.UserID 
            WHERE u.UserID = %s
        """, (session['user_id'],))
        profile = cursor.fetchone()
        conn.close()
        return render_template('guardian_settings.html', 
                             username=profile['Username'], 
                             name=profile['User_Name'],
                             avatar=profile['ProfilePicture'])
                             
    elif role == 'Child':
        child_id = session.get('child_id')
        cursor.execute("""
            SELECT u.Username, c.Name, c.Avatar 
            FROM User u 
            JOIN Child_Profile c ON u.UserID = c.UserID 
            WHERE c.ChildID = %s
        """, (child_id,))
        profile = cursor.fetchone()
        conn.close()
        return render_template('child_settings.html', 
                             username=profile['Username'], 
                             name=profile['Name'],
                             avatar=profile['Avatar'])
    
    return redirect(url_for('select_role'))

@app.route('/api/update-child-profile', methods=['POST'])
@login_required
def update_child_profile():
    if session.get('role') != 'Child':
        return jsonify({"success": False, "message": "Unauthorized"})

    data = request.get_json()
    new_name = data.get('name')
    new_username = data.get('username')
    
    if not new_name or not new_username:
        return jsonify({"success": False, "message": "Fields cannot be empty"})
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        child_id = session.get('child_id')
        user_id = session.get('user_id')
        
        # 1. Update Child Profile Name
        cursor.execute("UPDATE Child_Profile SET Name = %s WHERE ChildID = %s", (new_name, child_id))
        
        # 2. Update User Username
        cursor.execute("UPDATE User SET Username = %s WHERE UserID = %s", (new_username, user_id))
        
        conn.commit()
        conn.close()
        
        # Update Session
        session['child_name'] = new_name
        session['username'] = new_username
        
        return jsonify({"success": True, "message": "Profile Updated"})
    except Exception as e:
        if conn: conn.close()
        print(e)
        return jsonify({"success": False, "message": "Error (Username taken?)"})

@app.route('/api/upload-avatar', methods=['POST'])
@login_required
def upload_avatar():
    import os
    from werkzeug.utils import secure_filename
    
    if 'avatar' not in request.files:
        return jsonify({"success": False, "message": "No file part"})
    
    file = request.files['avatar']
    if file.filename == '':
        return jsonify({"success": False, "message": "No selected file"})
        
    if file:
        filename = secure_filename(file.filename)
        # Ensure unique name to avoid cache issues
        import time
        unique_filename = f"{session['user_id']}_{int(time.time())}_{filename}"
        
        upload_folder = os.path.join(app.root_path, 'static', 'uploads', 'avatars')
        os.makedirs(upload_folder, exist_ok=True)
        
        file.save(os.path.join(upload_folder, unique_filename))
        
        # Update DB based on Role
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if session.get('role') == 'Guardian':
            cursor.execute("UPDATE Guardian_Profile SET ProfilePicture = %s WHERE UserID = %s", (unique_filename, session['user_id']))
        elif session.get('role') == 'Child':
            cursor.execute("UPDATE Child_Profile SET Avatar = %s WHERE ChildID = %s", (unique_filename, session.get('child_id')))
            
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "Avatar Uploaded"})
        
# --- APIs ---

@app.route('/api/letters', methods=['GET'])
def get_letters():
    conn = get_db_connection()
    if not conn:
        # Return Demo Data if DB fails
        return jsonify({"success": True, "letters": [
            {"LetterID": 1, "SinhalaChar": "අ", "DifficultyLevel": "Easy"},
            {"LetterID": 2, "SinhalaChar": "ආ", "DifficultyLevel": "Easy"},
            {"LetterID": 3, "SinhalaChar": "ඇ", "DifficultyLevel": "Medium"}
        ]})
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT LetterID, SinhalaChar, DifficultyLevel FROM letter_template")
        letters = cursor.fetchall()
        conn.close()
        return jsonify({"success": True, "letters": letters})
    except Exception as e:
        print(f"Error fetching letters: {e}")
        conn.close()
        return jsonify({"success": False, "letters": []})

@app.route('/api/submit_attempt', methods=['POST'])
def submit_attempt():
    """Receive stroke from client, evaluate using ML-first classification.

    Integration Flow (ML-first — same model as Recognition Test page):
      1. ML recognition runs FIRST for ML-supported letters (14 letters).
         Uses the SAME preprocessing pipeline and model as /api/recognize.
      2. ML classifies: SCRIBBLE_OR_INVALID / WRONG_LETTER / CORRECT_LETTER
         based on ML confidence and prediction — NO heuristic overrides.
      3. Only CORRECT_LETTER proceeds to quality scoring.
      4. Quality score = 75% geometric + 25% CNN target-class confidence.
      5. For non-ML letters, geometric scoring + scribble detection.
    """
    data = request.get_json()
    user_path = data.get('path', [])
    letter_id = data.get('letter_id')
    input_mode = data.get('input_mode', 'draw')  # 'camera' or 'draw'

    if not user_path or len(user_path) < 3:
        return jsonify({"success": False, "error": "Not enough stroke data. Please draw more."})

    # ── 1. Fetch letter info and template from DB ──
    template_path = []
    target_letter = None

    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT SinhalaChar, StrokePathJSON FROM Letter_Template WHERE LetterID = %s", (letter_id,))
            row = cursor.fetchone()
            if row:
                target_letter = row['SinhalaChar']
                raw_json = row['StrokePathJSON']
                if raw_json:
                    parsed = json.loads(raw_json)
                    if isinstance(parsed, list) and len(parsed) >= 2:
                        template_path = parsed
        except Exception:
            pass
        finally:
            conn.close()

    if not template_path:
        return jsonify({"success": False, "error": "No reference template found for this letter."})

    # Determine if this letter is ML-supported (gatekeeper)
    is_ml_letter = ML_AVAILABLE and target_letter and target_letter in LETTER_TO_CLASS

    # Lazy-validate ML model on first request
    global ML_GATEKEEPER_RELIABLE
    if ML_GATEKEEPER_RELIABLE is None and ML_AVAILABLE:
        validate_ml_model()

    child_id = session.get('child_id')
    recognition_result = None
    gatekeeper_result = None
    prediction_id = None
    cnn_correct_confidence = None   # confidence for the TARGET class (0.0-1.0)

    # ══════════════════════════════════════════════════════════
    # STEP 1: ML RECOGNITION — MANDATORY for ML-supported letters
    # Uses the SAME model + preprocessing as /api/recognize (Recognition Test)
    # ALL letter identification comes from ML model output.
    # ══════════════════════════════════════════════════════════
    if is_ml_letter and ML_AVAILABLE:
        try:
            recognizer = get_recognizer()

            # Run the SAME prediction pipeline used by the Recognition Test page
            recognition_result = recognizer.predict(user_path)
            gatekeeper_result = recognizer.validate_letter(
                user_path, target_letter=target_letter
            )

            # Extract confidence for the TARGET class
            cnn_correct_confidence = gatekeeper_result.get('target_confidence', 0.0)
            if cnn_correct_confidence is None:
                cnn_correct_confidence = 0.0

            # Log prediction
            try:
                prediction_id = log_prediction(
                    child_id, letter_id, target_letter,
                    recognition_result, gatekeeper_result
                )
            except Exception:
                pass

            # ── ML-FIRST CLASSIFICATION (no heuristic overrides) ──
            classification = classify_attempt_ml(recognition_result, target_letter)

            # SCRIBBLE_OR_INVALID or WRONG_LETTER → block immediately
            # NO geometric cross-check — ML model is the sole authority
            if classification['classification'] != 'CORRECT_LETTER':
                try:
                    log_stroke_data(child_id, letter_id, user_path, prediction_id, score=0)
                except Exception:
                    pass

                return jsonify({
                    "success": False,
                    "blocked": True,
                    "classification": classification['classification'],
                    "give_score": False,
                    "give_stars": False,
                    "show_try_again": True,
                    "update_progress": False,
                    "block_reason": classification['classification'].lower(),
                    "reason": classification['message'],
                    "message": classification['message'],
                    "predicted_letter": classification.get('predicted_letter'),
                    "target_letter": classification.get('target_letter', target_letter or '?'),
                    "confidence": classification.get('confidence', 0),
                    "score": 0,
                    "stars": 0,
                    "child_message": classification['message'],
                })

        except Exception as e:
            # ML failed — fall through to geometric-only scoring as safety net
            if ML_AVAILABLE:
                try:
                    log_ml_error('ml_recognition', type(e).__name__, str(e), traceback.format_exc())
                except Exception:
                    pass
            print(f"[Submit] ML recognition failed: {e} — falling back to geometric")

    # ══════════════════════════════════════════════════════════
    # STEP 2: GEOMETRIC QUALITY SCORING
    # For ML letters: runs AFTER ML confirms CORRECT_LETTER
    # For non-ML letters: primary evaluation method
    # ══════════════════════════════════════════════════════════
    result = evaluate_stroke(user_path, template_path)
    geo_score = result['score']

    # Non-ML letters only: geometric scribble detection (fallback — no ML model)
    if not is_ml_letter or not ML_AVAILABLE or recognition_result is None:
        scribble_check = detect_scribble(result)
        if scribble_check['is_scribble']:
            try:
                if ML_AVAILABLE:
                    log_stroke_data(child_id, letter_id, user_path, prediction_id, score=0)
            except Exception:
                pass

            scribble_msg = get_scribble_message(target_letter or '?')
            return jsonify({
                "success": False,
                "blocked": True,
                "classification": "SCRIBBLE_OR_INVALID",
                "give_score": False,
                "give_stars": False,
                "show_try_again": True,
                "update_progress": False,
                "block_reason": "scribble_or_invalid",
                "reason": scribble_check['detail'],
                "message": scribble_msg,
                "predicted_letter": None,
                "target_letter": target_letter or '?',
                "confidence": 0,
                "score": 0,
                "stars": 0,
                "child_message": scribble_msg,
            })

    # ── STEP 3: Score blending (CORRECT_LETTER only) ──
    if is_ml_letter and cnn_correct_confidence is not None and cnn_correct_confidence > 0.1:
        cnn_component = cnn_correct_confidence * 100.0
        blended = 0.75 * geo_score + 0.25 * cnn_component
        scoring_method = 'blended'
    else:
        blended = geo_score
        scoring_method = 'geometric'

    score = round(max(0.0, min(100.0, blended)), 1)
    stars = calculate_stars(score)

    # Update result dict so downstream (logging, feedback) sees the blended score
    result['score'] = score
    result['stars'] = stars
    result['error_score'] = round(100.0 - score, 1)
    result['scoring_method'] = scoring_method

    # Recalculate feedback level based on blended score
    if score >= 88:
        result['feedback_level'] = 'excellent'
    elif score >= 72:
        result['feedback_level'] = 'good'
    elif score >= 55:
        result['feedback_level'] = 'fair'
    else:
        result['feedback_level'] = 'needs_practice'

    # Cache stroke data in session for the GET endpoint
    session['last_stroke_data'] = json.dumps(user_path)
    session['last_letter_id'] = letter_id

    # ── 4. Log to ML database ──
    if ML_AVAILABLE:
        try:
            score_id = log_score(prediction_id, child_id, letter_id, result,
                                scoring_method=scoring_method)
            log_error_feedback(score_id, prediction_id, child_id,
                             {'level': result.get('feedback_level', ''),
                              'message': result.get('feedback_text', ''),
                              'suggestions': [], 'error_areas': result.get('errors', [])},
                             {'error_types': result.get('error_types', {}),
                              'error_indices': result.get('error_indices', [])})
        except Exception:
            pass

    # ── 5. Collect training data ──
    if ML_AVAILABLE and app.config.get('COLLECT_TRAINING_DATA', True):
        try:
            meta = {
                "predicted_id": recognition_result['class_id'] if recognition_result else None,
                "confidence": recognition_result['confidence'] if recognition_result else 0,
                "gatekeeper_allowed": gatekeeper_result.get('allowed', True) if gatekeeper_result else True,
            }
            save_training_sample(letter_id, user_path, result, metadata=meta, input_mode=input_mode)
            log_stroke_data(child_id, letter_id, user_path, prediction_id, score=score)
        except Exception:
            pass

    # ── 6. Save Session — ONLY for CORRECT_LETTER classification ──
    # AI Evaluation Agent Step 3: This attempt passed Steps 1 & 2, so it is CORRECT_LETTER.
    # Score and stars are awarded and progress is saved.
    if child_id:
        save_session(child_id, letter_id, score, stars)

    # ── 7. Generate guidance + child message ──
    guidance = generate_correction_guidance(result)

    child_message = get_child_message(stars, score, result.get('error_types', {}))

    # ── 8. Return structured result — CORRECT_LETTER ──
    return jsonify({
        "success": True,
        "classification": "CORRECT_LETTER",
        "give_score": True,
        "give_stars": True,
        "show_try_again": False,
        "update_progress": True,
        "letter_id": letter_id,
        "score": score,
        "accuracy": score,
        "stars": stars,
        "child_message": child_message,
        "error_score": result.get('error_score', round(100 - score, 1)),
        "errors": result.get('errors', []),
        "error_indices": result.get('error_indices', []),
        "error_types": result.get('error_types', {}),
        "error_regions": result.get('error_regions', []),
        "breakdown": result.get('breakdown', {}),
        "metric_breakdown": result.get('breakdown', {}),
        "feedback_level": result.get('feedback_level', 'needs_practice'),
        "feedback_text": result.get('feedback_text', ''),
        "guidance": guidance,
        "scoring_method": scoring_method,
        "cnn_confidence": round(cnn_correct_confidence * 100, 1) if cnn_correct_confidence is not None else None,
        "recognition": {
            "predicted_letter": recognition_result.get('letter', '?') if recognition_result else None,
            "confidence": recognition_result.get('confidence', 0) if recognition_result else None,
            "target_confidence": round(cnn_correct_confidence, 4) if cnn_correct_confidence is not None else None,
            "match": gatekeeper_result.get('match', None) if gatekeeper_result else None,
        } if is_ml_letter and recognition_result else None,
    })


@app.route('/evaluate-letter', methods=['GET'])
def evaluate_letter_get():
    """
    GET endpoint for letter evaluation.
    Retrieves stroke data from session cache or database records,
    then runs deterministic geometric evaluation.

    Required query parameters:
      - user_id:    int  (child user ID)
      - letter_id:  int  (Letter_Template.LetterID)
      - session_id: int  (Session_Log.SessionID, optional — latest used if omitted)

    Stroke data is retrieved internally from:
      1. Flask session cache (set during last submit_attempt)
      2. ML_Stroke_Data table (latest entry for this child/letter)

    Returns:
      JSON with accuracy, stars, error_score, errors, metric_breakdown, feedback_text
    """
    user_id = request.args.get('user_id', type=int)
    letter_id = request.args.get('letter_id', type=int)
    session_id = request.args.get('session_id', type=int)

    if not letter_id:
        return jsonify({"success": False, "error": "letter_id is required."}), 400

    # ── 1. Load template ──
    template_path = []
    target_letter = None
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT SinhalaChar, StrokePathJSON FROM Letter_Template WHERE LetterID = %s", (letter_id,))
            row = cursor.fetchone()
            if row:
                target_letter = row['SinhalaChar']
                raw_json = row['StrokePathJSON']
                if raw_json:
                    parsed = json.loads(raw_json)
                    if isinstance(parsed, list) and len(parsed) >= 2:
                        template_path = parsed
        except Exception:
            pass
        finally:
            conn.close()

    if not template_path:
        return jsonify({"success": False, "error": "No template found for this letter."}), 404

    # ── 2. Retrieve user stroke data ──
    user_path = None

    # Try session cache first (from last submit_attempt)
    cached_stroke = session.get('last_stroke_data')
    cached_letter = session.get('last_letter_id')
    if cached_stroke and cached_letter == letter_id:
        try:
            user_path = json.loads(cached_stroke)
        except Exception:
            pass

    # Fallback: load from ML_Stroke_Data table
    if not user_path and ML_AVAILABLE:
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                query = "SELECT StrokeJSON FROM ML_Stroke_Data WHERE LetterID = %s"
                params = [letter_id]
                if user_id:
                    query += " AND ChildID = %s"
                    params.append(user_id)
                query += " ORDER BY CreatedAt DESC LIMIT 1"
                cursor.execute(query, params)
                row = cursor.fetchone()
                if row and row['StrokeJSON']:
                    user_path = json.loads(row['StrokeJSON'])
            except Exception:
                pass
            finally:
                conn.close()

    if not user_path or len(user_path) < 3:
        return jsonify({"success": False, "error": "No stroke data found. Submit an attempt first."}), 404

    # ── 3. Run geometric evaluation ──
    result = evaluate_stroke(user_path, template_path)

    # ── 4. Return structured response (matches required output format) ──
    return jsonify({
        "success": True,
        "letter_id": letter_id,
        "accuracy": result.get('score', 0),
        "stars": result.get('stars', 0),
        "error_score": result.get('error_score', 0),
        "errors": result.get('errors', []),
        "metric_breakdown": result.get('breakdown', {}),
        "feedback_text": result.get('feedback_text', ''),
        "error_indices": result.get('error_indices', []),
        "error_types": result.get('error_types', {}),
        "error_regions": result.get('error_regions', []),
        "scoring_method": "geometric",
    })


@app.route('/api/recognize', methods=['POST'])
def recognize_letter_api():
    """Independent endpoint to identify which Sinhala letter was drawn.
    Used by the recognition test page for standalone testing.
    """
    if not ML_AVAILABLE:
        return jsonify({"success": False, "error": "ML Pipeline not available. Train the model first."})

    data = request.get_json()
    user_path = data.get('path', [])
    target_letter = data.get('target_letter', None)

    if not user_path or len(user_path) < 2:
        return jsonify({"success": False, "error": "Not enough stroke data. Please draw more."})

    try:
        recognizer = get_recognizer()
        result = recognizer.predict(user_path)

        # If target provided, also run gatekeeper validation
        validation = None
        if target_letter:
            validation = recognizer.validate_letter(user_path, target_letter=target_letter)

        response = {
            "success": True,
            "letter_id": result['class_id'],
            "letter": result['letter'],
            "confidence": result['confidence'],
            "all_probabilities": result['probabilities'],
            "is_confident": result.get('is_confident', False),
        }

        if validation:
            response['validation'] = {
                "match": validation.get('match'),
                "allowed": validation.get('allowed'),
                "reason": validation.get('reason'),
            }

        # Log to database
        try:
            child_id = session.get('child_id')
            log_prediction(child_id, None, target_letter, result,
                         validation or {'match': None, 'allowed': True, 'reason': 'standalone test'})
        except:
            pass

        return jsonify(response)

    except Exception as e:
        print(f"[Recognize] Error: {e}")
        if ML_AVAILABLE:
            try:
                log_ml_error('recognize_api', type(e).__name__, str(e), traceback.format_exc())
            except:
                pass
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/assign-letter', methods=['POST'])
@login_required
def assign_letter():
    if session.get('role') != 'Guardian':
        return jsonify({"success": False, "message": "Unauthorized"})
        
    data = request.get_json()
    child_id = data.get('child_id')
    letter_id = data.get('letter_id')
    
    if not child_id or not letter_id:
        return jsonify({"success": False, "message": "Missing Data"})
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Verify child belongs to this guardian
        cursor.execute("SELECT ChildID FROM Child_Profile WHERE ChildID = %s AND GuardianID = %s", (child_id, session['user_id']))
        if cursor.fetchone():
            cursor.execute("INSERT IGNORE INTO Child_Letter_Assignment (ChildID, LetterID) VALUES (%s, %s)", (child_id, letter_id))
            conn.commit()
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Unauthorized access to child profile"})
    except Exception as e:
        print(f"Error assigning letter: {e}")
        return jsonify({"success": False, "message": "Execution Error"})
    finally:
        if conn: conn.close()

@app.route('/api/submit-feedback', methods=['POST'])
@login_required
def submit_feedback():
    if session.get('role') != 'Guardian':
        return jsonify({"success": False, "message": "Unauthorized"})
        
    data = request.get_json()
    child_id = data.get('child_id')
    letter_id = data.get('letter_id')
    message = data.get('message')
    
    if not child_id or not letter_id or not message:
        return jsonify({"success": False, "message": "Missing Data"})
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # Verify child belongs to this guardian
        cursor.execute("SELECT ChildID FROM Child_Profile WHERE ChildID = %s AND GuardianID = %s", (child_id, session['user_id']))
        if cursor.fetchone():
            cursor.execute("""
                INSERT INTO Letter_Progress_Feedback (ChildID, LetterID, GuardianID, Message)
                VALUES (%s, %s, %s, %s)
            """, (child_id, letter_id, session['user_id'], message))
            conn.commit()
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "Unauthorized access to child profile"})
    except Exception as e:
        print(f"Error submitting feedback: {e}")
        return jsonify({"success": False, "message": "Execution Error"})
    finally:
        if conn: conn.close()

@app.route('/recognition-test')
def recognition_test():
    """Testing page for the ML Recognition Model."""
    return render_template('recognition_test.html')


# --- Live Scoring API (Real-time feedback during writing) ---

@app.route('/api/live-score', methods=['POST'])
def live_score():
    """Real-time scoring endpoint — runs geometric evaluation + optional CNN blend.
    Called periodically during writing to update score display.
    Works for ALL 32 letters; ML letters get CNN confidence blended in."""
    data = request.get_json()
    user_path = data.get('path', [])
    letter_id = data.get('letter_id')

    if not user_path or len(user_path) < 5:
        return jsonify({"success": True, "score": 0, "confidence": 0, "quality": "low"})

    try:
        # Get template and letter info
        template_path = []
        target_letter = None
        conn = get_db_connection()
        if conn:
            try:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT SinhalaChar, StrokePathJSON FROM Letter_Template WHERE LetterID = %s", (letter_id,))
                lt = cursor.fetchone()
                if lt:
                    target_letter = lt.get('SinhalaChar')
                    if lt['StrokePathJSON']:
                        parsed = json.loads(lt['StrokePathJSON'])
                        if isinstance(parsed, list) and len(parsed) >= 2:
                            template_path = parsed
            except Exception:
                pass
            finally:
                conn.close()

        if not template_path:
            return jsonify({"success": True, "score": 0, "confidence": 0, "quality": "low",
                            "message": "No template available"})

        # Run geometric evaluation
        result = evaluate_stroke(user_path, template_path)
        geo_score = result.get('score', 0)

        # Blend CNN confidence for ML letters
        is_ml_letter = ML_AVAILABLE and target_letter and target_letter in LETTER_TO_CLASS
        if is_ml_letter:
            try:
                recognizer = get_recognizer()
                gk = recognizer.validate_letter(user_path, target_letter=target_letter)
                cnn_conf = gk.get('target_confidence', 0.0) or 0.0
                quick_score = 0.75 * geo_score + 0.25 * (cnn_conf * 100.0)
            except Exception:
                quick_score = geo_score
        else:
            quick_score = geo_score

        quick_score = round(max(0.0, min(100.0, quick_score)), 1)

        # Determine quality level for stroke coloring
        if quick_score >= 55:
            quality = "good"
        elif quick_score >= 30:
            quality = "fair"
        else:
            quality = "low"

        return jsonify({
            "success": True,
            "score": quick_score,
            "confidence": round(quick_score / 100.0, 4),
            "quality": quality,
            "coverage": result.get('breakdown', {}).get('coverage', 0),
        })
    except Exception:
        return jsonify({"success": True, "score": 0, "confidence": 0, "quality": "low"})


# --- Guardian: Child Progress API ---

@app.route('/api/child-progress/<int:child_id>')
@login_required
def get_child_progress(child_id):
    """Get detailed progress data for a child — used by guardian dashboard."""
    if session.get('role') != 'Guardian':
        return jsonify({"success": False, "message": "Unauthorized"})

    conn = get_db_connection()
    if not conn:
        return jsonify({"success": False, "message": "Database connection failed"})

    try:
        cursor = conn.cursor(dictionary=True)

        # Verify guardian owns this child
        cursor.execute(
            "SELECT ChildID, Name FROM Child_Profile WHERE ChildID = %s AND GuardianID = %s",
            (child_id, session['user_id'])
        )
        child = cursor.fetchone()
        if not child:
            conn.close()
            return jsonify({"success": False, "message": "Child not found or unauthorized"})

        # Letter-wise best scores
        cursor.execute("""
            SELECT sl.LetterID, lt.SinhalaChar,
                   MAX(sl.AccuracyScore) as BestScore,
                   MAX(sl.StarsEarned) as BestStars,
                   COUNT(*) as Attempts,
                   AVG(sl.AccuracyScore) as AvgScore
            FROM Session_Log sl
            JOIN Letter_Template lt ON sl.LetterID = lt.LetterID
            WHERE sl.ChildID = %s
            GROUP BY sl.LetterID, lt.SinhalaChar
            ORDER BY lt.LetterID
        """, (child_id,))
        letter_progress = cursor.fetchall()

        for lp in letter_progress:
            lp['BestScore'] = float(lp['BestScore']) if lp['BestScore'] else 0
            lp['BestStars'] = int(lp['BestStars']) if lp['BestStars'] else 0
            lp['Attempts'] = int(lp['Attempts'])
            lp['AvgScore'] = round(float(lp['AvgScore']), 1) if lp['AvgScore'] else 0

        # Total stars (sum of best stars per letter)
        cursor.execute("""
            SELECT COALESCE(SUM(best_stars), 0) as TotalStars FROM (
                SELECT MAX(StarsEarned) as best_stars
                FROM Session_Log WHERE ChildID = %s
                GROUP BY LetterID
            ) as best_per_letter
        """, (child_id,))
        total_row = cursor.fetchone()
        total_stars = int(total_row['TotalStars']) if total_row and total_row['TotalStars'] else 0

        # Weak letters (avg score < 60 or best < 75)
        weak_letters = [
            {"LetterID": lp['LetterID'], "SinhalaChar": lp['SinhalaChar'],
             "AvgScore": lp['AvgScore'], "BestScore": lp['BestScore']}
            for lp in letter_progress if lp['AvgScore'] < 60
        ]

        # Recent attempts (last 10)
        cursor.execute("""
            SELECT sl.LetterID, lt.SinhalaChar, sl.AccuracyScore,
                   sl.StarsEarned, sl.PlayedAt
            FROM Session_Log sl
            JOIN Letter_Template lt ON sl.LetterID = lt.LetterID
            WHERE sl.ChildID = %s
            ORDER BY sl.PlayedAt DESC
            LIMIT 10
        """, (child_id,))
        recent = cursor.fetchall()
        for r in recent:
            r['AccuracyScore'] = float(r['AccuracyScore']) if r['AccuracyScore'] else 0
            r['StarsEarned'] = int(r['StarsEarned']) if r['StarsEarned'] else 0
            r['PlayedAt'] = r['PlayedAt'].strftime('%Y-%m-%d %H:%M') if r['PlayedAt'] else ''

        # Accuracy trend (last 20 attempts in chronological order)
        cursor.execute("""
            SELECT sl.AccuracyScore, sl.PlayedAt
            FROM Session_Log sl
            WHERE sl.ChildID = %s
            ORDER BY sl.PlayedAt DESC
            LIMIT 20
        """, (child_id,))
        trend_data = cursor.fetchall()
        trend_data.reverse()  # chronological order
        accuracy_trend = [
            {"score": float(t['AccuracyScore']) if t['AccuracyScore'] else 0,
             "date": t['PlayedAt'].strftime('%m/%d') if t['PlayedAt'] else ''}
            for t in trend_data
        ]

        conn.close()

        return jsonify({
            "success": True,
            "child_name": child['Name'],
            "total_stars": total_stars,
            "letter_progress": letter_progress,
            "weak_letters": weak_letters,
            "recent_attempts": recent,
            "accuracy_trend": accuracy_trend,
        })
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({"success": False, "message": str(e)})

if __name__ == '__main__':
    app.run(debug=True)
