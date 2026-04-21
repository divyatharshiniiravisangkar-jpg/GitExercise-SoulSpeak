<<<<<<< HEAD
from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "secret123"

# ---------------- DATABASE ----------------
def get_db():
    conn = sqlite3.connect("soulspeak.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    # USERS TABLE
    conn.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )
    """)

    # DIARY TABLE
    conn.execute("""
    CREATE TABLE IF NOT EXISTS diary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- HOME ----------------
@app.route("/")
=======
from flask import Flask, render_template, request

app = Flask("Soul Speak")

@app.route('/')
>>>>>>> f42508935373f9b300753a1f5d0a4b79a68569f6
def home():
    return render_template('homepage.html')

<<<<<<< HEAD
# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password)
            )
            conn.commit()
            conn.close()
            return redirect("/login")
        except:
            return "Username already exists!"

    return render_template("register.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
=======
@app.route('/login', methods=['GET', 'POST'])
>>>>>>> f42508935373f9b300753a1f5d0a4b79a68569f6
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

<<<<<<< HEAD
        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect("/diary")
        else:
            return "Invalid login!"
=======
        return f"Login received: {username}"

    return render_template('login.html')

>>>>>>> f42508935373f9b300753a1f5d0a4b79a68569f6

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
# ---------------- DIARY ----------------
@app.route("/diary", methods=["GET", "POST"])
def diary():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_db()

    # SAVE ENTRY
    if request.method == "POST":
        content = request.form["content"]

        conn.execute(
            "INSERT INTO diary (user_id, content) VALUES (?, ?)",
            (session["user_id"], content)
        )
        conn.commit()

    # GET ENTRIES
    entries = conn.execute(
        "SELECT content, created_at FROM diary WHERE user_id=? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()

    conn.close()

    return render_template(
        "diary.html",
        user=session["username"],
        entries=entries
    )

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
=======
        return f"Registered: {username}"

    return render_template('register.html')



if __name__ == '__main__':
>>>>>>> f42508935373f9b300753a1f5d0a4b79a68569f6
    app.run(debug=True)