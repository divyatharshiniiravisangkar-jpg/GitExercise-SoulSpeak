from app import app
with app.test_client() as client:
    resp = client.get('/login')
    print('status', resp.status_code)
    print('len', len(resp.get_data(as_text=True)))
    txt = resp.get_data(as_text=True)
    print('/forgot in body:', '/forgot' in txt)
    print('error snippet:' , txt[:200])
