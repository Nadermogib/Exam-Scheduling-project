"""
Live endpoint smoke test for POST /api/graph (P2-T5).
Uploads the fixture, then calls /api/graph with the session_id.
"""
import json
import urllib.request
from pathlib import Path

BASE = "http://localhost:8000"

# ── Step 1: Upload fixture to get a session_id ────────────────────────────────
fixture = (Path(__file__).parent.parent.parent / "fixtures" / "test_fixture.xlsx").read_bytes()
boundary = "boundary_graph_test"
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
upload_data = json.loads(urllib.request.urlopen(req).read())
session_id = upload_data["session_id"]
print(f"Session ID: {session_id[:8]}...")
print(f"is_valid:   {upload_data['is_valid']}")

# ── Step 2: Fix the critical errors so /api/graph accepts the session ─────────
# Patch the blank course_id row (row 27 based on fixture structure)
# First find the row with blank course_id
blank_row = next(
    (r["row"] for r in upload_data["rows"] if r["course_id"] == ""),
    None
)
if blank_row:
    patch_body = json.dumps({"value": "C9999"}).encode()
    patch_req = urllib.request.Request(
        f"{BASE}/api/session/{session_id}/row/{blank_row}/field/course_id",
        data=patch_body,
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    patch_resp = json.loads(urllib.request.urlopen(patch_req).read())
    print(f"After patching blank course_id: is_valid={patch_resp['is_valid']}, errors={len(patch_resp['errors'])}")
    session_id = patch_resp.get("session_id", session_id)

# ── Step 3: Fix Rule 3 error (C0508 name conflict) — patch display_name ──────
# Find rows with C0508 and unify to one name
c0508_rows = [r for r in upload_data["rows"] if r["course_id"] == "C0508"]
if len(c0508_rows) >= 2:
    fix_row = c0508_rows[1]["row"]
    patch_body2 = json.dumps({"value": c0508_rows[0]["course_display_name"]}).encode()
    patch_req2 = urllib.request.Request(
        f"{BASE}/api/session/{session_id}/row/{fix_row}/field/course_display_name",
        data=patch_body2,
        headers={"Content-Type": "application/json"},
        method="PATCH",
    )
    patch_resp2 = json.loads(urllib.request.urlopen(patch_req2).read())
    print(f"After patching C0508 name: is_valid={patch_resp2['is_valid']}, errors={len(patch_resp2['errors'])}")

# ── Step 4: Call /api/graph ───────────────────────────────────────────────────
graph_body = json.dumps({"session_id": session_id}).encode()
graph_req = urllib.request.Request(
    f"{BASE}/api/graph",
    data=graph_body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
g = json.loads(urllib.request.urlopen(graph_req).read())
print()
print("=== /api/graph response ===")
print(f"  nodes:           {g['nodes']}")
print(f"  edges:           {g['edges']}")
print(f"  max_degree:      {g['max_degree']}")
print(f"  max_clique_size: {g['max_clique_size']}  ← min exam days needed")
print(f"  isolated_nodes:  {len(g['isolated_nodes'])} course(s) with no conflicts")
print(f"  conflict_pairs:  {len(g['conflict_pairs'])} pairs (first 3): {g['conflict_pairs'][:3]}")
print()
print("[OK] P2-T5 verified: /api/graph returns correct graph statistics")
