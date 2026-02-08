from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
from config import Config
from database import get_db_connection
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY  # Ensure secret key is set

# Admin Login Decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- Routes ---

@app.route('/')
def index():
    if 'admin_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        conn = get_db_connection()
        if not conn:
            return "Database Error", 500
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Admin_User WHERE Username = %s", (username,))
        admin = cursor.fetchone()
        conn.close()
        
        if admin and check_password_hash(admin['PasswordHash'], password):
            session['admin_id'] = admin['AdminID']
            session['admin_name'] = admin['Username']
            session['role'] = admin['Role']
            return redirect(url_for('dashboard'))
        else:
            return render_template('admin/login.html', error="Invalid Credentials")

    return render_template('admin/login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@admin_required
def dashboard():
    conn = get_db_connection()
    stats = {}
    recent_activity = []
    recent_guardians = []
    
    if conn:
        cursor = conn.cursor(dictionary=True)
        
        # 1. Key Statistics
        cursor.execute("SELECT COUNT(*) as count FROM User WHERE Role='Guardian'")
        stats['guardians'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM Child_Profile")
        stats['children'] = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM User WHERE Role='Child'")
        stats['active_learners'] = cursor.fetchone()['count']
        
        # 2. Recent Learning Activity (Live Feed)
        cursor.execute("""
            SELECT sl.PlayedAt, cp.Name as ChildName, lt.SinhalaChar, sl.StarsEarned
            FROM Session_Log sl
            JOIN Child_Profile cp ON sl.ChildID = cp.ChildID
            JOIN Letter_Template lt ON sl.LetterID = lt.LetterID
            ORDER BY sl.PlayedAt DESC LIMIT 5
        """)
        recent_activity = cursor.fetchall()

        # 3. Newest Guardians
        cursor.execute("SELECT Username, CreatedAt FROM User WHERE Role='Guardian' ORDER BY CreatedAt DESC LIMIT 5")
        recent_guardians = cursor.fetchall()
        
        conn.close()
        
    return render_template('admin/dashboard.html', stats=stats, recent_activity=recent_activity, recent_guardians=recent_guardians)

@app.route('/guardians')
@admin_required
def list_guardians():
    conn = get_db_connection()
    guardians = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT u.UserID, u.Username, u.CreatedAt,
            (SELECT COUNT(*) FROM Child_Profile WHERE GuardianID = u.UserID) as child_count
            FROM User u WHERE u.Role = 'Guardian'
        """)
        guardians = cursor.fetchall()
        conn.close()
    return render_template('admin/guardians.html', guardians=guardians)

@app.route('/children')
@admin_required
def list_children():
    conn = get_db_connection()
    children = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT cp.*, u.Username as ParentName
            FROM Child_Profile cp
            JOIN User u ON cp.GuardianID = u.UserID
        """)
        children = cursor.fetchall()
        conn.close()
    return render_template('admin/children.html', children=children)

@app.route('/letters', methods=['GET', 'POST'])
@admin_required
def manage_letters():
    conn = get_db_connection()
    if request.method == 'POST':
        # Add new letter logic here
        pass
    letters = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Letter_Template ORDER BY Level, LetterID")
        letters = cursor.fetchall()
        conn.close()
    return render_template('admin/letters.html', letters=letters)

@app.route('/feedback')
@admin_required
def view_feedback():
    conn = get_db_connection()
    feedbacks = []
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT f.*, u.Username as GuardianName
            FROM Feedback f
            JOIN User u ON f.GuardianID = u.UserID
            ORDER BY f.SubmittedAt DESC
        """)
        feedbacks = cursor.fetchall()
        conn.close()
    return render_template('admin/feedback.html', feedbacks=feedbacks)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
