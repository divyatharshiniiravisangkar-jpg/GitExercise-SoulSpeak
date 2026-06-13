from pathlib import Path
p = Path('app.py')
b = p.read_bytes()
BOM = b'\xef\xbb\xbf'
removed = 0
while b.startswith(BOM):
    b = b[len(BOM):]
    removed += 1
p.write_bytes(b)
print('Removed', removed, 'BOM(s)')
print('Start bytes now:', repr(b[:8]))
print('Decoded start:', b.decode('utf-8', errors='replace')[:60])
