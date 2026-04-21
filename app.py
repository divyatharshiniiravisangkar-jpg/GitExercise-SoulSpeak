import sqlite3
from flask import Flask, render_template, request, redirect, url_for, g, session, flash
from datetime import datetime
from textblob import TextBlob
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'soulspeak_secure_key_123'  # Change this for production
DATABASE = 'database.db'

# --- DATABASE MANAGEMENT ---

def get_db():
    """Opens connection and enables WAL mode for syncing/concurrency."""
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, timeout=20)
        db.row_factory = sqlite3.Row
        # Sync Fixes: Enable Write-Ahead Logging
        db.execute('PRAGMA journal_mode=WAL;')
        db.execute('PRAGMA synchronous=NORMAL;')
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Creates the full schema for all members' features."""
    with app.app_context():
        db = get_db()
        # 1. Users (Logan)
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )''')
        # 2. Chat (Logan & Divyatharshinii)
        db.execute('''CREATE TABLE IF NOT EXISTS chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT NOT NULL,
            sentiment_polarity REAL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        # 3. Journal (Pravien)
        db.execute('''CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            entry TEXT NOT NULL,
            mood_tag TEXT,
            sentiment_score REAL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        db.commit()

# --- AI & NLP LOGIC ---

def get_sentiment(text):
    """Member 1 AI Integration: Classifies text using TextBlob."""
    analysis = TextBlob(text)
    polarity = analysis.sentiment.polarity
    if polarity > 0.1: mood = "Positive"
    elif polarity < -0.1: mood = "Negative"
    else: mood = "Neutral"
    return polarity, mood

# --- ROUTES ---

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('home.html', username=session.get('username'))

# AUTHENTICATION (Member 1: Logan)
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form['username']
        pwd = generate_password_hash(request.form['password'])
        db = get_db()
        try:
            db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (user, pwd))
            db.commit()
            flash("Registration successful! Please login.")
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash("Username already exists.")
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        db = get_db()
        user_data = db.execute("SELECT * FROM users WHERE username = ?", (user,)).fetchone()
        if user_data and check_password_hash(user_data['password'], pwd):
            session['user_id'] = user_data['id']
            session['username'] = user_data['username']
            return redirect(url_for('home'))
        flash("Invalid credentials.")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# CHAT SYSTEM (Member 1 & 2)
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db()
    
    if request.method == 'POST':
        msg = request.form.get('message')
        polarity, mood = get_sentiment(msg) # AI Integration
        db.execute("INSERT INTO chat (user_id, message, sentiment_polarity) VALUES (?, ?, ?)", 
                   (session['user_id'], msg, polarity))
        db.commit()

    messages = db.execute('''
        SELECT chat.*, users.username FROM chat 
        JOIN users ON chat.user_id = users.id 
        ORDER BY date DESC
    ''').fetchall()
    return render_template('chat.html', messages=messages)

# DIARY & MOOD TRACKING (Member 3: Pravien)
@app.route('/diary', methods=['GET', 'POST'])
def diary():
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db()

    if request.method == 'POST':
        entry = request.form.get('entry')
        polarity, mood = get_sentiment(entry)
        db.execute("INSERT INTO journal (user_id, entry, mood_tag, sentiment_score) VALUES (?, ?, ?, ?)",
                   (session['user_id'], entry, mood, polarity))
        db.commit()
        flash(f"Diary saved. We detected your mood as: {mood}")

    entries = db.execute("SELECT * FROM journal WHERE user_id = ? ORDER BY date DESC", 
                        (session['user_id'],)).fetchall()
    return render_template('diary.html', entries=entries)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)