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
from sqlalchemy import inspect, text

from flask_login import LoginManager
from flask_login import UserMixin
from flask_login import login_user
from flask_login import logout_user
from flask_login import login_required
import os

from flask_login import current_user

from datetime import datetime

# ==========================================
# FLASK CONFIGURATION
# ==========================================

app = Flask(__name__, instance_relative_config=True)

app.config['SECRET_KEY'] = 'soulspeaksecret'

os.makedirs(app.instance_path, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(app.instance_path, 'database.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

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

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id')
    )

    recipient = db.Column(
        db.String(100),
        nullable=False,
        default='Admin'
    )

    reply_to = db.Column(
        db.Integer,
        db.ForeignKey('chat.id'),
        nullable=True
    )


def init_db():
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        if inspector.has_table('chat'):
            result = db.session.execute(text("PRAGMA table_info(chat)"))
            columns = [row[1] for row in result]
            if 'user_id' not in columns:
                db.session.execute(text('ALTER TABLE chat ADD COLUMN user_id INTEGER'))
            if 'recipient' not in columns:
                db.session.execute(text("ALTER TABLE chat ADD COLUMN recipient VARCHAR(100) NOT NULL DEFAULT 'Admin'"))
            if 'reply_to' not in columns:
                db.session.execute(text('ALTER TABLE chat ADD COLUMN reply_to INTEGER'))
            db.session.commit()

init_db()

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

        existing_username = User.query.filter_by(
            username=username
        ).first()

        if existing_email:

            flash('Email already registered')

            return redirect(url_for('register'))

        if existing_username:

            flash('Username already taken')

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

    posts = Post.query.order_by(Post.id.desc()).all()

    return render_template(
        'dashboard.html',
        posts=posts,
        user=current_user.username
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
    ).order_by(Diary.date.desc()).all()

    return render_template(
        'diary.html',
        entries=entries,
        user=current_user.username
    )

# ==========================================
# CHAT ROOM
# ==========================================

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():

    if request.method == 'POST':

        if 'reply_to' in request.form and request.form.get('reply_message'):
            reply_to = request.form['reply_to']
            reply_text = request.form['reply_message']
            original = Chat.query.get(int(reply_to))

            if original:
                reply_sender = 'Admin' if current_user.username.lower() == 'admin' else current_user.username
                new_message = Chat(
                    message=f"Reply to {original.sender}: {reply_text}",
                    sender=reply_sender,
                    user_id=original.user_id,
                    recipient=original.sender,
                    reply_to=original.id
                )
            else:
                flash('Original message not found.')
                return redirect(url_for('chat'))
        else:
            message = request.form['message']
            new_message = Chat(
                message=message,
                sender=current_user.username,
                user_id=current_user.id,
                recipient='Admin'
            )

        db.session.add(new_message)

        db.session.commit()

    if current_user.username.lower() == 'admin':
        messages = Chat.query.order_by(Chat.id.asc()).all()
    else:
        messages = Chat.query.filter_by(
            user_id=current_user.id
        ).order_by(Chat.id.asc()).all()

    return render_template(
        'chat.html',
        messages=messages,
        user=current_user.username
    )

# ==========================================
# DATABASE VIEW

@app.route('/database')
@login_required
def database_view():
    if current_user.username.lower() != 'admin':
        flash('Database view is admin only.')
        return redirect(url_for('dashboard'))

    users = User.query.all()
    posts = Post.query.order_by(Post.id.desc()).all()
    diary_entries = Diary.query.order_by(Diary.date.desc()).all()
    chats = Chat.query.order_by(Chat.id.desc()).all()

    return render_template(
        'database.html',
        users=users,
        posts=posts,
        diary_entries=diary_entries,
        chats=chats,
        user=current_user.username
    )

# ==========================================
# CREATE DATABASE
# ==========================================

if __name__ == '__main__':

    with app.app_context():

        db.create_all()

    app.run(debug=True)
    
