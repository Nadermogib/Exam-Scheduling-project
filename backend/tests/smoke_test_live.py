"""Quick smoke test for the live upload and template endpoints."""
import json
import urllib.request
from pathlib import Path

BASE = "http://localhost:8000"

# ── Template ──────────────────────────────────────────────────────────────────
resp = urllib.request.urlopen(f"{BASE}/api/template")
print("Template Content-Disposition:", resp.headers.get("Content-Disposition", ""))
print("Template Content-Type:        ", resp.headers.get("Content-Type", ""))
print("Template size (bytes):        ", len(resp.read()))

# ── Upload ────────────────────────────────────────────────────────────────────
fixture = (Path(__file__).parent.parent.parent / "fixtures" / "test_fixture.xlsx").read_bytes()
boundary = "boundary123abc"
body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="test_fixture.xlsx"\r\n'
    f"Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n"
).encode() + fixture + f"\r\n--{boundary}--\r\n".encode()

req = urllib.request.Request(
    f"{BASE}/api/upload",
    data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)
resp2 = urllib.request.urlopen(req)
data = json.loads(resp2.read())
print()
print("Upload session_id:  ", data.get("session_id", "MISSING"))
print("Upload is_valid:    ", data.get("is_valid"))
print("Upload row_count:   ", data.get("row_count"))
print("Critical errors:    ", len(data.get("errors", [])))
print("Warnings:           ", len(data.get("warnings", [])))
print()
for i, err in enumerate(data.get("errors", []), 1):
    print(f"  Error {i} [Rule {err['rule']}] Row {err['row']}: {err['message'][:60]}...")
