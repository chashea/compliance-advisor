# Compliance Advisor — Local Dashboard MVP

A single-tenant CISO dashboard that pulls real **Microsoft Secure Score** and
**Compliance Manager** data from your M365 tenant via Microsoft Graph and
visualises it locally with Chart.js.

- Dashboard/API mode runs locally with no Azure infrastructure required.
- Conversational agent mode requires Azure AI Foundry (and Azure AI Search for knowledge retrieval).

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
- An **Entra ID app registration** in your M365 tenant with app credentials
  (`AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`) and Graph
  permissions needed for the Secure Score and Compliance Manager endpoints your
  tenant exposes.

If you don't have credentials yet, skip straight to [Start the server](#4-start-the-server) —
the dashboard falls back to built-in demo data automatically.

---

## Quick Start

### Option A — Demo mode (no Azure credentials needed)

Explore the UI with an empty database — the dashboard renders chart
placeholders so you can evaluate the layout before connecting a real tenant.

```bash
cd compliance-advisor
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python init_db.py          # create empty data/compliance.db
uvicorn api:app --reload --port 8000
```

Open **http://localhost:8000**.

### Option B — Live data from your M365 tenant

```bash
cd compliance-advisor
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env       # Windows: copy .env.example .env
```

Open `.env` and fill in your tenant credentials:

```bash
AZURE_TENANT_ID=your-tenant-guid
AZURE_CLIENT_ID=your-app-client-id
AZURE_CLIENT_SECRET=your-client-secret
TENANT_DISPLAY_NAME=My Organization
TENANT_DEPARTMENT=IT
TENANT_RISK_TIER=High
```

Then initialise the database, sync live data from Microsoft Graph, and start
the server:

```bash
python init_db.py          # create data/compliance.db
python sync.py             # pull Secure Score + Compliance Manager from Graph
uvicorn api:app --reload --port 8000
```

Open **http://localhost:8000** — the dashboard now shows real tenant data.
Re-run `sync.py` at any time to refresh.

### Verify deployment

```bash
python verify.py
```

This runs automated checks against the database and API. Expected output
after a successful full deployment:

```
1. Database
  [PASS] Database file exists — data/compliance.db

2. Schema
  [PASS] Tables created — 8 tables
  [PASS] Views created — 17 views

3. Data
  [PASS] secure_scores — 90 rows
  ...

4. API
  [PASS] API responding — HTTP 200
  [PASS] Status healthy — healthy
  [PASS] Active tenants — 1 tenants

  11 passed, 0 failed
```

---

## Conversational Agent

The Compliance Advisor includes an **Azure AI Foundry** conversational agent that
answers natural-language questions about your compliance posture in real time.
The agent calls Python functions that query the local SQLite database on every
turn — no stale index, no extra Azure service.

### How it works

```
You (terminal)
    │
    ▼
agent.py  ──→  Azure AI Foundry (GPT-4o, Responses API)
                    │
                    └─ function tool calls → compliance_tools.py
                                                  │
                                                  ▼
                                          data/compliance.db
                                          (populated by sync.py)
```

GPT-4o never touches Microsoft Graph or the database directly. It calls one of
nine Python functions, receives the JSON result, and writes a natural-language
answer. Conversation context is maintained via `previous_response_id` — no
persistent assistant or thread objects are created.

Nine function tools are registered:

| Tool | What it returns |
|------|-----------------|
| `get_secure_score` | Current score %, current/max points, 30-day trend |
| `get_top_gaps` | Top N controls by unrealised points, with remediation URLs |
| `get_weekly_change` | Week-over-week delta for Secure Score and Compliance Score |
| `get_compliance_score` | Compliance Manager score %, 30-day trend |
| `get_assessments` | Active assessments with pass rates (filterable by regulation) |
| `get_improvement_actions` | Prioritised actions (filterable by regulation) |
| `get_regulation_coverage` | Pass rates per framework (NIST, ISO, SOC 2, CIS…) |
| `get_category_breakdown` | Avg gap by control category / control family |
| `search_knowledge` | Retrieved policy/framework/remediation passages from Azure AI Search |

### 1. Register an Entra ID app for Microsoft Graph

```bash
az login

# Create the app registration
az ad app create --display-name "compliance-advisor"

# Create its service principal (note the AppId from the output above)
az ad sp create --id <AppId>

# Add SecurityEvents.Read.All (application permission)
az ad app permission add \
  --id <AppId> \
  --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions bf394140-e372-4bf9-a898-299cfc7564e5=Role

# Create a client secret
az ad app credential reset --id <AppId> --display-name "compliance-advisor-secret" --years 1
```

Then have a **Global Administrator** grant admin consent — either via the Entra
portal (App registrations → compliance-advisor → API permissions → Grant admin
consent) or by opening this URL in a GA browser session:

```
https://login.microsoftonline.com/<TENANT_ID>/adminconsent?client_id=<AppId>
```

> **Note:** Compliance Manager Graph access differs by endpoint and tenant. If
> Compliance Manager results are empty, verify API permissions/consent for your
> tenant and validate with Graph Explorer for the same endpoints.

### 2. Provision Azure AI Foundry infrastructure

```bash
az group create --name rg-compliance-advisor --location eastus
az deployment group create \
  --resource-group rg-compliance-advisor \
  --template-file infra/foundry.bicep \
  --query "properties.outputs" -o table
```

Copy the `endpoint` and `searchEndpoint` values from the output.

Assign the **Azure AI Developer** RBAC role to your app's service principal on
the AIServices resource so it can call the Foundry API:

```bash
az rest --method PUT \
  --url "https://management.azure.com/subscriptions/<SUB_ID>/resourceGroups/rg-compliance-advisor/providers/Microsoft.CognitiveServices/accounts/compliance-advisor/providers/Microsoft.Authorization/roleAssignments/<NEW-GUID>?api-version=2022-04-01" \
  --body '{"properties":{"roleDefinitionId":"/subscriptions/<SUB_ID>/providers/Microsoft.Authorization/roleDefinitions/64702f94-c441-49e6-a78b-ef80e0188fee","principalId":"<SERVICE_PRINCIPAL_OBJECT_ID>","principalType":"ServicePrincipal"}}'
```

### 3. Configure .env

```bash
cp .env.example .env
```

Fill in all values:

```bash
AZURE_TENANT_ID=<tenant-guid>
AZURE_CLIENT_ID=<app-client-id>
AZURE_CLIENT_SECRET=<client-secret>
TENANT_DISPLAY_NAME=My Organization
TENANT_DEPARTMENT=IT
TENANT_RISK_TIER=High
SQLITE_DB_PATH=data/compliance.db

AIPROJECT_ENDPOINT=<endpoint from deployment output>
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_SEARCH_ENDPOINT=https://<search-service>.search.windows.net
AZURE_SEARCH_INDEX_NAME=<compliance-knowledge-index>
# Optional when using AzureCliCredential for local dev:
# AZURE_SEARCH_API_KEY=<query-or-admin-key>
```

### 4. Install dependencies

On **Windows ARM64**, install the `cryptography` binary wheel first to avoid a
Rust build failure:

```bash
python -m venv .venv
.venv\Scripts\pip install --upgrade pip
.venv\Scripts\pip install --only-binary cryptography cryptography
.venv\Scripts\pip install -r requirements.txt
```

On x64 / macOS / Linux, the standard install works:

```bash
pip install -r requirements.txt
```

### 5. Initialise the database and sync data

```bash
.venv\Scripts\python init_db.py
.venv\Scripts\python sync.py
```

### 6. Start the agent

```bash
.venv\Scripts\python agent.py --register-only
```

Expected output:
```
Registered Foundry Agent: compliance-advisor v1 (id: ...)
```

Then start interactive chat:

```bash
.venv\Scripts\python agent.py
```

Expected output:
```
Registered Foundry Agent: compliance-advisor v2 (id: ...)
Compliance Advisor ready. Type 'quit' to exit.

You:
```

Set `FOUNDRY_AGENT_NAME` in `.env` to control the portal-visible agent name.
Each run registers a new version via `client.agents.create_version(...)` with
the system prompt and function tool definitions.

The agent uses `AzureCliCredential` (`az login`) for Azure AI Foundry calls.
The `AZURE_CLIENT_ID`/`AZURE_CLIENT_SECRET` in `.env` are used only by `sync.py`
for Microsoft Graph — they are not used by the agent.

### 7. Clean release workflow (recommended)

Use this sequence whenever publishing changes to GitHub and deploying:

1. Pull latest `main` and run tests locally.
2. Deploy/update Foundry + Search infra from `infra/foundry.bicep`.
3. Run sync to refresh Purview-backed data.
4. Register a new Foundry agent version from current source.
5. Run smoke checks (`/api/advisor/status`, one `search_knowledge` prompt).
6. Commit, push, and tag release.

Example command flow:

```bash
git pull origin main
.venv/bin/python -m pytest -q tests/test_compliance_tools.py
az deployment group create --resource-group rg-compliance-advisor --template-file infra/foundry.bicep
.venv/bin/python sync.py
.venv/bin/python agent.py --register-only
curl -s -X POST http://localhost:8000/api/advisor/status
git push origin main
```

### Example questions

- `What is our current Secure Score?`
- `What are our top 5 compliance gaps?`
- `Which NIST 800-53 controls are we failing?`
- `What should we prioritise to improve our score this week?`
- `How has our compliance posture changed since last week?`
- `Show me our SOC 2 pass rate`

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
| `POST /api/advisor/briefing` | `department` | Raw SQL executive briefing from local data |
| `POST /api/advisor/ask` | `question` (string) | Local API stub response; use `agent.py` for Foundry-powered chat |

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
├── agent.py                # Azure AI Foundry conversational agent
├── compliance_tools.py     # 9 function tools for the Foundry agent
├── sync.py                 # One-command data sync from Microsoft Graph
├── init_db.py              # One-time database initialiser
├── verify.py               # Post-deployment verification checks
├── index_knowledge.py      # Azure AI Search index builder
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Ruff, Black, Mypy, Pytest config
├── .env.example            # Credential template
├── infra/
│   └── foundry.bicep       # Azure AI Foundry + AI Search Bicep template
├── sql/
│   ├── schema.sql          # Original SQL Server schema (reference)
│   └── schema_sqlite.sql   # SQLite translation (used by init_db.py)
├── src/
│   ├── functions/activities/
│   │   ├── collect_tenant_data.py    # Pulls Secure Score from Graph
│   │   └── collect_compliance_data.py # Pulls Compliance Manager from Graph
│   └── shared/
│       ├── auth.py         # OAuth2 token helper (reads from .env)
│       ├── ai_search_client.py # Azure AI Search query client
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
├── tests/                  # Unit tests (pytest)
├── .github/
│   └── workflows/ci.yml    # CI pipeline (ruff, black, mypy, pytest)
└── docs/
    ├── DATA-SOURCE-PURVIEW.md
    └── M365-GCC-SETUP.md
```
