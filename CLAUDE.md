# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project-specific guidance. Global conventions (communication style, git workflow, always/never, code style) are in `~/CLAUDE.md`.

## Instructions

You are a full stack developer building a dashboard with a built in AI Agent for a State and Local customer. The dashboard should pull in data from multiple tenants to give the customer a one view across their whole environment that can be shared with their leadership. The data will be pulled in from their environment using Microsoft Graph API.

CRITICAL CONSTRAINTS:
- All tenants are Microsoft 365 GCC or Microsoft 365 Commercial.
- No document content may leave any tenant.
- No user-level PII may be stored centrally.
- Solution must align to CJIS-aware and sovereign boundary requirements.
- Must be Zero Trust aligned

## Project Identity

- **Repo:** `github.com/chashea/compliance-advisor`, branch `main`
- **Resource group:** `rg-compliance-advisor`
- **Current version:** v0.32.0

## Build & Run Commands

```bash
# Backend — Install collector CLI (editable)
pip install -e .

# Backend — Run collector (dry run, Data category improvement actions by default)
compliance-collect --tenant-id <GUID> --agency-id <ID> --department <DEPT> --display-name "<NAME>" --dry-run

# Backend — Run collector with different actions category
compliance-collect --tenant-id <GUID> --agency-id <ID> --department <DEPT> --actions-category Identity

# Backend — Run Function App locally
cd functions && pip install -r requirements.txt && func start

# Backend — Lint & format
ruff check .
black .

# Frontend — Dev server
cd frontend && npm run dev

# Frontend — Demo mode (uses mock data, no backend needed)
cd frontend && npm run demo    # VITE_DEMO=true vite

# Frontend — Build (type-check + bundle)
cd frontend && npm run build   # tsc -b && vite build

# Frontend — Lint
cd frontend && npm run lint

# Deploy infrastructure
az bicep build --file infra/main.bicep --outfile azuredeploy.json
az deployment group create --resource-group rg-compliance-advisor --template-file infra/main.bicep --parameters postgresAdminPassword='<PW>'
```

## Tests

48 tests across 4 files. Run all with:
```bash
python3.12 -m pytest tests/
```
Run a single test file:
```bash
python3.12 -m pytest tests/test_validation.py
```
Run a single test:
```bash
python3.12 -m pytest tests/test_validation.py::test_valid_payload
```

## Architecture

Multi-tenant compliance workload platform. Two core runtime components share a PostgreSQL database:

1. **Collector** (`collector/`) — Python CLI (`compliance-collect`) that authenticates to tenants via MSAL client credentials (app-only), pulls compliance workload data from Microsoft Graph API (eDiscovery, sensitivity labels, retention labels/events, audit log, DLP alerts, IRM alerts, protection scopes, Secure Score with Data category breakdown, improvement actions filtered to Data category by default, subject rights requests, communication compliance, information barriers), and POSTs a payload to the Function App's `/api/ingest` endpoint. DLP and IRM alerts use the legacy `/security/alerts` endpoint filtered by `vendorInformation/provider`. Use `--actions-category` (env: `ACTIONS_CATEGORY`, default: `Data`) to control which Secure Score category is collected.

2. **Function App** (`functions/`) — Azure Functions v2 Python (decorator-based, no `function.json` files). All routes defined in `function_app.py`. Three categories:
   - **Ingest** (`/api/ingest`) — FUNCTION-level auth, validates payload via JSON schema (`shared/validation.py`), upserts to PostgreSQL (`shared/db.py`).
   - **Dashboard APIs** (`/api/advisor/*`, 15 endpoints) — ANONYMOUS auth, all POST with optional `{department}` filter. SQL queries in `shared/dashboard_queries.py`. Includes AI-powered `/advisor/briefing` and `/advisor/ask` endpoints via Azure OpenAI Assistants API (rate-limited: 10 req/60s per IP).
   - **Timer** (`compute_aggregates`) — daily 6am UTC, rolls up workload counts into `compliance_trend`.

3. **Frontend** (`frontend/`) — React 19 SPA with TypeScript, Vite, Tailwind CSS v4, Recharts, React Router v7. 12 pages mapping to dashboard API endpoints. Has a demo mode (`npm run demo`) that uses mock data without a backend. Deployed to `cadvisor-web-prod` (Azure App Service).

**Database**: PostgreSQL with 17 tables (schema in `sql/schema.sql`). Connection pool via psycopg2 `ThreadedConnectionPool` in `shared/db.py`.

**Infrastructure** (`infra/`): Bicep modules for PostgreSQL Flexible Server, Function App + App Service Plan, Key Vault, Azure OpenAI, Log Analytics + App Insights. Function App uses SystemAssigned managed identity with RBAC for Key Vault and Azure OpenAI (Cognitive Services OpenAI User). `azuredeploy.json` at repo root is the compiled ARM template for the "Deploy to Azure" button.

## Key File Paths

| Component | File | Purpose |
|---|---|---|
| Function App | `functions/function_app.py` | All 17 route/timer definitions |
| DB layer | `functions/shared/db.py` | PostgreSQL connection pool + upserts |
| Dashboard queries | `functions/shared/dashboard_queries.py` | SQL for all dashboard endpoints |
| Validation | `functions/shared/validation.py` | JSON schema validation for ingest |
| AI Advisor | `functions/shared/ai_advisor.py` | Azure OpenAI Assistants API integration |
| Function config | `functions/shared/config.py` | `FunctionSettings` (pydantic-settings) |
| Collector client | `collector/compliance_client.py` | Graph API calls for 12 compliance workloads |
| Collector config | `collector/config.py` | `CollectorSettings` (pydantic-settings) |
| Payload | `collector/payload.py` | `CompliancePayload` dataclass |
| DB schema | `sql/schema.sql` | PostgreSQL table definitions |
| Infra entry | `infra/main.bicep` | Bicep entry point |
| Frontend entry | `frontend/src/App.tsx` | React app with routing |
| Frontend pages | `frontend/src/pages/` | 12 page components (Overview, DLP, IRM, etc.) |
| Frontend API | `frontend/src/api/` | API client + demo data |
| CI/CD Deploy | `.github/workflows/deploy.yml` | OIDC deploy for infra, Functions, and frontend |
| CI/CD Schedule | `.github/workflows/app-hours.yml` | Weekday ET start/stop schedule for Function App + Web App |

## Key Design Decisions

- All dashboard API routes are POST (not GET) — body contains optional filters.
- DATABASE_URL is stored as a Key Vault reference in Function App app settings (`@Microsoft.KeyVault(SecretUri=...)`). The Function App's SystemAssigned managed identity has `Key Vault Secrets User` RBAC.
- Collector uses client credentials (app-only) auth via MSAL `ConfidentialClientApplication` — `CLIENT_ID` + `CLIENT_SECRET` in `.env`. App registration: `compliance-advisor-collector` (28ce4587-667e-4eec-8740-190dee3634da), multi-tenant. Service principal must be in eDiscovery Manager and Compliance Administrator role groups in Purview.
- Config uses pydantic-settings: `functions/shared/config.py` (`FunctionSettings`) and `collector/config.py` (`CollectorSettings`).
- Audit log API is async: POST query, poll status, GET records.
- Sensitivity labels use beta API with v1.0 fallback.
- DLP and IRM alerts use the legacy `/v1.0/security/alerts` endpoint filtered by `vendorInformation/provider` — IRM has no valid `serviceSource` enum in `alerts_v2`; DLP surfaces more reliably this way.
- Improvement actions default to `controlCategory eq 'Data'` via `--actions-category` / `ACTIONS_CATEGORY` env var.
- Secure Score snapshot cross-references `controlScores` with Data category profiles to compute `data_current_score` / `data_max_score`.

## CI/CD

GitHub Actions (OIDC, no stored secrets):
- `deploy.yml`: push to `current branch` → run tests → deploy infra/functions/frontend.
- `app-hours.yml`: hourly scheduler with local-time checks (`America/New_York`) that starts apps at 9:00 AM ET and stops at 8:00 PM ET on weekdays.

## Code Style

- Python 3.12+, line length 120
- Ruff rules: `E, F, I, W` (configured in `pyproject.toml`)
- Black formatting (configured in `pyproject.toml`)
