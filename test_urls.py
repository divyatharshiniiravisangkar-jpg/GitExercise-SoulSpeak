from app import app
from flask import url_for

print('Registered endpoints:')
for r in sorted(r.endpoint for r in app.url_map.iter_rules()):
    print(' -', r)

with app.test_request_context():
    try:
        print('\nurl_for("forgot") ->', url_for('forgot'))
    except Exception as e:
        print('Error building forgot:', e)
    try:
        print('url_for("register_with_security") ->', url_for('register_with_security'))
    except Exception as e:
        print('Error building register_with_security:', e)
