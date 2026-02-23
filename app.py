from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from functools import wraps
from config import Config
from database import get_db_connection
from vision_engine import calculate_score
import json

app = Flask(__name__)
app.config.from_object(Config)

# --- Helpers ---
def calculate_stars(score):
    """Convert accuracy score (0-100) into stars (0-3)"""
    if score >= 85: return 3
    if score >= 60: return 2
    if score >= 30: return 1
    return 0

def save_session(child_id, letter_id, score, stars, time_taken=0):
    """Save session log to DB"""
    conn = get_db_connection()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO Session_Log (ChildID, LetterID, AccuracyScore, StarsEarned, TimeTakenSeconds)
                VALUES (%s, %s, %s, %s, %s)
            """, (child_id, letter_id, score, stars, time_taken))
            
            # Also update TotalStars in Child_Profile for easier access
            cursor.execute("""
                UPDATE Child_Profile 
                SET TotalStars = (SELECT SUM(StarsEarned) FROM Session_Log WHERE ChildID = %s)
                WHERE ChildID = %s
            """, (child_id, child_id))
            
            conn.commit()
        except Exception as e:
            print(f"Error saving session: {e}")
        finally:
            conn.close()

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
            
            # 2. Get Completed Letters (Score > 0)
            cursor.execute("""
                SELECT LetterID, MAX(StarsEarned) as MaxStars 
                FROM Session_Log 
                WHERE ChildID = %s 
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
    data = request.get_json()
    user_path = data.get('path', [])
    letter_id = data.get('letter_id')
    
    # 1. Fetch Template from DB
    conn = get_db_connection()
    template_path = []
    
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT StrokePathJSON FROM Letter_Template WHERE LetterID = %s", (letter_id,))
        result = cursor.fetchone()
        
        if result and result['StrokePathJSON']:
            template_path = json.loads(result['StrokePathJSON'])
        
        # MOCK TEMPLATE IF EMPTY DB (For Verification without seeding)
        if not template_path:
            # A simple vertical line mock for testing
            template_path = [{'x': 0.5, 'y': 0.2}, {'x': 0.5, 'y': 0.8}]
            
        conn.close()
    else:
        # Fallback if DB fails
        template_path = [{'x': 0.5, 'y': 0.2}, {'x': 0.5, 'y': 0.8}]

    # 2. Calculate Score
    score, error_indices = calculate_score(user_path, template_path)
    stars = calculate_stars(score)
    
    # 3. Save Session if logged in
    child_id = session.get('child_id')
    if child_id:
        save_session(child_id, letter_id, score, stars)

    return jsonify({
        "success": True, 
        "score": score, 
        "stars": stars,
        "error_indices": error_indices
    })

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

if __name__ == '__main__':
    app.run(debug=True)
