# ==========================================
# SOULSPEAK FULL PROJECT
# app.py
# ==========================================

from flask import Flask
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from flask import flash

from flask_sqlalchemy import SQLAlchemy

from flask_login import LoginManager
from flask_login import UserMixin
from flask_login import login_user
from flask_login import logout_user
from flask_login import login_required
from flask_login import current_user

from datetime import datetime

# ==========================================
# FLASK CONFIGURATION
# ==========================================

app = Flask(__name__)

app.config['SECRET_KEY'] = 'soulspeaksecret'

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'

db = SQLAlchemy(app)

# ==========================================
# LOGIN MANAGER
# ==========================================

login_manager = LoginManager()

login_manager.init_app(app)

login_manager.login_view = 'login'

# ==========================================
# DATABASE TABLES
# ==========================================

class User(UserMixin, db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    username = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False
    )

    password = db.Column(
        db.String(100),
        nullable=False
    )


class Post(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    content = db.Column(
        db.Text,
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )


class Diary(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    content = db.Column(
        db.Text,
        nullable=False
    )

    date = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )


class Chat(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    message = db.Column(
        db.Text,
        nullable=False
    )

    sender = db.Column(
        db.String(100),
        nullable=False
    )

# ==========================================
# USER LOADER
# ==========================================

@login_manager.user_loader
def load_user(user_id):

    return User.query.get(int(user_id))

# ==========================================
# HOME PAGE
# ==========================================

@app.route('/')
def home():

    return render_template('index.html')

# ==========================================
# REGISTER
# ==========================================

@app.route('/register', methods=['GET', 'POST'])
def register():

    if request.method == 'POST':

        username = request.form['username']

        email = request.form['email']

        password = request.form['password']

        # CHECK EMAIL ONLY

        existing_email = User.query.filter_by(
            email=email
        ).first()

        if existing_email:

            flash('Email already registered')

            return redirect(url_for('register'))

        # CREATE USER

        new_user = User(
            username=username,
            email=email,
            password=password
        )

        db.session.add(new_user)

        db.session.commit()

        flash('Registration Successful')

        return redirect(url_for('login'))

    return render_template('register.html')

# ==========================================
# LOGIN
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email']

        password = request.form['password']

        user = User.query.filter_by(
            email=email,
            password=password
        ).first()

        if user:

            login_user(user)

            return redirect(url_for('dashboard'))

        flash('Invalid Email or Password')

    return render_template('login.html')

# ==========================================
# LOGOUT
# ==========================================

@app.route('/logout')
@login_required
def logout():

    logout_user()

    return redirect(url_for('home'))

# ==========================================
# DASHBOARD
# ==========================================

@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():

    if request.method == 'POST':

        content = request.form['content']

        post = Post(
            content=content,
            user_id=current_user.id
        )

        db.session.add(post)

        db.session.commit()

    posts = Post.query.all()

    return render_template(
        'dashboard.html',
        posts=posts
    )

# ==========================================
# DIARY
# ==========================================

@app.route('/diary', methods=['GET', 'POST'])
@login_required
def diary():

    if request.method == 'POST':

        content = request.form['content']

        entry = Diary(
            content=content,
            user_id=current_user.id
        )

        db.session.add(entry)

        db.session.commit()

    entries = Diary.query.filter_by(
        user_id=current_user.id
    ).all()

    return render_template(
        'diary.html',
        entries=entries
    )

# ==========================================
# CHAT ROOM
# ==========================================

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():

    if request.method == 'POST':

        message = request.form['message']

        new_message = Chat(
            message=message,
            sender=current_user.username
        )

        db.session.add(new_message)

        db.session.commit()

    messages = Chat.query.all()

    return render_template(
        'chat.html',
        messages=messages
    )

# ==========================================
# CREATE DATABASE
# ==========================================

if __name__ == '__main__':

    with app.app_context():

        db.create_all()

    app.run(debug=True)