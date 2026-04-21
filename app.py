from flask import Flask, render_template, request, redirect, session, g
import sqlite3
from textblob import TextBlob
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret123"

DATABASE = "database.db"

# ================= DATABASE =================
def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

def init_db():
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()

    # USERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT
    )
    """)

    # POSTS (Journal)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT,
        sentiment TEXT,
        date TEXT
    )
    """)

    # CHAT
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        date TEXT
    )
    """)

    db.commit()
    db.close()

# ================= SENTIMENT =================
def analyze_sentiment(text):
    analysis = TextBlob(text)
    if analysis.sentiment.polarity > 0:
        return "Positive 😊"
    elif analysis.sentiment.polarity < 0:
        return "Negative 😔"
    else:
        return "Neutral 😐"

# ================= ROUTES =================

# LOGIN
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        cursor = db.cursor()

        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()

        if user:
            session["user_id"] = user[0]
            return redirect("/dashboard")
        else:
            return "Invalid Login"

    return render_template("login.html")


# REGISTER
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        db = get_db()
        cursor = db.cursor()

        try:
            cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            db.commit()
            return redirect("/")
        except:
            return "Username already exists"

    return render_template("register.html")


# DASHBOARD
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")
    return render_template("dashboard.html")


# JOURNAL
@app.route("/journal", methods=["GET", "POST"])
def journal():
    if "user_id" not in session:
        return redirect("/")

    if request.method == "POST":
        content = request.form["content"]

        sentiment = analyze_sentiment(content)

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
        INSERT INTO posts (user_id, content, sentiment, date)
        VALUES (?, ?, ?, ?)
        """, (session["user_id"], content, sentiment, datetime.now()))

        db.commit()

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT content, sentiment, date FROM posts WHERE user_id=?", (session["user_id"],))
    posts = cursor.fetchall()

    return render_template("journal.html", posts=posts)


# CHAT
@app.route("/chat", methods=["GET", "POST"])
def chat():
    if "user_id" not in session:
        return redirect("/")

    if request.method == "POST":
        message = request.form["message"]

        db = get_db()
        cursor = db.cursor()

        cursor.execute("""
        INSERT INTO chat (user_id, message, date)
        VALUES (?, ?, ?)
        """, (session["user_id"], message, datetime.now()))

        db.commit()

    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT message, date FROM chat WHERE user_id=?", (session["user_id"],))
    messages = cursor.fetchall()

    return render_template("chat.html", messages=messages)


# LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


# ================= RUN =================
if __name__ == "__main__":
    init_db()
    app.run(debug=True) 