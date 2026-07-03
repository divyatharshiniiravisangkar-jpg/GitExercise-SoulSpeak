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
from flask import jsonify
from flask import send_from_directory
from flask import abort

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

from datetime import datetime, timedelta
import base64
import json
import random
import smtplib
import ssl
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

try:
    import cloudinary
    import cloudinary.uploader
except ImportError:
    cloudinary = None

REACTION_MAP = {
    'love': 6,
    'like': 1,
    'dislike': -1,
    'sad': 2,
    'angry': 3,
    'funny': 4,
}

REACTION_LABELS = {
    'love': 'Like / Love',
    'like': 'Happy',
    'funny': 'Laugh',
    'dislike': 'Dislike',
    'angry': 'Angry',
    'sad': 'Sad',
}

REACTION_EMOJIS = {
    'love': 'heart',
    'like': 'smile',
    'funny': 'laugh',
    'dislike': 'thumbs down',
    'angry': 'angry',
    'sad': 'sad',
}

REACTION_SENTIMENT_SCORES = {
    'love': 0.74,
    'like': 0.65,
    'funny': 0.80,
    'dislike': -0.60,
    'angry': -0.85,
    'sad': -0.65,
}

SENTIMENT_SCALE = [
    {'label': '+1.00', 'meaning': 'Extremely Positive'},
    {'label': '+0.50 to +0.99', 'meaning': 'Positive'},
    {'label': '0.00', 'meaning': 'Neutral'},
    {'label': '-0.50 to -0.99', 'meaning': 'Negative'},
    {'label': '-1.00', 'meaning': 'Extremely Negative'},
]

REACTION_SCORE_LOOKUP = {
    action: {
        'emoji': REACTION_EMOJIS[action],
        'emotion': REACTION_LABELS[action],
        'score': REACTION_SENTIMENT_SCORES[action],
    }
    for action in ('love', 'like', 'funny', 'dislike', 'angry', 'sad')
}


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


def env_first(*names, default=None):
    for name in names:
        value = os.environ.get(name)
        if value is not None and str(value).strip():
            value = str(value).strip().strip('"').strip("'")
            for env_name in names:
                prefix = env_name + '='
                if value.startswith(prefix):
                    value = value[len(prefix):].strip().strip('"').strip("'")
            return value
    return default


def env_flag(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on')

# ==========================================
# FLASK CONFIGURATION
# ==========================================

app = Flask(__name__, instance_relative_config=True)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'soulspeaksecret')

# Mail settings can be supplied via environment variables for real email delivery.
# Common SMTP aliases are accepted so deploy dashboards do not have to use one exact name.
app.config['MAIL_SERVER'] = env_first('MAIL_SERVER', 'SMTP_SERVER', 'SMTP_HOST', default='smtp.gmail.com')
app.config['MAIL_PORT'] = int(env_first('MAIL_PORT', 'SMTP_PORT', default=587))
app.config['MAIL_USERNAME'] = env_first('MAIL_USERNAME', 'EMAIL_USER', 'EMAIL_USERNAME', 'SMTP_USERNAME')
app.config['MAIL_PASSWORD'] = env_first('MAIL_PASSWORD', 'EMAIL_PASSWORD', 'EMAIL_PASS', 'SMTP_PASSWORD')
app.config['MAIL_TIMEOUT'] = int(os.environ.get('MAIL_TIMEOUT', 8))
app.config['LAST_MAIL_ERROR'] = ''
app.config['OTP_FALLBACK_ON_MAIL_FAILURE'] = env_flag('OTP_FALLBACK_ON_MAIL_FAILURE', False)
app.config['GMAIL_CLIENT_ID'] = env_first('GMAIL_CLIENT_ID', 'GOOGLE_CLIENT_ID')
app.config['GMAIL_CLIENT_SECRET'] = env_first('GMAIL_CLIENT_SECRET', 'GOOGLE_CLIENT_SECRET')
app.config['GMAIL_REFRESH_TOKEN'] = env_first('GMAIL_REFRESH_TOKEN', 'GOOGLE_REFRESH_TOKEN')
app.config['ADMIN_EMAILS'] = {
    email.strip().lower()
    for email in os.environ.get('ADMIN_EMAILS', 'logananthan02@gmail.com').split(',')
    if email.strip()
}

# Only show OTP on-screen for local/debug testing. Production should deliver OTP by email.
debug_enabled = env_flag('FLASK_DEBUG')
show_otp_requested = env_flag('SHOW_OTP')
app.config['SHOW_OTP'] = debug_enabled and show_otp_requested


def should_show_otp(email_sent=False):
    if app.config.get('SHOW_OTP', False):
        return True
    return (not email_sent) and app.config.get('OTP_FALLBACK_ON_MAIL_FAILURE', False)


def gmail_api_configured():
    return all((
        (app.config.get('GMAIL_CLIENT_ID') or '').strip(),
        (app.config.get('GMAIL_CLIENT_SECRET') or '').strip(),
        (app.config.get('GMAIL_REFRESH_TOKEN') or '').strip(),
        (app.config.get('MAIL_USERNAME') or '').strip(),
    ))


def gmail_api_access_token():
    data = urllib.parse.urlencode({
        'client_id': (app.config['GMAIL_CLIENT_ID'] or '').strip(),
        'client_secret': (app.config['GMAIL_CLIENT_SECRET'] or '').strip(),
        'refresh_token': (app.config['GMAIL_REFRESH_TOKEN'] or '').strip(),
        'grant_type': 'refresh_token',
    }).encode('utf-8')
    req = urllib.request.Request(
        'https://oauth2.googleapis.com/token',
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST',
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        payload = json.loads(response.read().decode('utf-8'))

    token = payload.get('access_token')
    if not token:
        raise RuntimeError('Gmail API did not return an access token')
    return token


def send_gmail_api_message(msg):
    token = gmail_api_access_token()
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode('ascii')
    data = json.dumps({'raw': raw}).encode('utf-8')
    req = urllib.request.Request(
        'https://gmail.googleapis.com/gmail/v1/users/me/messages/send',
        data=data,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode('utf-8'))


def is_admin_user(user=None):
    user = user or current_user
    if not getattr(user, 'is_authenticated', False):
        return False

    username = (getattr(user, 'username', '') or '').strip().lower()
    email = (getattr(user, 'email', '') or '').strip().lower()
    return username == 'admin' or email in app.config.get('ADMIN_EMAILS', set())


def can_delete_post(post, user=None):
    user = user or current_user
    if not getattr(user, 'is_authenticated', False):
        return False

    return is_admin_user(user) or post.user_id == user.id


def can_delete_diary(entry, user=None):
    user = user or current_user
    if not getattr(user, 'is_authenticated', False):
        return False

    return entry.user_id == user.id


def can_delete_chat(message, user=None):
    user = user or current_user
    if not getattr(user, 'is_authenticated', False):
        return False

    if is_admin_user(user):
        return True

    sender = (message.sender or '').strip().lower()
    username = (user.username or '').strip().lower()
    return message.user_id == user.id and sender == username


@app.context_processor
def inject_admin_status():
    return {'is_admin': is_admin_user()}


@app.template_filter('malaysia_time')
def malaysia_time(value, fmt='%I:%M %p'):
    if not value:
        return ''

    return (value + timedelta(hours=8)).strftime(fmt)


def send_email(to_addr, subject, body):
    app.config['LAST_MAIL_ERROR'] = ''
    mail_server = (app.config.get('MAIL_SERVER') or '').strip()
    mail_port = app.config.get('MAIL_PORT', 587)
    mail_user = (app.config.get('MAIL_USERNAME') or '').strip()
    mail_pass = (app.config.get('MAIL_PASSWORD') or '').replace(' ', '').strip()
    mail_timeout = app.config.get('MAIL_TIMEOUT', 8)
    use_gmail_api = gmail_api_configured()

    # Log OTP to instance/otp.log for debugging/audit
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        log_path = os.path.join(app.instance_path, 'otp.log')
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"{datetime.utcnow().isoformat()} {to_addr} {subject} {body}\n")
    except Exception:
        pass

    if not mail_user:
        missing = []
        missing.append('MAIL_USERNAME')
        app.config['LAST_MAIL_ERROR'] = 'Missing environment variables: ' + ', '.join(missing)
        print(f"OTP for {to_addr}: {body}")
        return False

    if not use_gmail_api and not (mail_server and mail_pass):
        missing = []
        if not mail_server:
            missing.append('MAIL_SERVER')
        if not mail_pass:
            missing.append('MAIL_PASSWORD')
        app.config['LAST_MAIL_ERROR'] = 'Missing environment variables: ' + ', '.join(missing)
        print(f"OTP for {to_addr}: {body}")
        return False

    if not use_gmail_api and mail_server == 'smtp.gmail.com' and len(mail_pass) != 16:
        app.config['LAST_MAIL_ERROR'] = 'Gmail App Password must be 16 characters'
        print('Failed to send email:', app.config['LAST_MAIL_ERROR'])
        return False

    msg = EmailMessage()
    msg.set_content(body)

    html_body = f"""
    <!doctype html>
    <html lang="en">
        <body style="margin:0;padding:24px;background:#f6f8fb;font-family:Arial,sans-serif;color:#1f2937;">
            <div style="max-width:520px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;border-radius:14px;padding:24px;">
                <p style="margin:0 0 10px;color:#2563eb;font-size:12px;font-weight:700;letter-spacing:1.6px;">SOULSPEAK</p>
                <h2 style="margin:0 0 12px;font-size:22px;color:#111827;">Your verification code</h2>
                <p style="margin:0 0 16px;font-size:15px;line-height:1.6;">Use this code to complete your SoulSpeak registration:</p>
                <div style="font-size:32px;font-weight:700;letter-spacing:8px;color:#111827;background:#f3f4f6;border-radius:12px;padding:16px;text-align:center;">{body.replace('Your OTP is:', '').strip()}</div>
                <p style="margin:18px 0 0;font-size:13px;line-height:1.6;color:#6b7280;">This code expires in 15 minutes. If you did not request it, you can ignore this email.</p>
            </div>
        </body>
    </html>
    """
    msg.add_alternative(html_body, subtype='html')
    msg['Subject'] = subject
    msg['From'] = f"SoulSpeak <{mail_user}>"
    msg['To'] = to_addr
    msg['Reply-To'] = mail_user
    context = ssl.create_default_context()

    if use_gmail_api:
        try:
            send_gmail_api_message(msg)
            try:
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.utcnow().isoformat()} SENT_GMAIL_API {to_addr} {subject}\n")
            except Exception:
                pass
            return True
        except Exception as e:
            api_error = str(e)
            if isinstance(e, urllib.error.HTTPError):
                try:
                    api_error = e.read().decode('utf-8')
                except Exception:
                    api_error = str(e)
            print('Failed Gmail API send:', api_error)
            try:
                with open(log_path, 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.utcnow().isoformat()} FAILED_GMAIL_API {to_addr} {subject} {api_error}\n")
            except Exception:
                pass
            if not mail_pass:
                if 'invalid_client' in api_error:
                    app.config['LAST_MAIL_ERROR'] = (
                        'Gmail API client is invalid. Check GMAIL_CLIENT_ID and '
                        'GMAIL_CLIENT_SECRET in your hosting environment variables.'
                    )
                    return False
                if 'unauthorized_client' in api_error:
                    app.config['LAST_MAIL_ERROR'] = (
                        'Gmail API refresh token is not authorized for this client. '
                        'Regenerate GMAIL_REFRESH_TOKEN using the same Web application '
                        'GMAIL_CLIENT_ID and GMAIL_CLIENT_SECRET from your hosting environment.'
                    )
                    return False
                app.config['LAST_MAIL_ERROR'] = 'Gmail API failed: ' + api_error
                return False

    smtp_attempts = [(mail_server, mail_port)]
    if mail_server == 'smtp.gmail.com':
        alternate_gmail_port = 465 if mail_port != 465 else 587
        smtp_attempts.append((mail_server, alternate_gmail_port))

    try:
        last_error = None
        for smtp_server, smtp_port in smtp_attempts:
            try:
                # Choose SSL or STARTTLS based on port.
                if smtp_port == 465:
                    with smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=mail_timeout, context=context) as server:
                        server.ehlo()
                        server.login(mail_user, mail_pass)
                        server.send_message(msg)
                else:
                    with smtplib.SMTP(smtp_server, smtp_port, timeout=mail_timeout) as server:
                        server.ehlo()
                        server.starttls(context=context)
                        server.ehlo()
                        server.login(mail_user, mail_pass)
                        server.send_message(msg)
                last_error = None
                break
            except Exception as e:
                last_error = e
                print(f'Failed SMTP attempt via {smtp_server}:{smtp_port}:', e)

        if last_error:
            raise last_error

        # Log success
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.utcnow().isoformat()} SENT {to_addr} {subject}\n")
        except Exception:
            pass
        return True
    except Exception as e:
        app.config['LAST_MAIL_ERROR'] = str(e)
        print('Failed to send email:', e)
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(f"{datetime.utcnow().isoformat()} FAILED {to_addr} {subject} {e}\n")
        except Exception:
            pass
        return False


def mail_setup_message():
    last_error = (app.config.get('LAST_MAIL_ERROR') or '').strip()
    if last_error:
        return 'OTP email could not be sent: ' + last_error + '.'

    mail_server = (app.config.get('MAIL_SERVER') or '').strip()
    mail_user = (app.config.get('MAIL_USERNAME') or '').strip()
    mail_pass = (app.config.get('MAIL_PASSWORD') or '').replace(' ', '').strip()
    use_gmail_api = gmail_api_configured()

    missing = []
    if not mail_user:
        missing.append('MAIL_USERNAME')
    if not use_gmail_api and not mail_server:
        missing.append('MAIL_SERVER')
    if not use_gmail_api and not mail_pass:
        missing.append('MAIL_PASSWORD')

    if missing:
        return 'OTP email could not be sent. Missing environment variables: ' + ', '.join(missing) + '.'

    if not use_gmail_api and mail_server == 'smtp.gmail.com' and len(mail_pass) != 16:
        return 'OTP email could not be sent. Gmail needs a 16-character App Password, not your normal Gmail password.'

    return 'OTP email could not be sent. Check your MAIL environment variables.'


def database_uri_from_env():
    database_url = env_first('DATABASE_URL', 'POSTGRES_URL', 'POSTGRESQL_URL')
    if database_url:
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        return database_url, False

    persistent_path = env_first('RENDER_DISK_PATH', 'PERSISTENT_STORAGE_PATH', 'DATA_DIR')
    if persistent_path:
        os.makedirs(persistent_path, exist_ok=True)
        return f"sqlite:///{os.path.join(persistent_path, 'database.db')}", False

    os.makedirs(app.instance_path, exist_ok=True)
    return f"sqlite:///{os.path.join(app.instance_path, 'database.db')}", True


def persistent_storage_path():
    return env_first('RENDER_DISK_PATH', 'PERSISTENT_STORAGE_PATH', 'DATA_DIR')


def table_columns(table_name):
    inspector = inspect(db.engine)
    if not inspector.has_table(table_name):
        return set()
    return {column['name'] for column in inspector.get_columns(table_name)}


def sql_table_name(table_name):
    if db.engine.dialect.name == 'sqlite':
        return table_name
    return f'"{table_name}"'


def sql_datetime_type():
    if db.engine.dialect.name == 'sqlite':
        return 'DATETIME'
    return 'TIMESTAMP'


database_uri, using_ephemeral_sqlite = database_uri_from_env()
app.config['USING_EPHEMERAL_SQLITE'] = using_ephemeral_sqlite
if using_ephemeral_sqlite:
    print(
        'WARNING: DATABASE_URL is not set. Published data may disappear when '
        'the hosting service restarts or redeploys. Use a persistent PostgreSQL '
        'DATABASE_URL for production.'
    )

database_url = database_uri
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

storage_path = persistent_storage_path()
if storage_path:
    UPLOAD_FOLDER = os.path.join(storage_path, 'uploads')
else:
    UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def cloudinary_configured():
    if cloudinary is None:
        return False

    cloudinary_url = env_first('CLOUDINARY_URL')
    cloud_name = env_first('CLOUDINARY_CLOUD_NAME')
    api_key = env_first('CLOUDINARY_API_KEY')
    api_secret = env_first('CLOUDINARY_API_SECRET')

    if cloudinary_url:
        cloudinary.config(secure=True)
        return True

    if cloud_name and api_key and api_secret:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        return True

    return False


def cloudinary_image_parts(image_path):
    if not image_path or not image_path.startswith('cloudinary:'):
        return '', ''

    value = image_path.split(':', 1)[1]
    if '|' not in value:
        return '', value

    public_id, image_url = value.split('|', 1)
    return public_id, image_url


def cloudinary_upload_image(image, image_id):
    if not cloudinary_configured():
        return None

    image.stream.seek(0)
    result = cloudinary.uploader.upload(
        image.stream,
        folder='soulspeak_posts',
        public_id=image_id,
        resource_type='image',
        overwrite=False
    )
    saved_public_id = result.get('public_id') or f'soulspeak_posts/{image_id}'
    secure_url = result.get('secure_url') or result.get('url')
    if not secure_url:
        raise RuntimeError('Cloudinary did not return an image URL.')
    return f"cloudinary:{saved_public_id}|{secure_url}"


def save_post_image(image):
    image_id = uuid.uuid4().hex

    try:
        cloudinary_path = cloudinary_upload_image(image, image_id)
        if cloudinary_path:
            return cloudinary_path, None
    except Exception:
        pass

    mimetype = image.mimetype or 'image/jpeg'
    image.stream.seek(0)
    encoded_image = base64.b64encode(image.read()).decode('ascii')
    return f"database:{image_id}", f"data:{mimetype};base64,{encoded_image}"


def post_image_values(image_source):
    if hasattr(image_source, 'image_path'):
        return image_source.image_path, getattr(image_source, 'image_data', None)

    return image_source, None


def delete_post_image_file(image_path):
    if not image_path:
        return

    public_id, _ = cloudinary_image_parts(image_path)
    if public_id and cloudinary_configured():
        cloudinary.uploader.destroy(public_id, resource_type='image')
        return

    upload_filename = upload_filename_from_path(image_path)
    if upload_filename:
        candidate_paths = [
            os.path.join(folder, upload_filename)
            for folder in upload_search_folders()
        ]
    else:
        candidate_paths = [
            os.path.join(app.static_folder, image_path.replace('/', os.sep))
        ]

    for full_path in candidate_paths:
        if os.path.isfile(full_path):
            os.remove(full_path)
            return


@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    for folder in upload_search_folders():
        if os.path.isfile(os.path.join(folder, filename)):
            return send_from_directory(folder, filename)

    abort(404)


def upload_search_folders():
    folders = [app.config['UPLOAD_FOLDER']]
    static_uploads = os.path.join(app.static_folder, 'uploads')
    if static_uploads not in folders:
        folders.append(static_uploads)
    return folders


def upload_filename_from_path(image_path):
    if not image_path:
        return ''

    normalized_path = image_path.replace('\\', '/')
    if normalized_path.startswith('uploads/'):
        return normalized_path.split('/', 1)[1]
    if normalized_path.startswith('static/uploads/'):
        return normalized_path.split('/', 2)[2]
    return ''


def post_image_url(image_path):
    image_path, image_data = post_image_values(image_path)
    if image_path and image_path.startswith('database:'):
        return image_data or ''

    _, cloudinary_url = cloudinary_image_parts(image_path)
    if cloudinary_url:
        return cloudinary_url

    upload_filename = upload_filename_from_path(image_path)
    if upload_filename:
        return url_for('uploaded_file', filename=upload_filename)
    if image_path:
        return url_for('static', filename=image_path)
    return ''


def post_image_exists(image_path):
    image_path, image_data = post_image_values(image_path)
    if image_path and image_path.startswith('database:'):
        return bool(image_data)

    _, cloudinary_url = cloudinary_image_parts(image_path)
    if cloudinary_url:
        return True

    upload_filename = upload_filename_from_path(image_path)
    if upload_filename:
        return any(
            os.path.isfile(os.path.join(folder, upload_filename))
            for folder in upload_search_folders()
        )

    if image_path:
        return os.path.isfile(os.path.join(app.static_folder, image_path.replace('/', os.sep)))

    return False


@app.context_processor
def inject_upload_helpers():
    return {
        'post_image_url': post_image_url,
        'post_image_exists': post_image_exists
    }


def sentiment_label_for_score(score):
    if score >= 0.50:
        return 'Positive'
    if score <= -0.50:
        return 'Negative'
    return 'Neutral'


def reaction_counts_for_post(post):
    votes = PostVote.query.filter_by(post_id=post.id).all() if post.id else post.votes
    return {
        action: sum(1 for vote in votes if vote.value == value)
        for action, value in REACTION_MAP.items()
    }


def calculate_post_sentiment(post):
    reaction_counts = reaction_counts_for_post(post)
    total_reactions = sum(reaction_counts.values())

    if total_reactions == 0:
        return reaction_counts, 0.0, 'Neutral'

    weighted_score = sum(
        reaction_counts[action] * REACTION_SENTIMENT_SCORES[action]
        for action in REACTION_MAP
    )
    score = round(weighted_score / total_reactions, 2)

    return reaction_counts, score, sentiment_label_for_score(score)


def update_post_sentiment(post):
    reaction_counts, score, label = calculate_post_sentiment(post)
    post.sentiment_score = score
    post.sentiment_label = label
    return reaction_counts, score, label

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

    image_data = db.Column(
        db.Text,
        nullable=True
    )

    sentiment_score = db.Column(
        db.Float,
        nullable=False,
        default=0.0
    )

    sentiment_label = db.Column(
        db.String(30),
        nullable=False,
        default='Neutral'
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
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

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    user = db.relationship('User', backref='chats')


def init_db():
    with app.app_context():
        db.create_all()
        inspector = inspect(db.engine)
        if inspector.has_table('chat'):
            columns = table_columns('chat')
            if 'user_id' not in columns:
                db.session.execute(text(f'ALTER TABLE {sql_table_name("chat")} ADD COLUMN user_id INTEGER'))
            if 'recipient' not in columns:
                db.session.execute(text(f"ALTER TABLE {sql_table_name('chat')} ADD COLUMN recipient VARCHAR(100) NOT NULL DEFAULT 'Admin'"))
            if 'reply_to' not in columns:
                db.session.execute(text(f'ALTER TABLE {sql_table_name("chat")} ADD COLUMN reply_to INTEGER'))
            if 'created_at' not in columns:
                db.session.execute(text(f'ALTER TABLE {sql_table_name("chat")} ADD COLUMN created_at {sql_datetime_type()}'))
            db.session.commit()

        if inspector.has_table('post'):
            columns = table_columns('post')
            if 'image_path' not in columns:
                db.session.execute(text(f"ALTER TABLE {sql_table_name('post')} ADD COLUMN image_path VARCHAR(255)"))
            if 'image_data' not in columns:
                db.session.execute(text(f"ALTER TABLE {sql_table_name('post')} ADD COLUMN image_data TEXT"))
            if 'sentiment_score' not in columns:
                db.session.execute(text(f"ALTER TABLE {sql_table_name('post')} ADD COLUMN sentiment_score FLOAT NOT NULL DEFAULT 0.0"))
            if 'sentiment_label' not in columns:
                db.session.execute(text(f"ALTER TABLE {sql_table_name('post')} ADD COLUMN sentiment_label VARCHAR(30) NOT NULL DEFAULT 'Neutral'"))
            if 'created_at' not in columns:
                db.session.execute(text(f"ALTER TABLE {sql_table_name('post')} ADD COLUMN created_at {sql_datetime_type()}"))
            db.session.commit()

init_db()


def repair_chat_user_ids():
    users_by_name = {
        (user.username or '').strip().lower(): user
        for user in User.query.all()
    }

    changed = False
    for message in Chat.query.filter(Chat.user_id.is_(None)).all():
        sender_name = (message.sender or '').strip().lower()
        recipient_name = (message.recipient or '').strip().lower()

        matched_user = None
        if sender_name != 'admin':
            matched_user = users_by_name.get(sender_name)
        if not matched_user and recipient_name != 'admin':
            matched_user = users_by_name.get(recipient_name)

        if matched_user:
            message.user_id = matched_user.id
            changed = True

    if changed:
        db.session.commit()


def ensure_user_columns():
    with app.app_context():
        cols = table_columns('user')
        if 'security_question' not in cols:
            db.session.execute(text(f"ALTER TABLE {sql_table_name('user')} ADD COLUMN security_question VARCHAR(255)"))
        if 'security_answer' not in cols:
            db.session.execute(text(f"ALTER TABLE {sql_table_name('user')} ADD COLUMN security_answer VARCHAR(255)"))
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

    if current_user.is_authenticated:
        return redirect(url_for('menu'))

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

        email_sent = send_email(email, 'Your registration OTP', f'Your OTP is: {otp}')
        show_otp = should_show_otp(email_sent)
        pending['show_otp'] = show_otp
        session['pending_registration'] = pending
        if email_sent:
            flash('OTP sent to your email. Please check your inbox or spam folder.')
        elif show_otp:
            flash(mail_setup_message() + ' Use the OTP shown below to finish registration.')
        else:
            flash(mail_setup_message())
            return redirect(url_for('register'))
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
        show_otp = app.config.get('SHOW_OTP', False) or data.get('show_otp', False)
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
    show_otp = should_show_otp(email_sent)
    if email_sent:
        flash('OTP resent to your email. Please check your inbox or spam folder.')
    elif show_otp:
        flash(mail_setup_message() + ' Use the OTP shown below to finish registration.')
    else:
        flash(mail_setup_message())

    data['show_otp'] = show_otp
    session['pending_registration'] = data
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

            return redirect(url_for('menu'))

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

        post_token = request.form.get('post_token')
        valid_tokens = session.get('post_tokens', [])

        if not post_token or post_token not in valid_tokens:
            flash('That post was already submitted.')
            return redirect(url_for('dashboard'))

        valid_tokens.remove(post_token)
        session['post_tokens'] = valid_tokens

        content = request.form['content']
        image = request.files.get('image')
        image_path = None
        image_data = None
        user_id = current_user.id if current_user.is_authenticated else None

        if image and image.filename:
            if allowed_file(image.filename):
                try:
                    image_path, image_data = save_post_image(image)
                except Exception:
                    flash('Image upload failed. Please try again.')
                    return redirect(url_for('post'))
            else:
                flash('Only PNG, JPG, JPEG and GIF files are allowed')
                return redirect(url_for('post'))

        new_post = Post(
            content=content,
            image_path=image_path,
            image_data=image_data,
            user_id=user_id
        )

        db.session.add(new_post)
        db.session.commit()

        flash('Post created')

        return redirect(url_for('dashboard'))

    user_display = current_user.username if current_user.is_authenticated else 'Anonymous'
    post_token = uuid.uuid4().hex
    session.setdefault('post_tokens', [])
    session['post_tokens'].append(post_token)
    session.modified = True

    return render_template(
        'post.html',
        user=user_display,
        post_token=post_token
    )


@app.route('/post/<int:post_id>/react', methods=['POST'])
def react_to_post(post_id):
    if not current_user.is_authenticated:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Please log in to react to posts'}), 401
        flash('Please log in to react to posts')
        return redirect(url_for('login'))

    action = request.form.get('action')

    if action not in REACTION_MAP:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'Invalid reaction'}), 400
        flash('Invalid reaction')
        return redirect(url_for('dashboard'))

    post = Post.query.get_or_404(post_id)

    existing_vote = PostVote.query.filter_by(
        post_id=post.id,
        user_id=current_user.id
    ).first()

    vote_value = REACTION_MAP[action]

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

    db.session.flush()
    reaction_counts, sentiment_score, sentiment = update_post_sentiment(post)
    db.session.commit()

    updated_vote = PostVote.query.filter_by(
        post_id=post.id,
        user_id=current_user.id
    ).first()
    user_reaction = next(
        (reaction for reaction, value in REACTION_MAP.items() if updated_vote and updated_vote.value == value),
        None
    )

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'reaction_counts': reaction_counts,
            'user_reaction': user_reaction,
            'sentiment': sentiment,
            'sentiment_score': sentiment_score
        })

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


@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)

    if not can_delete_post(post):
        flash('You can only delete your own posts.')
        return redirect(url_for('dashboard'))

    image_path = post.image_path
    db.session.delete(post)
    db.session.commit()

    delete_post_image_file(image_path)

    flash('Post deleted')
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
        reaction_counts, sentiment_score, sentiment_label = update_post_sentiment(post)

        user_vote = user_votes.get(post.id)
        user_reaction = next(
            (action for action, value in REACTION_MAP.items() if user_vote == value),
            None
        )

        post_data.append(
            {
                'post': post,
                'reaction_counts': reaction_counts,
                'user_vote': user_vote,
                'user_reaction': user_reaction,
                'sentiment_score': sentiment_score,
                'sentiment_label': sentiment_label,
                'comments': sorted(post.comments, key=lambda c: c.created_at),
                'can_delete': can_delete_post(post)
            }
        )

    db.session.commit()

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
    admin_view = is_admin_user()

    if admin_view:
        diary_users = db.session.query(User).join(
            Diary,
            Diary.user_id == User.id
        ).distinct().order_by(User.username.asc()).all()

        return render_template(
            'diary.html',
            entries=[],
            diary_users=diary_users,
            user=current_user.username,
            is_admin=True
        )

    if request.method == 'POST':

        content = request.form['content']

        entry = Diary(
            content=content,
            user_id=current_user.id
        )

        db.session.add(entry)

        db.session.commit()
        return redirect(url_for('diary'))

    entries = Diary.query.filter_by(
        user_id=current_user.id
    ).order_by(Diary.date.desc()).all()

    return render_template(
        'diary.html',
        entries=entries,
        user=current_user.username,
        is_admin=False
    )


@app.route('/diary/<int:entry_id>/delete', methods=['POST'])
@login_required
def delete_diary(entry_id):
    entry = Diary.query.get_or_404(entry_id)

    if not can_delete_diary(entry):
        flash('You can only delete your own diary entries.')
        return redirect(url_for('diary'))

    db.session.delete(entry)
    db.session.commit()

    flash('Diary entry deleted.')
    return redirect(url_for('diary'))

# ==========================================
# CHAT ROOM
# ==========================================

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    admin_view = is_admin_user()
    repair_chat_user_ids()

    if request.method == 'POST':

        if 'reply_to' in request.form and request.form.get('reply_message'):
            reply_to = request.form['reply_to']
            reply_text = request.form['reply_message']
            original = Chat.query.get(int(reply_to))

            if original:
                if admin_view and not original.user_id:
                    flash('This message is not linked to a user account yet.')
                    return redirect(url_for('chat'))

                if not admin_view and original.user_id != current_user.id:
                    flash('You can only reply in your own chat.')
                    return redirect(url_for('chat'))

                reply_sender = 'Admin' if admin_view else current_user.username
                reply_recipient = original.user.username if admin_view and original.user else original.sender
                new_message = Chat(
                    message=reply_text,
                    sender=reply_sender,
                    user_id=original.user_id,
                    recipient=reply_recipient,
                    reply_to=original.id
                )
            else:
                flash('Original message not found.')
                return redirect(url_for('chat'))
        else:
            message = request.form['message']
            selected_user_id = request.form.get('selected_user_id', type=int)

            if admin_view:
                selected_user = User.query.get(selected_user_id) if selected_user_id else None
                if not selected_user:
                    flash('Choose a user before sending a chat reply.')
                    return redirect(url_for('chat'))

                new_message = Chat(
                    message=message,
                    sender='Admin',
                    user_id=selected_user.id,
                    recipient=selected_user.username
                )
            else:
                new_message = Chat(
                    message=message,
                    sender=current_user.username,
                    user_id=current_user.id,
                    recipient='Admin'
                )

        db.session.add(new_message)

        db.session.commit()
        if admin_view:
            return redirect(url_for('chat', user_id=new_message.user_id))
        return redirect(url_for('chat'))

    # Fetch messages visible to this user
    chat_users = []
    selected_chat_user = None

    if admin_view:
        chat_user_ids = [
            row[0]
            for row in db.session.query(Chat.user_id)
            .filter(Chat.user_id.isnot(None))
            .distinct()
            .all()
        ]
        chat_users = User.query.filter(User.id.in_(chat_user_ids)).order_by(User.username.asc()).all() if chat_user_ids else []

        selected_user_id = request.args.get('user_id', type=int)
        if selected_user_id:
            selected_chat_user = User.query.get(selected_user_id)
            if not selected_chat_user:
                flash('Selected chat user was not found.')
                return redirect(url_for('chat'))

        if selected_chat_user:
            all_messages = Chat.query.filter_by(
                user_id=selected_chat_user.id
            ).order_by(Chat.id.asc()).all()
        else:
            all_messages = []
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
        chat_users=chat_users,
        selected_chat_user=selected_chat_user,
        user=current_user.username,
        is_admin=admin_view
    )


@app.route('/chat/<int:message_id>/delete', methods=['POST'])
@login_required
def delete_chat(message_id):
    message = Chat.query.get_or_404(message_id)
    message_user_id = message.user_id

    if not can_delete_chat(message):
        flash('You can only delete chat messages you sent.')
        return redirect(url_for('chat'))

    if message.reply_to:
        db.session.delete(message)
    else:
        Chat.query.filter_by(reply_to=message.id).delete()
        db.session.delete(message)

    db.session.commit()

    flash('Chat message deleted.')
    if is_admin_user() and message_user_id:
        return redirect(url_for('chat', user_id=message_user_id))
    return redirect(url_for('chat'))

# ==========================================
# DATABASE VIEW

@app.route('/database')
@login_required
def database_view():
    if not is_admin_user():
        flash('Database view is admin only.')
        return redirect(url_for('dashboard'))

    users = User.query.all()
    posts = Post.query.order_by(Post.id.desc()).all()
    diary_users = db.session.query(User).join(
        Diary,
        Diary.user_id == User.id
    ).distinct().order_by(User.username.asc()).all()
    chat_users = db.session.query(User).join(
        Chat,
        Chat.user_id == User.id
    ).distinct().order_by(User.username.asc()).all()

    for post in posts:
        update_post_sentiment(post)
    db.session.commit()

    return render_template(
        'database.html',
        users=users,
        posts=posts,
        diary_users=diary_users,
        chat_users=chat_users,
        user=current_user.username
    )

# ==========================================
# SENTIMENT ANALYSIS VIEW
# ==========================================

@app.route('/sentiment-analysis')
@login_required
def sentiment_analysis():
    if not is_admin_user():
        flash('Sentiment analysis is admin only.')
        return redirect(url_for('dashboard'))

    posts = Post.query.order_by(Post.id.desc()).all()
    sentiment_items = []
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    total_score = 0

    for post in posts:
        reaction_counts, sentiment_score, sentiment = update_post_sentiment(post)
        total_votes = sum(reaction_counts.values())
        total_score += sentiment_score

        if sentiment == 'Positive':
            positive_count += 1
        elif sentiment == 'Negative':
            negative_count += 1
        else:
            neutral_count += 1

        sentiment_items.append(
            {
                'post': post,
                'reaction_counts': reaction_counts,
                'total_votes': total_votes,
                'sentiment': sentiment,
                'sentiment_score': sentiment_score,
            }
        )

    db.session.commit()

    total_posts = len(sentiment_items)
    positive_percent = round((positive_count / total_posts) * 100) if total_posts else 0
    negative_percent = round((negative_count / total_posts) * 100) if total_posts else 0
    neutral_percent = round((neutral_count / total_posts) * 100) if total_posts else 0
    average_score = round(total_score / total_posts, 2) if total_posts else 0.0
    overall_label = sentiment_label_for_score(average_score)

    return render_template(
        'sentiment_analysis.html',
        posts=sentiment_items,
        positive_count=positive_count,
        negative_count=negative_count,
        neutral_count=neutral_count,
        positive_percent=positive_percent,
        negative_percent=negative_percent,
        neutral_percent=neutral_percent,
        average_score=average_score,
        overall_label=overall_label,
        reaction_score_lookup=REACTION_SCORE_LOOKUP,
        sentiment_scale=SENTIMENT_SCALE,
        total_posts=total_posts,
        user=current_user.username
    )

# ==========================================
# CREATE DATABASE
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '1').strip().lower() in ('1', 'true', 'yes')

    app.run(host=host, port=port, debug=debug)
