#!/usr/bin/env python3
"""Post-deployment verification — checks database, data, and API health."""
import os
import sqlite3
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

db_path = os.environ.get("SQLITE_DB_PATH", "data/compliance.db")
api_base = os.environ.get("COMPLIANCE_API_BASE", "http://localhost:8000/api/advisor")
ok = 0
fail = 0


def check(label: str, passed: bool, detail: str = "") -> None:
    global ok, fail
    status = "PASS" if passed else "FAIL"
    msg = f"  [{status}] {label}"
    if detail:
        msg += f" — {detail}"
    print(msg)
    if passed:
        ok += 1
    else:
        fail += 1


# ── 1. Database exists ────────────────────────────────────────────────────────
print("\n1. Database")
db_exists = Path(db_path).exists()
check("Database file exists", db_exists, db_path)

if not db_exists:
    print("\n  Run 'python init_db.py' to create the database.")
    sys.exit(1)

conn = sqlite3.connect(db_path)

# ── 2. Schema ─────────────────────────────────────────────────────────────────
print("\n2. Schema")
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
views = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name").fetchall()]
check("Tables created", len(tables) >= 8, f"{len(tables)} tables")
check("Views created", len(views) >= 17, f"{len(views)} views")

# ── 3. Data ───────────────────────────────────────────────────────────────────
print("\n3. Data (run sync.py to populate)")
counts = {}
for table in ["tenants", "secure_scores", "control_scores", "assessments", "assessment_controls", "compliance_scores"]:
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
    except Exception:
        count = 0
    counts[table] = count
    check(f"{table}", count > 0, f"{count} rows")

conn.close()

# ── 4. API health ─────────────────────────────────────────────────────────────
print("\n4. API (start with 'uvicorn api:app --port 8000')")
try:
    import requests

    resp = requests.post(f"{api_base}/status", json={}, timeout=5)
    data = resp.json()
    check("API responding", resp.status_code == 200, f"HTTP {resp.status_code}")
    check("Status healthy", data.get("status") == "healthy", data.get("status", "unknown"))
    check("Active tenants", (data.get("active_tenants") or 0) > 0, f"{data.get('active_tenants')} tenants")
except requests.ConnectionError:
    check("API responding", False, f"could not connect to {api_base}")
except Exception as e:
    check("API responding", False, str(e))

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\n{'=' * 40}")
print(f"  {ok} passed, {fail} failed")
if fail == 0:
    print("  All checks passed.")
else:
    print("  Review failures above.")
sys.exit(1 if fail else 0)
