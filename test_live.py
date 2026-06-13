import urllib.request
import urllib.error

for path in ['/', '/login', '/register', '/forgot']:
    url = 'http://127.0.0.1:5000' + path
    try:
        r = urllib.request.urlopen(url, timeout=5)
        data = r.read()
        print(path, '->', r.status, 'len=', len(data))
    except urllib.error.HTTPError as e:
        print(path, 'HTTPError', e.code)
    except Exception as e:
        print(path, 'Error', type(e).__name__, e)
