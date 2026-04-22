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
def home():
    return render_template('homepage.html')

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
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

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


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Simple check for demo
        if username == 'admin' and password == 'admin':
            return "Admin login successful"
        else:
            return "Invalid credentials"

    return render_template('admin_login.html')


@app.route('/admin')
def admin_dashboard():
    # Dummy data
    total_users = 10
    total_posts = 5
    users = [
        {'id': 1, 'username': 'user1'},
        {'id': 2, 'username': 'user2'}
    ]
    posts = [
        {'id': 1, 'content': 'Sample post', 'sentiment': 'positive'},
        {'id': 2, 'content': 'Another post', 'sentiment': 'neutral'}
    ]
    return render_template('admin_dashbaord.html', total_users=total_users, total_posts=total_posts, users=users, posts=posts)


@app.route('/search_user', methods=['GET'])
def search_user():
    username = request.args.get('username')
    # Dummy search
    if username:
        users = [{'id': 1, 'username': username}]
    else:
        users = []
    return render_template('admin_dashbaord.html', users=users, posts=[], total_users=0, total_posts=0)


@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    return f"User {user_id} deleted"


@app.route('/delete_post/<int:post_id>', methods=['POST'])
def delete_post(post_id):
    return f"Post {post_id} deleted"


@app.route('/admin_logout')
def admin_logout():
    return "Logged out"


if __name__ == '__main__':
    app.run(debug=True)