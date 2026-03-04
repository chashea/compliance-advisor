# Compliance Advisor — Local Dashboard MVP

A single-tenant CISO dashboard that pulls real **Microsoft Secure Score** and
**Compliance Manager** data from your M365 tenant via Microsoft Graph and
visualises it locally with Chart.js. No Azure infrastructure required.

```
.env (AZURE_TENANT_ID, CLIENT_ID, CLIENT_SECRET)
    │
    ▼
sync.py ──→ src/shared/auth.py (OAuth2) ──→ Microsoft Graph API
    │           └── collect_tenant_data.py   (Secure Score)
    │           └── collect_compliance_data.py (Compliance Manager)
    │
    ▼
sqlite3 ──→ data/compliance.db
    │
    ▼
api.py (FastAPI + uvicorn, port 8000)
    ├── POST /api/advisor/{action}
    └── GET  /  →  dashboard/index.html

Browser → http://localhost:8000
```

---

## Prerequisites

- Python 3.10+
- An **Entra ID app registration** in your M365 tenant with:
  - `SecurityEvents.Read.All` (Application permission, admin-consented) — for Secure Score
  - `ComplianceManager.Read.All` (Application permission, admin-consented) — for Compliance Manager
  - A client secret

If you don't have credentials yet, skip straight to [Start the server](#4-start-the-server) —
the dashboard falls back to built-in demo data automatically.

---

## Setup

### 1. Create a virtual environment and install dependencies

```bash
cd compliance-advisor
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure credentials

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and fill in your tenant details:

```bash
AZURE_TENANT_ID=your-tenant-guid
AZURE_CLIENT_ID=your-app-client-id
AZURE_CLIENT_SECRET=your-client-secret
TENANT_DISPLAY_NAME=My Organization   # display name shown in the dashboard
TENANT_DEPARTMENT=IT
TENANT_RISK_TIER=High
SQLITE_DB_PATH=data/compliance.db
# GRAPH_NATIONAL_CLOUD=usgovernment   # GCC High / DoD only — leave blank for commercial & GCC
```

### 3. Initialise the database

Run once to create `data/compliance.db` from the SQLite schema:

```bash
python init_db.py
```

Expected output:
```
Database initialized: data/compliance.db
```

### 4. Sync data from Microsoft Graph

```bash
python sync.py
```

Expected output (counts will vary):
```
2024-01-15 10:23:01 INFO Syncing Secure Score...
2024-01-15 10:23:04 INFO {'tenant_id': '...', 'success': True, 'snapshots': 90}
2024-01-15 10:23:04 INFO Syncing Compliance Manager...
2024-01-15 10:23:12 INFO {'tenant_id': '...', 'success': True, 'compliance_score': 67.4, 'assessments': 4, 'controls': 312}
2024-01-15 10:23:12 INFO Sync complete.
```

### 5. Start the server

```bash
uvicorn api:app --reload --port 8000
```

Open **http://localhost:8000** in your browser.

---

## Verification

Run these checks in order after setup to confirm each layer is working.

### 1. Database was created with the correct schema

```bash
python -c "
import sqlite3
c = sqlite3.connect('data/compliance.db')
tables = [r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
views  = [r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='view'\").fetchall()]
print('Tables:', len(tables), tables)
print('Views: ', len(views),  views)
"
```

Expected: **8 tables** and **17 views**.

### 2. Data was synced successfully

```bash
python -c "
import sqlite3
c = sqlite3.connect('data/compliance.db')
print('Secure Score snapshots:', c.execute('SELECT COUNT(*) FROM secure_scores').fetchone()[0])
print('Control scores:        ', c.execute('SELECT COUNT(*) FROM control_scores').fetchone()[0])
print('Assessments:           ', c.execute('SELECT COUNT(*) FROM assessments').fetchone()[0])
print('Assessment controls:   ', c.execute('SELECT COUNT(*) FROM assessment_controls').fetchone()[0])
print('Compliance scores:     ', c.execute('SELECT COUNT(*) FROM compliance_scores').fetchone()[0])
"
```

Expected: non-zero counts in each table after `sync.py`.

### 3. API health check

```bash
curl -s -X POST http://localhost:8000/api/advisor/status | python -m json.tool
```

Expected:
```json
{
    "active_tenants": 1,
    "oldest_sync": "2024-01-15 10:23:12",
    "newest_sync": "2024-01-15 10:23:12",
    "status": "healthy"
}
```

### 4. Secure Score trends

```bash
curl -s -X POST http://localhost:8000/api/advisor/trends \
  -H "Content-Type: application/json" \
  -d '{"days": 30}' | python -m json.tool
```

Expected: `score_trend` array with daily data points.

### 5. Compliance Manager data

```bash
curl -s -X POST http://localhost:8000/api/advisor/compliance \
  -H "Content-Type: application/json" \
  -d '{}' | python -m json.tool
```

Expected: `latest_scores`, `compliance_trend`, and `department_rollup` arrays.

### 6. Assessment gaps

```bash
curl -s -X POST http://localhost:8000/api/advisor/assessments \
  -H "Content-Type: application/json" \
  -d '{"top_gaps": 5}' | python -m json.tool
```

Expected: `assessments` list and `top_gaps` ranked by points gap.

### 7. Dashboard loads with real data

Open **http://localhost:8000** and verify:
- Trend charts are populated (not the "Demo data" placeholder)
- The tenant name matches `TENANT_DISPLAY_NAME` in your `.env`
- Check the **"Demo data"** toggle — uncheck it to confirm live data loads;
  re-check it to restore the synthetic fallback

---

## API Reference

All endpoints accept `POST` with a JSON body. All responses are JSON.

| Endpoint | Body params | Description |
|----------|-------------|-------------|
| `POST /api/advisor/status` | _(none)_ | Health check — tenant count and last sync time |
| `POST /api/advisor/trends` | `days` (int, default 30, max 90), `tenant_id`, `department` | Secure Score trend, week-over-week change, category breakdown |
| `POST /api/advisor/departments` | _(none)_ | Department rollup and risk-tier summary |
| `POST /api/advisor/compliance` | `days`, `department` | Compliance Manager scores, trend, weekly change, department rollup |
| `POST /api/advisor/assessments` | `top_gaps` (int, default 20), `department`, `regulation` | Assessment summary, top control gaps, family breakdown |
| `POST /api/advisor/regulations` | _(none)_ | Regulation coverage and pass rates |
| `POST /api/advisor/actions` | `top_n`, `department`, `regulation`, `status`, `owner`, `score_impact` | Prioritised improvement actions |
| `POST /api/advisor/briefing` | `department` | Raw SQL executive briefing (AI agent not available in local MVP) |
| `POST /api/advisor/ask` | `question` (string) | Returns stub — AI advisor not available in local MVP |

---

## Keeping data fresh

Re-run `sync.py` at any time to pull the latest snapshot from Microsoft Graph.
The sync is idempotent — existing rows are updated in place.

```bash
python sync.py
```

To automate it, add a daily scheduled task / cron job that runs `sync.py`.

---

## GCC High / DoD tenants

Set `GRAPH_NATIONAL_CLOUD=usgovernment` in `.env`. This switches the OAuth2
endpoint to `login.microsoftonline.us` and the Graph scope to
`https://graph.microsoft.us/.default`. See [docs/M365-GCC-SETUP.md](docs/M365-GCC-SETUP.md)
for app registration details.

Standard M365 GCC uses the **same global endpoints** as commercial — leave
`GRAPH_NATIONAL_CLOUD` unset.

---

## Data sources

Dashboard data maps directly to **Microsoft Purview Compliance Manager**:
compliance score, assessments, improvement actions, implementation status,
and test status. See [docs/DATA-SOURCE-PURVIEW.md](docs/DATA-SOURCE-PURVIEW.md)
for the full field mapping.

---

## Project structure

```
compliance-advisor/
├── api.py                  # FastAPI server (API + static dashboard)
├── sync.py                 # One-command data sync from Microsoft Graph
├── init_db.py              # One-time database initialiser
├── requirements.txt        # Python dependencies
├── .env.example            # Credential template
├── sql/
│   ├── schema.sql          # Original SQL Server schema (reference)
│   └── schema_sqlite.sql   # SQLite translation (used by init_db.py)
├── src/
│   ├── functions/activities/
│   │   ├── collect_tenant_data.py    # Pulls Secure Score from Graph
│   │   └── collect_compliance_data.py # Pulls Compliance Manager from Graph
│   └── shared/
│       ├── auth.py         # OAuth2 token helper (reads from .env)
│       ├── graph_client.py # Microsoft Graph HTTP client
│       └── sql_client.py   # SQLite connection and upsert helpers
├── dashboard/
│   ├── index.html          # CISO dashboard
│   ├── app.js              # Chart.js data loading and rendering
│   ├── styles.css
│   └── env.js              # API base URL (http://localhost:8000/api/advisor)
├── data/
│   ├── compliance.db       # SQLite database (created by init_db.py, gitignored)
│   └── frameworks/         # Local JSON files: NIST, ISO 27001, SOC 2, CIS
├── tests/                  # Unit tests
└── docs/
    ├── DATA-SOURCE-PURVIEW.md
    └── M365-GCC-SETUP.md
```
