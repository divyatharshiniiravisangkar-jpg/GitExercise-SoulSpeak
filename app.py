from flask import Flask, render_template, request

app = Flask("Soul Speak")

@app.route('/')
def home():
    return render_template('homepage.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        return f"Login received: {username}"

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        return f"Registered: {username}"

    return render_template('register.html')


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