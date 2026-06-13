from flask import render_template, request, redirect, url_for, flash
from sqlalchemy import text

# Import app and db and User model from the main app
from app import app, db

# NOTE: The main `User` SQLAlchemy model is declared in `app.py`.
# We will operate on the `user` table directly to add missing columns
# (SQLite doesn't support DROP COLUMN; we add columns if absent) and
# perform insert/update/select operations for the simple security flow.


def ensure_user_columns():
    with app.app_context():
        inspector = db.session.execute(text("PRAGMA table_info('user')"))
        cols = [row[1] for row in inspector]
        if 'security_question' not in cols:
            db.session.execute(text("ALTER TABLE user ADD COLUMN security_question VARCHAR(255)"))
        if 'security_answer' not in cols:
            db.session.execute(text("ALTER TABLE user ADD COLUMN security_answer VARCHAR(255)"))
        db.session.commit()


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

    # Check existing email/username
    existing = db.session.execute(text('SELECT id FROM user WHERE email=:email OR username=:username'), {'email': email, 'username': username}).fetchone()
    if existing:
        flash('User with that email or username already exists')
        return redirect(url_for('register'))

    # Insert user record (storing password in plaintext to match existing app style)
    db.session.execute(text('INSERT INTO user (username, email, password, security_question, security_answer) VALUES (:username, :email, :password, :question, :answer)'), {'username': username, 'email': email, 'password': password, 'question': question, 'answer': answer})
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
    row = db.session.execute(text('SELECT security_question FROM user WHERE email=:email'), {'email': email}).fetchone()
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
    row = db.session.execute(text('SELECT security_answer FROM user WHERE email=:email'), {'email': email}).fetchone()
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

    # Update password
    db.session.execute(text('UPDATE user SET password=:pw WHERE email=:email'), {'pw': new_password, 'email': email})
    db.session.commit()

    flash('Password updated. You may now log in with your new password.')
    return redirect(url_for('login'))
