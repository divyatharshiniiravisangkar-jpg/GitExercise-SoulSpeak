import traceback
try:
    import auth_routes
    print('auth_routes imported')
    from app import app
    print('endpoints:')
    print('\n'.join(sorted(r.endpoint for r in app.url_map.iter_rules())))
except Exception:
    traceback.print_exc()
