import os

from app import app
from app import send_email


mail_to = (os.environ.get('SMTP_TEST_TO') or app.config.get('MAIL_USERNAME') or '').strip()
if not mail_to:
    raise SystemExit('Set SMTP_TEST_TO or MAIL_USERNAME first.')

sent = send_email(
    mail_to,
    'SOULSPEAK Gmail API test',
    'SOULSPEAK Gmail API test email. If you received this, OTP email can work.',
)

if not sent:
    raise SystemExit(app.config.get('LAST_MAIL_ERROR') or 'Gmail API test failed.')

print(f'Gmail API test sent to {mail_to}')
