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
from flask import session

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
import random
import smtplib
import ssl
from email.message import EmailMessage


def load_env_file(path='.env'):
    if not os.path.exists(path):
        return

    with open(path, encoding='utf-8') as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue

            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ[key] = value


load_env_file()

# ==========================================
# FLASK CONFIGURATION
# ==========================================

app = Flask(__name__, instance_relative_config=True)

app.config['SECRET_KEY'] = 'soulspeaksecret'

# Mail settings can be supplied via environment variables for real email delivery
app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.environ.get('MAIL_PORT', 587))
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD')

# Developer helper: show OTP on the verification page when enabled (for testing only)
app.config['SHOW_OTP'] = os.environ.get('SHOW_OTP', '0').strip().lower() in ('1', 'true', 'yes')


def send_email(to_addr, subject, body):
    mail_server = (app.config.get('MAIL_SERVER') or '').strip()
    mail_port = app.config.get('MAIL_PORT', 587)
    mail_user = (app.config.get('MAIL_USERNAME') or '').strip()
    mail_pass = (app.config.get('MAIL_PASSWORD') or '').replace(' ', '').strip()

    # Log OTP to instance/otp.log for debugging/audit
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        log_path = os.path.join(app.instance_path, 'otp.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.utcnow().isoformat()} {to_addr} {subject} {body}\n")
    except Exception:
        pass

    if not (mail_server and mail_user and mail_pass):
        print(f"OTP for {to_addr}: {body}")
        return False

    if mail_server == 'smtp.gmail.com' and len(mail_pass) != 16:
        print('Failed to send email: Gmail App Password must be 16 characters')
        return False

    # Build the email message
    msg = EmailMessage()
    # Plain text
    msg.set_content(body)
    # HTML alternative for better inbox rendering
    html_body = f"""
    <html>
      <body>
        <h2>SOULSPEAK</h2>
        <p>{body}</p>
        <p>If you did not request this, please ignore.</p>
      </body>
    </html>
    """
    msg.add_alternative(html_body, subtype='html')
    # Friendly headers
    msg['Subject'] = subject
    try:
        display_from = f"SOULSPEAK <{mail_user}>"
    except Exception:
        display_from = mail_user
    msg['From'] = display_from
    msg['To'] = to_addr
    msg['Reply-To'] = mail_user
    context = ssl.create_default_context()
    try:
        # Choose SSL or STARTTLS based on port
        if mail_port == 465:
            with smtplib.SMTP_SSL(mail_server, mail_port, context=context) as server:
                server.ehlo()
                server.login(mail_user, mail_pass)
                server.send_message(msg)
        else:
            with smtplib.SMTP(mail_server, mail_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                server.login(mail_user, mail_pass)
                server.send_message(msg)
        # Log success
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.utcnow().isoformat()} SENT {to_addr} {subject}\n")
        except Exception:
            pass
        return True
    except Exception as e:
        print('Failed to send email:', e)
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.utcnow().isoformat()} FAILED {to_addr} {subject} {e}\n")
        except Exception:
            pass
        return False


def mail_setup_message():
    mail_server = (app.config.get('MAIL_SERVER') or '').strip()
    mail_user = (app.config.get('MAIL_USERNAME') or '').strip()
    mail_pass = (app.config.get('MAIL_PASSWORD') or '').replace(' ', '').strip()

    if not (mail_server and mail_user and mail_pass):
        return 'OTP email could not be sent. Fill MAIL_SERVER, MAIL_USERNAME, and MAIL_PASSWORD in .env.'

    if mail_server == 'smtp.gmail.com' and len(mail_pass) != 16:
        return 'OTP email could not be sent. Gmail needs a 16-character App Password, not your normal Gmail password.'

    return 'OTP email could not be sent. Check your MAIL settings or enable SHOW_OTP=1 for local testing.'

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

        email = request.form['email'].strip().lower()

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

        # Create a pending registration and send OTP to email
        question = request.form.get('security_question')
        answer = request.form.get('security_answer')

        pending = {
            'username': username,
            'email': email,
            'password': password,
            'security_question': question,
            'security_answer': answer,
        }

        otp = f"{random.randint(100000, 999999)}"
        pending['otp'] = otp
        pending['otp_ts'] = datetime.utcnow().timestamp()

        session['pending_registration'] = pending

        email_sent = send_email(email, 'Your registration OTP', f'Your OTP is: {otp}')
        if not email_sent:
            flash(mail_setup_message())

        show_otp = app.config.get('SHOW_OTP', False)
        otp_val = otp if show_otp else None
        return render_template('otp_verify.html', email=email, otp=otp_val, show_otp=show_otp)

    return render_template('register.html')


@app.route('/register_with_security', methods=['POST'])
def register_with_security():
    ensure_user_columns()

    username = request.form.get('username')
    email = request.form.get('email', '').strip().lower()
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


@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    data = session.get('pending_registration')
    if not data:
        flash('No pending registration found')
        return redirect(url_for('register'))

    entered = request.form.get('otp')
    if not entered:
        flash('Please enter the OTP')
        return redirect(url_for('register'))

    ts = data.get('otp_ts', 0)
    if datetime.utcnow().timestamp() - ts > 15 * 60:
        session.pop('pending_registration', None)
        flash('OTP expired')
        return redirect(url_for('register'))

    if entered.strip() != data.get('otp'):
        flash('Invalid OTP')
        show_otp = app.config.get('SHOW_OTP', False)
        otp_val = data.get('otp') if show_otp else None
        return render_template('otp_verify.html', email=data.get('email'), otp=otp_val, show_otp=show_otp)

    new_user = User(
        username=data['username'],
        email=data['email'],
        password=data['password']
    )

    db.session.add(new_user)
    db.session.commit()

    question = data.get('security_question')
    answer = data.get('security_answer')
    if question and answer:
        try:
            ensure_user_columns()
            db.session.execute(
                text('UPDATE user SET security_question=:q, security_answer=:a WHERE id=:id'),
                {'q': question, 'a': answer, 'id': new_user.id}
            )
            db.session.commit()
        except Exception:
            pass

    session.pop('pending_registration', None)
    flash('Registration verified and complete. Please log in.')
    return redirect(url_for('login'))


@app.route('/resend_otp', methods=['POST'])
def resend_otp():
    data = session.get('pending_registration')
    if not data:
        flash('No pending registration to resend OTP for')
        return redirect(url_for('register'))

    # generate new OTP and update timestamp
    otp = f"{random.randint(100000, 999999)}"
    data['otp'] = otp
    data['otp_ts'] = datetime.utcnow().timestamp()
    session['pending_registration'] = data

    email_sent = send_email(data['email'], 'Your registration OTP (resend)', f'Your OTP is: {otp}')

    if email_sent:
        flash('OTP resent')
    else:
        flash(mail_setup_message())
    show_otp = app.config.get('SHOW_OTP', False)
    otp_val = otp if show_otp else None
    return render_template('otp_verify.html', email=data.get('email'), otp=otp_val, show_otp=show_otp)


@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'GET':
        return render_template('forgot.html')

    email = request.form.get('email', '').strip().lower()
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

    # This POST verifies the security answer and, if correct,
    # stores the email in session and redirects to a separate
    # new-password page so the user can set a new password.
    email = request.form.get('email', '').strip().lower()
    answer = request.form.get('security_answer')

    if not (email and answer):
        flash('Email and answer are required')
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

    session['password_reset_email'] = email
    return redirect(url_for('set_new_password'))


@app.route('/set_new_password', methods=['GET', 'POST'])
def set_new_password():
    email = session.get('password_reset_email')
    if not email:
        flash('No password reset in progress')
        return redirect(url_for('forgot'))

    if request.method == 'GET':
        return render_template('reset_password.html', email=email)

    new_password = request.form.get('new_password')
    if not new_password:
        flash('Please provide a new password')
        return redirect(url_for('set_new_password'))

    db.session.execute(
        text('UPDATE user SET password=:pw WHERE email=:email'),
        {'pw': new_password, 'email': email}
    )
    db.session.commit()
    session.pop('password_reset_email', None)
    flash('Password updated. You may now log in with your new password.')
    return redirect(url_for('login'))


# ==========================================
# LOGIN
# ==========================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        email = request.form['email'].strip().lower()

        password = request.form['password']

        user = User.query.filter_by(email=email).first()

        if user and user.password == password:

            login_user(user)

            return redirect(url_for('dashboard'))

        if user:
            flash('Wrong password')
        else:
            flash('No account found with that email. Register first and complete OTP verification.')

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
