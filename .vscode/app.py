# =========================================
# SOULSPEAK FULL PROJECT
# app.py
# =========================================

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
from werkzeug.utils import secure_filename
import uuid

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

UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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

    image_path = db.Column(
        db.String(255),
        nullable=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=True
    )

    user = db.relationship(
        'User',
        backref='posts'
    )

    votes = db.relationship(
        'PostVote',
        backref='post',
        cascade='all, delete-orphan'
    )

    comments = db.relationship(
        'PostComment',
        backref='post',
        cascade='all, delete-orphan'
    )


class PostVote(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    value = db.Column(
        db.Integer,
        nullable=False
    )

    post_id = db.Column(
        db.Integer,
        db.ForeignKey('post.id'),
        nullable=False
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', name='uq_post_vote_post_user'),
    )


class PostComment(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    content = db.Column(
        db.Text,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )

    post_id = db.Column(
        db.Integer,
        db.ForeignKey('post.id'),
        nullable=False
    )

    user = db.relationship('User', backref='comments')


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

        if inspector.has_table('post'):
            result = db.session.execute(text("PRAGMA table_info(post)"))
            columns = [row[1] for row in result]
            if 'image_path' not in columns:
                db.session.execute(text("ALTER TABLE post ADD COLUMN image_path VARCHAR(255)"))
            db.session.commit()

init_db()


def ensure_user_columns():
    with app.app_context():
        inspector = db.session.execute(text("PRAGMA table_info('user')"))
        cols = [row[1] for row in inspector]
        if 'security_question' not in cols:
            db.session.execute(text("ALTER TABLE user ADD COLUMN security_question VARCHAR(255)"))
        if 'security_answer' not in cols:
            db.session.execute(text("ALTER TABLE user ADD COLUMN security_answer VARCHAR(255)"))
        db.session.commit()

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

        # If security question/answer were provided (from the register template),
        # ensure the columns exist and save them directly into the user row.
        question = request.form.get('security_question')
        answer = request.form.get('security_answer')
        if question and answer:
            try:
                ensure_user_columns()

                db.session.execute(
                    text('UPDATE user SET security_question=:q, security_answer=:a WHERE id=:id'),
                    {'q': question, 'a': answer, 'id': new_user.id}
                )
                db.session.commit()
            except Exception:
                # best-effort: if this fails we still consider registration successful
                pass

        flash('Registration Successful')

        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/register_with_security', methods=['POST'])
def register_with_security():
    ensure_user_columns()

    username = request.form.get('username')
    email = request.form.get('email')
    password = request.form.get('password')
    question = request.form.get('security_question')
    answer = request.form.get('security_answer')

    if not (username and email and password and question and answer):
        flash('All fields are required')
        return redirect(url_for('register'))

    existing = db.session.execute(
        text('SELECT id FROM user WHERE email=:email OR username=:username'),
        {'email': email, 'username': username}
    ).fetchone()
    if existing:
        flash('User with that email or username already exists')
        return redirect(url_for('register'))

    db.session.execute(
        text('INSERT INTO user (username, email, password, security_question, security_answer) VALUES (:username, :email, :password, :question, :answer)'),
        {'username': username, 'email': email, 'password': password, 'question': question, 'answer': answer}
    )
    db.session.commit()

    flash('Registration complete. Please log in.')
    return redirect(url_for('login'))


@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'GET':
        return render_template('forgot.html')

    email = request.form.get('email')
    if not email:
        flash('Please provide your email')
        return redirect(url_for('forgot'))

    ensure_user_columns()
    row = db.session.execute(
        text('SELECT security_question FROM user WHERE email=:email'),
        {'email': email}
    ).fetchone()
    if not row or not row[0]:
        flash('No user found with that email or no security question set')
        return redirect(url_for('forgot'))

    question = row[0]
    return render_template('forgot_question.html', email=email, question=question)


@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'GET':
        flash('Please use the Forgot Password form to reset your password')
        return redirect(url_for('forgot'))

    email = request.form.get('email')
    answer = request.form.get('security_answer')
    new_password = request.form.get('new_password')

    if not (email and answer and new_password):
        flash('All fields are required')
        return redirect(url_for('forgot'))

    ensure_user_columns()
    row = db.session.execute(
        text('SELECT security_answer FROM user WHERE email=:email'),
        {'email': email}
    ).fetchone()
    if not row:
        flash('User not found')
        return redirect(url_for('forgot'))

    stored_answer = row[0]
    if stored_answer is None:
        flash('No security answer set for this account')
        return redirect(url_for('forgot'))

    if stored_answer.strip().lower() != answer.strip().lower():
        flash('Security answer did not match')
        return redirect(url_for('forgot'))

    db.session.execute(
        text('UPDATE user SET password=:pw WHERE email=:email'),
        {'pw': new_password, 'email': email}
    )
    db.session.commit()

    flash('Password updated. You may now log in with your new password.')
    return redirect(url_for('login'))


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
# CREATE POST
# ==========================================

@app.route('/post', methods=['GET', 'POST'])
def post():

    if request.method == 'POST':

        content = request.form['content']
        image = request.files.get('image')
        image_path = None
        user_id = current_user.id if current_user.is_authenticated else None

        if image and image.filename:
            if allowed_file(image.filename):
                filename = secure_filename(image.filename)
                unique_filename = f"{uuid.uuid4().hex}_{filename}"
                full_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
                image.save(full_path)
                image_path = f"uploads/{unique_filename}"
            else:
                flash('Only PNG, JPG, JPEG and GIF files are allowed')
                return redirect(url_for('post'))

        new_post = Post(
            content=content,
            image_path=image_path,
            user_id=user_id
        )

        db.session.add(new_post)
        db.session.commit()

        flash('Post created')

        return redirect(url_for('dashboard'))

    user_display = current_user.username if current_user.is_authenticated else 'Anonymous'
    return render_template(
        'post.html',
        user=user_display
    )


@app.route('/post/<int:post_id>/react', methods=['POST'])
def react_to_post(post_id):
    if not current_user.is_authenticated:
        flash('Please log in to react to posts')
        return redirect(url_for('login'))

    action = request.form.get('action')

    if action not in ('like', 'dislike'):

        flash('Invalid reaction')

        return redirect(url_for('dashboard'))

    post = Post.query.get_or_404(post_id)

    existing_vote = PostVote.query.filter_by(
        post_id=post.id,
        user_id=current_user.id
    ).first()

    vote_value = 1 if action == 'like' else -1

    if existing_vote and existing_vote.value == vote_value:

        db.session.delete(existing_vote)

    elif existing_vote:

        existing_vote.value = vote_value

    else:

        db.session.add(
            PostVote(
                post_id=post.id,
                user_id=current_user.id,
                value=vote_value
            )
        )

    db.session.commit()

    return redirect(url_for('dashboard'))


@app.route('/post/<int:post_id>/comment', methods=['POST'])
def comment(post_id):
    if not current_user.is_authenticated:
        flash('Please log in to comment')
        return redirect(url_for('login'))
    content = request.form.get('comment_content')
    if not content:
        flash('Comment cannot be empty')
        return redirect(url_for('dashboard'))

    post = Post.query.get_or_404(post_id)
    comment = PostComment(
        content=content,
        user_id=current_user.id,
        post_id=post.id
    )
    db.session.add(comment)
    db.session.commit()

    return redirect(url_for('dashboard'))

# ==========================================
# DASHBOARD
# ==========================================

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():

    posts = Post.query.order_by(Post.id.desc()).all()

    user_votes = {}
    if current_user.is_authenticated:
        user_votes = {
            vote.post_id: vote.value
            for vote in PostVote.query.filter_by(
                user_id=current_user.id
            ).all()
        }

    post_data = []

    for post in posts:

        likes = sum(1 for vote in post.votes if vote.value == 1)

        dislikes = sum(1 for vote in post.votes if vote.value == -1)

        post_data.append(
            {
                'post': post,
                'likes': likes,
                'dislikes': dislikes,
                'user_vote': user_votes.get(post.id),
                'comments': sorted(post.comments, key=lambda c: c.created_at)
            }
        )

    user_display = current_user.username if current_user.is_authenticated else 'Guest'
    return render_template(
        'dashboard.html',
        posts=post_data,
        user=user_display
    )

# ==========================================
# MENU
# ==========================================

@app.route('/menu', methods=['GET'])
def menu():
    user_display = current_user.username if current_user.is_authenticated else 'Guest'
    return render_template('menu.html', user=user_display)

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

    # Fetch messages visible to this user
    if current_user.username.lower() == 'admin':
        all_messages = Chat.query.order_by(Chat.id.asc()).all()
    else:
        all_messages = Chat.query.filter_by(
            user_id=current_user.id
        ).order_by(Chat.id.asc()).all()

    # Build threaded view: top-level messages (reply_to is None) and replies map
    originals = [m for m in all_messages if not m.reply_to]
    replies_map = {}
    for m in all_messages:
        if m.reply_to:
            replies_map.setdefault(m.reply_to, []).append(m)

    return render_template(
        'chat.html',
        originals=originals,
        replies_map=replies_map,
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
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(debug=True)
