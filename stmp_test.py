import os
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

mail_server = os.environ.get('MAIL_SERVER', 'smtp.gmail.com').strip()
mail_port = int(os.environ.get('MAIL_PORT', '587'))
mail_username = (os.environ.get('MAIL_USERNAME') or '').strip()
mail_password = (os.environ.get('MAIL_PASSWORD') or '').replace(' ', '').strip()
mail_to = (os.environ.get('SMTP_TEST_TO') or mail_username).strip()

missing = [
    name
    for name, value in {
        'MAIL_USERNAME': mail_username,
        'MAIL_PASSWORD': mail_password,
        'SMTP_TEST_TO or MAIL_USERNAME': mail_to,
    }.items()
    if not value
]

if missing:
    raise SystemExit(
        'Missing SMTP setting(s): '
        + ', '.join(missing)
        + '. Add them to .env first.'
    )

if mail_server == 'smtp.gmail.com' and len(mail_password) != 16:
    raise SystemExit(
        f'MAIL_PASSWORD is {len(mail_password)} characters. Gmail SMTP needs a '
        '16-character App Password, not your normal Gmail password.'
    )

msg = EmailMessage()
msg.set_content('SOULSPEAK SMTP test email. If you received this, OTP email can work.')
msg['Subject'] = 'SOULSPEAK SMTP test'
msg['From'] = f'SOULSPEAK <{mail_username}>'
msg['To'] = mail_to

ctx = ssl.create_default_context()
try:
    if mail_port == 465:
        with smtplib.SMTP_SSL(mail_server, mail_port, context=ctx) as server:
            server.login(mail_username, mail_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(mail_server, mail_port) as server:
            server.starttls(context=ctx)
            server.login(mail_username, mail_password)
            server.send_message(msg)
except smtplib.SMTPAuthenticationError as exc:
    raise SystemExit(
        'SMTP login failed. For Gmail, MAIL_PASSWORD must be a 16-digit App Password, '
        'not your normal Gmail password. Original error: '
        + str(exc)
    ) from exc

print(f'SMTP test sent to {mail_to}')
