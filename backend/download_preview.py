import urllib.request
import urllib.parse
import json
import io
import sys
from pathlib import Path

with open('../fixtures/test_fixture.xlsx', 'rb') as f:
    data = f.read()

boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
body = (
    b'--' + boundary.encode() + b'\r\n' +
    b'Content-Disposition: form-data; name=\"file\"; filename=\"test_fixture.xlsx\"\r\n' +
    b'Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n' +
    data + b'\r\n' +
    b'--' + boundary.encode() + b'--\r\n'
)

req = urllib.request.Request(
    'http://localhost:8000/api/upload',
    data=body,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)
resp = urllib.request.urlopen(req)
session_id = json.loads(resp.read().decode())['session_id']

config = {
    'available_days': 20,
    'max_courses_per_day': 3,
    'excluded_dates': [],
    'start_date': '2026-08-20'
}
req2 = urllib.request.Request(
    f'http://localhost:8000/api/schedule?session_id={session_id}',
    data=json.dumps(config).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
urllib.request.urlopen(req2)

master_url = f'http://localhost:8000/api/export/master?session_id={session_id}'
with urllib.request.urlopen(master_url) as r, open(r'C:\Users\DELL\.gemini\antigravity-ide\brain\312324b9-08f4-4db3-928e-be7053e47ad1\master_preview.xlsx', 'wb') as f:
    f.write(r.read())

dept = 'شبكات الحاسوب'
dept_url = f'http://localhost:8000/api/export/department/{urllib.parse.quote(dept)}?session_id={session_id}'
with urllib.request.urlopen(dept_url) as r, open(r'C:\Users\DELL\.gemini\antigravity-ide\brain\312324b9-08f4-4db3-928e-be7053e47ad1\dept_preview.xlsx', 'wb') as f:
    f.write(r.read())

print('Success! Files saved.')
