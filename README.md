# SoulSpeak

SoulSpeak is a Flask app with login, posts, diary, chat, admin views, and sentiment analysis.

## Public Deployment

GitHub stores the code, but it does not run this Flask app by itself. For proper public use, deploy the GitHub repo to a hosting platform such as Render, Railway, PythonAnywhere, or Heroku.

All users and the admin must open the same deployed URL, for example:

```text
https://your-soulspeak-app.onrender.com
```

Use one shared hosted database so everyone sees the same users, posts, diary entries, and chat messages.

## Environment Variables

Set these on your hosting platform:

```text
SECRET_KEY=change-this-to-a-long-random-value
DATABASE_URL=your-postgresql-database-url
ADMIN_EMAILS=admin@example.com
MAIL_USERNAME=your-email@example.com
MAIL_PASSWORD=your-email-app-password
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_TIMEOUT=8
SHOW_OTP=0
FLASK_DEBUG=0
```

If `DATABASE_URL` is not set, the app uses local SQLite at `instance/database.db`, which is only suitable for local testing or a small demo.

## Run Locally

```bash
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```
