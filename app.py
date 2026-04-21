import sqlite3
from flask import Flask, render_template, request, redirect, url_for, g, session, flash
from textblob import TextBlob
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'soulspeak_secret_key'
DATABASE = 'database.db'

# --- DATABASE HELPERS ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        # timeout=20 and WAL mode help prevent "database is locked"
        db = g._database = sqlite3.connect(DATABASE, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL;')
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        # Users Table
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )''')
        # Chat Table
        db.execute('''CREATE TABLE IF NOT EXISTS chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT NOT NULL,
            sentiment_polarity REAL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        # Journal Table
        db.execute('''CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            entry TEXT NOT NULL,
            mood_tag TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        db.commit()

# --- NLP LOGIC ---
def analyze(text):
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity
    mood = "Positive" if polarity > 0.1 else "Negative" if polarity < -0.1 else "Neutral"
    return polarity, mood

# --- ROUTES ---

@app.route('/')
def home():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('home.html', username=session['username'], is_admin=session.get('is_admin'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        db = get_db()
        row = db.execute("SELECT * FROM users WHERE username = ?", (user,)).fetchone()
        if row and check_password_hash(row['password'], pwd):
            session['user_id'] = row['id']
            session['username'] = row['username']
            session['is_admin'] = row['is_admin']
            return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db()
    if request.method == 'POST':
        msg = request.form.get('message')
        pol, _ = analyze(msg)
        db.execute("INSERT INTO chat (user_id, message, sentiment_polarity) VALUES (?, ?, ?)", 
                   (session['user_id'], msg, pol))
        db.commit()
    
    messages = db.execute("SELECT chat.*, users.username FROM chat JOIN users ON chat.user_id = users.id ORDER BY date DESC").fetchall()
    return render_template('chat.html', messages=messages)

@app.route('/journal', methods=['GET', 'POST'])
def journal():
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db()
    if request.method == 'POST':
        entry = request.form.get('entry')
        _, mood = analyze(entry)
        db.execute("INSERT INTO journal (user_id, entry, mood_tag) VALUES (?, ?, ?)", 
                   (session['user_id'], entry, mood))
        db.commit()
    
    entries = db.execute("SELECT * FROM journal WHERE user_id = ? ORDER BY date DESC", (session['user_id'],)).fetchall()
    return render_template('journal.html', entries=entries)

# --- ADMIN VIEW ---
@app.route('/admin')
def admin_view():
    if not session.get('is_admin'): 
        return "Access Denied", 403
    db = get_db()
    all_chats = db.execute("SELECT chat.*, users.username FROM chat JOIN users ON chat.user_id = users.id").fetchall()
    return render_template('admin.html', chats=all_chats)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)