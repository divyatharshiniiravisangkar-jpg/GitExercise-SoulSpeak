import sqlite3
import os
from flask import Flask, render_template, request, redirect, url_for, g, session, flash
from textblob import TextBlob
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'soulspeak_2026_key'
DATABASE = 'database.db'

# --- DATABASE SETUP WITH SYNC FIX ---
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE, timeout=20)
        db.row_factory = sqlite3.Row
        # WAL Mode prevents "Database is Locked" errors
        db.execute('PRAGMA journal_mode=WAL;')
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    """Creates tables for all members' features."""
    with app.app_context():
        db = get_db()
        # 1. Users (Logan)
        db.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin INTEGER DEFAULT 0
        )''')
        # 2. Chat with Reply Logic (Divyatharshinii)
        db.execute('''CREATE TABLE IF NOT EXISTS chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT NOT NULL,
            sentiment_polarity REAL,
            reply_to INTEGER DEFAULT NULL, 
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        # 3. Diary (Pravien)
        db.execute('''CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            entry TEXT NOT NULL,
            mood_tag TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )''')
        db.commit()

# --- AI SENTIMENT ENGINE ---
def analyze_mood(text):
    blob = TextBlob(text)
    pol = blob.sentiment.polarity
    if pol > 0.1: mood = "Positive"
    elif pol < -0.1: mood = "Negative"
    else: mood = "Neutral"
    return pol, mood

# --- ACCESS CONTROL ---
@app.route('/')
def home():
    if 'user_id' not in session: return redirect(url_for('login'))
    return render_template('home.html', username=session['username'], is_admin=session.get('is_admin'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        user = request.form['username']
        hashed_pwd = generate_password_hash(request.form['password'])
        db = get_db()
        try:
            db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (user, hashed_pwd))
            db.commit()
            return redirect(url_for('login'))
        except:
            flash("Username taken!")
    return render_template('register.html')

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

# --- CHAT & REPLY (Logan/Divya) ---
@app.route('/chat', methods=['GET', 'POST'])
def chat():
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db()
    if request.method == 'POST':
        msg = request.form.get('message')
        reply_id = request.form.get('reply_to') # This captures the ID of the msg being replied to
        pol, _ = analyze_mood(msg)
        db.execute("INSERT INTO chat (user_id, message, sentiment_polarity, reply_to) VALUES (?, ?, ?, ?)", 
                   (session['user_id'], msg, pol, reply_id))
        db.commit()
    
    # Get messages and join with usernames
    messages = db.execute('''
        SELECT chat.*, users.username FROM chat 
        JOIN users ON chat.user_id = users.id 
        ORDER BY date DESC
    ''').fetchall()
    return render_template('chat.html', messages=messages)

# --- DIARY (Pravien) ---
@app.route('/diary', methods=['GET', 'POST'])
def diary():
    if 'user_id' not in session: return redirect(url_for('login'))
    db = get_db()
    if request.method == 'POST':
        entry = request.form.get('entry')
        _, mood = analyze_mood(entry)
        db.execute("INSERT INTO journal (user_id, entry, mood_tag) VALUES (?, ?, ?)", 
                   (session['user_id'], entry, mood))
        db.commit()
    entries = db.execute("SELECT * FROM journal WHERE user_id = ? ORDER BY date DESC", (session['user_id'],)).fetchall()
    return render_template('diary.html', entries=entries)

# --- ADMIN PANEL ---
@app.route('/admin')
def admin():
    if not session.get('is_admin'): return "Access Denied", 403
    db = get_db()
    chats = db.execute("SELECT chat.*, users.username FROM chat JOIN users ON chat.user_id = users.id").fetchall()
    return render_template('admin.html', chats=chats)

# SECRET ROUTE TO MAKE YOURSELF ADMIN
@app.route('/make_admin/<name>')
def make_admin(name):
    db = get_db()
    db.execute("UPDATE users SET is_admin = 1 WHERE username = ?", (name,))
    db.commit()
    return f"{name} is now an Admin! Access at /admin"

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True)