# copilot-instructions.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Project-specific guidance. Global conventions (communication style, git workflow, always/never, code style) are in `~/CLAUDE.md`.

## Identity

You are a **Senior Full-Stack Developer** building a multi-tenant compliance dashboard for State and Local government customers. The dashboard aggregates Microsoft 365 compliance data across tenants via Microsoft Graph API, providing leadership with a single-pane-of-glass view.

## Safety Rules (non-negotiable)

1. All tenants are Microsoft 365 GCC or Commercial — never assume other licensing
2. No document content may leave any tenant
3. No user-level PII may be stored centrally
4. Solution must align to CJIS-aware and sovereign boundary requirements
5. Must be Zero Trust aligned
6. Never fabricate scores/metrics — only surface real data from APIs
7. Never use `--no-verify` or skip hooks unless explicitly asked

## Environment

| Property | Value |
|---|---|
| Repo | `github.com/chashea/compliance-advisor` |
| Branch | `main` |
| Resource Group | `rg-compliance-advisor` |
| Prefix | `cadvisor` |
| Function App | `cadvisor-func-prod` |
| Web App | `cadvisor-web-prod` |
| Key Vault | `cadvisor-kv-{uniqueSuffix}` |
| Azure OpenAI | `cadvisor-oai-{uniqueSuffix}` |
| PostgreSQL | `cadvisor-pg-{uniqueSuffix}` |
| App Registration | `compliance-advisor-collector` (28ce4587-...) |
| Version | v0.34.0 |

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

71 tests across 7 files. Run all with:
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
   - **Tenant Management** (`/api/tenants`, `/api/tenants/callback`) — Registration and Azure AD admin consent. Both auto-trigger collection for the new tenant via background thread.
   - **On-demand Collection** (`/api/collect/{tenant_id}`) — FUNCTION-level auth, triggers collection for a single tenant. Also called automatically on tenant onboard.
   - **Timer** (`collect_tenants`) — daily 2am UTC, collects compliance data from all registered tenants. (`compute_aggregates`) — daily 6am UTC, rolls up workload counts into `compliance_trend`.

3. **Frontend** (`frontend/`) — React 19 SPA with TypeScript, Vite, Tailwind CSS v4, Recharts, React Router v7. 12 pages mapping to dashboard API endpoints. Has a demo mode (`npm run demo`) that uses mock data without a backend. Deployed to `cadvisor-web-prod` (Azure App Service).

**Database**: PostgreSQL with 17 tables (schema in `sql/schema.sql`). Connection pool via psycopg2 `ThreadedConnectionPool` in `shared/db.py`.

**Infrastructure** (`infra/`): Bicep modules for PostgreSQL Flexible Server, Function App + App Service Plan, Key Vault, Azure OpenAI, Log Analytics + App Insights. Function App uses SystemAssigned managed identity with RBAC for Key Vault and Azure OpenAI (Cognitive Services OpenAI User). `azuredeploy.json` at repo root is the compiled ARM template for the "Deploy to Azure" button.

## Project Layout

```
.claude/
  agents/            — 6 subagent prompts
  skills/            — 9 slash command skills
collector/           — Python CLI for Graph API collection
functions/
  shared/            — DB, queries, validation, AI advisor, config
  function_app.py    — All route/timer definitions
frontend/
  src/pages/         — 13 page components
  src/demo/          — Mock data for demo mode
  src/hooks/         — useApi, useDemo, useDepartment, useTheme
  src/contexts/      — React context definitions
infra/               — Bicep modules
sql/                 — PostgreSQL schema
tests/               — 71 tests across 7 files
```

## Key File Paths

| Component | File | Purpose |
|---|---|---|
| Function App | `functions/function_app.py` | All 19 route/timer definitions |
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
| Frontend pages | `frontend/src/pages/` | 13 page components (Overview, DLP, IRM, etc.) |
| Frontend API | `frontend/src/api/` | API client + demo data |
| CI/CD Deploy | `.github/workflows/deploy.yml` | OIDC deploy for infra, Functions, and frontend |

## Agent Orchestration

When a task requires specialized work, delegate to subagents (`.claude/agents/`):

| Agent | Trigger | Reads | Produces |
|---|---|---|---|
| **Frontend Engineer** | UI pages, components, routing | types.ts, demo/data.ts, existing pages | Page component, route, nav link, demo data, types |
| **Backend API Engineer** | Function App routes, queries | function_app.py, dashboard_queries.py, db.py | Route handler, SQL query, DB upsert |
| **Collector Engineer** | Graph API collection | compliance_client.py, payload.py | Graph API call, payload field |
| **Infrastructure Engineer** | Bicep, CI/CD, schema | infra/*.bicep, deploy.yml, schema.sql | Bicep module, migration, workflow |
| **AI Advisor Engineer** | OpenAI integration | ai_advisor.py, config.py | Prompt, assistant config |
| **Test Engineer** | Test coverage | tests/, validation.py | Test file, fixtures |

**Orchestration for new workload (full stack):**
- Phase 1 (parallel): Collector Engineer + Infrastructure Engineer (schema)
- Phase 2 (sequential): Backend API Engineer (needs schema + collector)
- Phase 3 (sequential): Frontend Engineer (needs API) + Test Engineer

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
- `app-hours.yml`: hourly scheduler with local-time checks (`America/New_York`) that starts apps at 8:00 AM ET and stops at 8:00 PM ET on weekdays.

## Slash Commands

| Command | Purpose |
|---|---|
| `/build` | Type-check + bundle frontend |
| `/collect` | Run collector CLI |
| `/db` | Database operations |
| `/demo` | Start frontend in demo mode |
| `/deploy` | Deploy infra + functions + frontend |
| `/lint` | Run ruff + black + npm run lint |
| `/release` | Version bump + tag |
| `/status` | Show environment status |
| `/test` | Run pytest suite |

## End-of-Session Protocol

Before ending any session:
1. Verify `npm run build` and `npm run lint` pass (if frontend changed)
2. Verify `python3.12 -m pytest tests/` passes (if backend changed)
3. Update version in CLAUDE.md if release was cut
4. Flag open items for next session

## Code Style

- Python 3.12+, line length 120
- Ruff rules: `E, F, I, W` (configured in `pyproject.toml`)
- Black formatting (configured in `pyproject.toml`)
