import sqlite3
from datetime import datetime
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = "soulspeak-secret-key"
DATABASE = "users.db"

POSITIVE_WORDS = {
    "happy", "hopeful", "good", "great", "love", "calm", "excited", "joy",
    "better", "grateful", "peace", "relaxed", "smile", "proud", "fine",
}
NEGATIVE_WORDS = {
    "sad", "angry", "upset", "bad", "hate", "tired", "stress", "stressed",
    "anxious", "lonely", "depressed", "worried", "pain", "cry", "fear",
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    cursor = db.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    existing_columns = {
        row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()
    }
    if "email" not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN email TEXT")
    if "created_at" not in existing_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN created_at TEXT")
        cursor.execute(
            "UPDATE users SET created_at = ? WHERE created_at IS NULL",
            (datetime.now().strftime("%Y-%m-%d %H:%M"),),
        )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS diary_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS anonymous_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            mood TEXT NOT NULL,
            sentiment TEXT NOT NULL,
            polarity REAL NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            reply_to INTEGER,
            sentiment_polarity REAL NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (reply_to) REFERENCES chat_messages(id)
        )
        """
    )

    admin = cursor.execute(
        "SELECT id FROM users WHERE username = ?", ("admin",)
    ).fetchone()
    if admin is None:
        cursor.execute(
            """
            INSERT INTO users (username, email, password, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                "admin",
                "admin@soulspeak.local",
                generate_password_hash("admin"),
                datetime.now().strftime("%Y-%m-%d %H:%M"),
            ),
        )

    db.commit()
    db.close()


def analyze_sentiment(text):
    words = [word.strip(".,!?").lower() for word in text.split()]
    if not words:
        return 0.0, "neutral"

    positive_hits = sum(1 for word in words if word in POSITIVE_WORDS)
    negative_hits = sum(1 for word in words if word in NEGATIVE_WORDS)
    polarity = round((positive_hits - negative_hits) / max(len(words), 1), 2)

    if polarity > 0.1:
        return polarity, "positive"
    if polarity < -0.1:
        return polarity, "negative"
    return polarity, "neutral"


def build_suggestions(mood, sentiment):
    mood_tips = {
        "happy": [
            "Keep the momentum going by writing down one thing you are proud of.",
            "Share your positive energy with someone you trust today.",
            "Capture this moment in your diary so you can revisit it later.",
        ],
        "sad": [
            "Try a short walk or a few deep breaths to reset your mind.",
            "Write one honest sentence about what hurts most right now.",
            "Reach out to a trusted friend or family member if you need support.",
        ],
        "angry": [
            "Pause before reacting and write what triggered you.",
            "Take five slow breaths and step away for a few minutes.",
            "Turn the energy into movement like stretching or a short walk.",
        ],
        "stressed": [
            "Break your worries into one small next step you can control.",
            "Try a two-minute breathing break before doing anything else.",
            "Write a short list of priorities instead of carrying them in your head.",
        ],
        "neutral": [
            "Notice one small detail about your day and write it down.",
            "Check in with yourself and name what you need most right now.",
            "Use this calm moment to plan one helpful habit for tomorrow.",
        ],
    }
    suggestions = mood_tips.get(mood, mood_tips["neutral"]).copy()
    if sentiment == "negative":
        suggestions[0] = "Be gentle with yourself and focus on one small comforting action."
    elif sentiment == "positive":
        suggestions[1] = "Celebrate this win by saving it in your diary or sharing it kindly."
    return suggestions


def password_matches(stored_password, provided_password):
    if not stored_password:
        return False
    if stored_password.startswith("pbkdf2:") or stored_password.startswith("scrypt:"):
        return check_password_hash(stored_password, provided_password)
    return stored_password == provided_password


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "error")
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Admin access required.", "error")
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped_view


@app.context_processor
def inject_user():
    return {
        "current_username": session.get("username"),
        "is_admin": session.get("is_admin", False),
    }


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not email or not password:
            flash("Please fill in all registration fields.", "error")
            return render_template("register.html")

        db = get_db()
        try:
            db.execute(
                """
                INSERT INTO users (username, email, password, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    username,
                    email,
                    generate_password_hash(password),
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                ),
            )
            db.commit()
        except sqlite3.IntegrityError:
            flash("That username is already taken.", "error")
            return render_template("register.html")

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if user and password_matches(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = user["username"] == "admin"
            flash("Welcome back.", "success")
            return redirect(url_for("home"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))


@app.route("/dashboard")
def dashboard():
    return redirect(url_for("home"))


@app.route("/homepage")
def homepage():
    return redirect(url_for("home"))


@app.route("/journal", methods=["GET", "POST"])
def journal():
    result = None
    if request.method == "POST":
        text = request.form.get("thoughts", "").strip()
        mood = request.form.get("mood", "neutral")
        if text:
            polarity, sentiment = analyze_sentiment(text)
            db = get_db()
            db.execute(
                """
                INSERT INTO anonymous_posts (content, mood, sentiment, polarity, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    text,
                    mood,
                    sentiment,
                    polarity,
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                ),
            )
            db.commit()
            result = {
                "polarity": polarity,
                "sentiment": sentiment,
                "suggestions": build_suggestions(mood, sentiment),
            }
            flash("Your anonymous post has been shared.", "success")
        else:
            flash("Please write something before submitting.", "error")

    return render_template("journal.html", result=result)


@app.route("/post", methods=["GET", "POST"])
def post():
    return journal()


@app.route("/diary", methods=["GET", "POST"])
@login_required
def diary():
    db = get_db()

    if request.method == "POST":
        text = request.form.get("entry", "").strip()
        if text:
            db.execute(
                """
                INSERT INTO diary_entries (user_id, text, created_at)
                VALUES (?, ?, ?)
                """,
                (
                    session["user_id"],
                    text,
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                ),
            )
            db.commit()
            flash("Diary entry saved.", "success")
            return redirect(url_for("diary"))
        flash("Your diary entry cannot be empty.", "error")

    entries = db.execute(
        """
        SELECT id, text, created_at
        FROM diary_entries
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (session["user_id"],),
    ).fetchall()
    return render_template("diary.html", entries=entries)


@app.route("/chat", methods=["GET", "POST"])
@login_required
def chat():
    db = get_db()

    if request.method == "POST":
        message = request.form.get("message", "").strip()
        reply_to = request.form.get("reply_to") or None
        if message:
            polarity, _sentiment = analyze_sentiment(message)
            db.execute(
                """
                INSERT INTO chat_messages (user_id, message, reply_to, sentiment_polarity, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session["user_id"],
                    message,
                    int(reply_to) if reply_to else None,
                    polarity,
                    datetime.now().strftime("%Y-%m-%d %H:%M"),
                ),
            )
            db.commit()
            flash("Message sent.", "success")
            return redirect(url_for("chat"))
        flash("Please type a message.", "error")

    messages = db.execute(
        """
        SELECT
            chat_messages.id,
            users.username,
            chat_messages.message,
            chat_messages.sentiment_polarity,
            chat_messages.created_at,
            parent.message AS replying_to_msg
        FROM chat_messages
        JOIN users ON users.id = chat_messages.user_id
        LEFT JOIN chat_messages AS parent ON parent.id = chat_messages.reply_to
        ORDER BY chat_messages.id DESC
        """
    ).fetchall()
    return render_template("chat.html", messages=messages)


@app.route("/mood")
@login_required
def mood():
    db = get_db()
    posts = db.execute(
        """
        SELECT mood, sentiment
        FROM anonymous_posts
        ORDER BY id DESC
        """
    ).fetchall()

    total_entries = len(posts)
    current_mood = posts[0]["mood"] if posts else "neutral"

    positive_count = sum(1 for post in posts if post["sentiment"] == "positive")
    negative_count = sum(1 for post in posts if post["sentiment"] == "negative")
    neutral_count = sum(1 for post in posts if post["sentiment"] == "neutral")

    def percent(count):
        return round((count / total_entries) * 100) if total_entries else 0

    return render_template(
        "mood.html",
        current_mood=current_mood,
        positive_percent=percent(positive_count),
        negative_percent=percent(negative_count),
        neutral_percent=percent(neutral_count),
        total_entries=total_entries,
    )


@app.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if (
            user
            and user["username"] == "admin"
            and password_matches(user["password"], password)
        ):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["is_admin"] = True
            flash("Admin login successful.", "success")
            return redirect(url_for("admin_dashboard"))

        flash("Invalid admin credentials.", "error")

    return render_template("admin_login.html")


@app.route("/admin")
@admin_required
def admin_dashboard():
    username = request.args.get("username", "").strip()
    db = get_db()

    if username:
        users = db.execute(
            """
            SELECT id, username, email, created_at
            FROM users
            WHERE username LIKE ?
            ORDER BY id DESC
            """,
            (f"%{username}%",),
        ).fetchall()
    else:
        users = db.execute(
            """
            SELECT id, username, email, created_at
            FROM users
            ORDER BY id DESC
            """
        ).fetchall()

    posts = db.execute(
        """
        SELECT id, content, sentiment, mood, created_at
        FROM anonymous_posts
        ORDER BY id DESC
        """
    ).fetchall()

    return render_template(
        "admin.html",
        users=users,
        posts=posts,
        total_users=len(users),
        total_posts=len(posts),
        search_query=username,
    )


@app.route("/search_user")
@admin_required
def search_user():
    return redirect(url_for("admin_dashboard", username=request.args.get("username", "")))


@app.route("/delete_user/<int:user_id>", methods=["POST"])
@admin_required
def delete_user(user_id):
    if session.get("user_id") == user_id:
        flash("You cannot delete the currently logged in admin account.", "error")
        return redirect(url_for("admin_dashboard"))

    db = get_db()
    db.execute("DELETE FROM diary_entries WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM chat_messages WHERE user_id = ?", (user_id,))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    flash("User deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/delete_post/<int:post_id>", methods=["POST"])
@admin_required
def delete_post(post_id):
    db = get_db()
    db.execute("DELETE FROM anonymous_posts WHERE id = ?", (post_id,))
    db.commit()
    flash("Post deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin_logout")
def admin_logout():
    session.clear()
    flash("Admin session ended.", "success")
    return redirect(url_for("home"))


init_db()


if __name__ == "__main__":
    app.run(debug=True)