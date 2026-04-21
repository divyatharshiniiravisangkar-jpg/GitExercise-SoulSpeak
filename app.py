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
        db.row_factory = sqlite3.Row # This allows accessing columns by name
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    with app.app_context():
        db = get_db()
        # USERS
        db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )""")
        # POSTS (Private Journal)
        db.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            content TEXT,
            sentiment TEXT,
            date TEXT
        )""")
        # CHAT (With Reply Support)
        db.execute("""
        CREATE TABLE IF NOT EXISTS chat (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            message TEXT,
            reply_to INTEGER DEFAULT NULL,
            date TEXT
        )""")
        db.commit()

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

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password)).fetchone()
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/dashboard")
        return "Invalid Login"
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        db = get_db()
        try:
            db.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            db.commit()
            return redirect("/")
        except:
            return "Username already exists"
    return render_template("register.html")

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/")
    return render_template("dashboard.html")

@app.route("/journal", methods=["GET", "POST"])
def journal():
    if "user_id" not in session:
        return redirect("/")
    db = get_db()
    if request.method == "POST":
        content = request.form["content"]
        sentiment = analyze_sentiment(content)
        db.execute("INSERT INTO posts (user_id, content, sentiment, date) VALUES (?, ?, ?, ?)",
                   (session["user_id"], content, sentiment, datetime.now().strftime("%Y-%m-%d %H:%M")))
        db.commit()
    
    # Strictly fetch only this user's posts (Private)
    posts = db.execute("SELECT content, sentiment, date FROM posts WHERE user_id=? ORDER BY id DESC", (session["user_id"],)).fetchall()
    return render_template("journal.html", posts=posts)

@app.route("/chat", methods=["GET", "POST"])
def chat():
    if "user_id" not in session:
        return redirect("/")
    db = get_db()
    if request.method == "POST":
        message = request.form["message"]
        reply_to = request.form.get("reply_to") # Get the ID of the message being replied to
        db.execute("INSERT INTO chat (user_id, message, reply_to, date) VALUES (?, ?, ?, ?)",
                   (session["user_id"], message, reply_to, datetime.now().strftime("%H:%M")))
        db.commit()

    # Query that joins chat with itself to show what message is being replied to
    messages = db.execute("""
        SELECT c1.id, c1.message, c1.date, u.username, c2.message AS replying_to_msg
        FROM chat c1
        JOIN users u ON c1.user_id = u.id
        LEFT JOIN chat c2 ON c1.reply_to = c2.id
        ORDER BY c1.id ASC
    """).fetchall()
    return render_template("chat.html", messages=messages)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)