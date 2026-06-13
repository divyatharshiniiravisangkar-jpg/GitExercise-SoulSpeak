from app import app

with app.test_client() as c:
    for path in ['/login', '/register', '/forgot']:
        r = c.get(path)
        body = r.get_data(as_text=True)
        print(path, r.status_code, 'len=', len(body), 'css_link=', 'static/style.css' in body)
