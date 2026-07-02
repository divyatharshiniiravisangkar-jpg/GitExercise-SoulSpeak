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
OTP_FALLBACK_ON_MAIL_FAILURE=0
```

If `DATABASE_URL` is not set, the app uses local SQLite at `instance/database.db`, which is only suitable for local testing or a small demo.

For Gmail, `MAIL_PASSWORD` must be a 16-character Gmail App Password, not your normal Gmail password. The app also accepts common SMTP aliases such as `EMAIL_USER`, `EMAIL_PASSWORD`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SERVER`, and `SMTP_PORT`. If port `587` is unreachable, the app automatically retries Gmail on port `465`.

Keep `OTP_FALLBACK_ON_MAIL_FAILURE=0` when you want OTPs to be email-only.

If the published app says `[Errno 101] Network is unreachable`, the hosting platform is blocking Gmail SMTP. Use Gmail API instead by adding these environment variables:

```text
MAIL_USERNAME=your-gmail@gmail.com
GMAIL_CLIENT_ID=your-google-oauth-client-id
GMAIL_CLIENT_SECRET=your-google-oauth-client-secret
GMAIL_REFRESH_TOKEN=your-google-oauth-refresh-token
SHOW_OTP=0
FLASK_DEBUG=0
OTP_FALLBACK_ON_MAIL_FAILURE=0
```

When Gmail API variables are present, the app sends OTP email through Gmail over HTTPS before trying SMTP.

To test Gmail API locally after setting the variables:

```bash
python gmail_api_test.py
```

## Run Locally

```bash
pip install -r requirements.txt
python app.py
```

Open:

```text
http://127.0.0.1:5000
```
