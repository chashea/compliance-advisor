# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# Install collector CLI (editable)
pip install -e .

# Run collector (dry run)
compliance-collect --tenant-id <GUID> --agency-id <ID> --department <DEPT> --display-name "<NAME>" --dry-run

# Run Function App locally
cd functions && pip install -r requirements.txt && func start

# Serve dashboard
python3 -m http.server 8080 --directory dashboard/

# Lint
ruff check .

# Format
black .

# Deploy infrastructure
az bicep build --file infra/main.bicep --outfile azuredeploy.json
az deployment group create --resource-group rg-compliance-advisor --template-file infra/main.bicep --parameters postgresAdminPassword='<PW>'
```

No tests exist yet. `pyproject.toml` configures pytest with `testpaths = ["tests"]`.

## Architecture

Multi-tenant GCC compliance dashboard. Three independent components share a PostgreSQL database:

1. **Collector** (`collector/`) — Python CLI (`compliance-collect`) that authenticates to GCC tenants via MSAL ROPC, scrapes Compliance Manager portal API (`/api/ComplianceScore`, `/api/Assessments`, `/api/ImprovementActions`), and POSTs a payload to the Function App's `/api/ingest` endpoint.

2. **Function App** (`functions/`) — Azure Functions v2 Python (decorator-based, no `function.json` files). All routes defined in `function_app.py`. Two categories:
   - **Ingest** (`/api/ingest`) — FUNCTION-level auth, validates payload via JSON schema (`shared/validation.py`), upserts to PostgreSQL (`shared/db.py`).
   - **Dashboard APIs** (`/api/advisor/*`, 7 endpoints) — ANONYMOUS auth, all POST with optional `{department}` filter. SQL queries in `shared/dashboard_queries.py`. Two AI endpoints (`briefing`, `ask`) use `shared/ai_agent.py` → Azure OpenAI GPT-4o.
   - **Timer** (`compute_aggregates`) — daily 6am UTC, rolls up `posture_snapshots` → `compliance_trend`.

3. **Dashboard** (`dashboard/`) — Static HTML/CSS/JS SPA. Config in `env.js` (`window.COMPLIANCE_API_BASE`, `window.COMPLIANCE_API_KEY`). No build step. Has built-in demo data mode toggled by checkbox.

**Database**: PostgreSQL with 5 tables: `tenants`, `posture_snapshots`, `assessments`, `improvement_actions`, `compliance_trend`. Schema in `sql/schema.sql`. Connection pool via psycopg2 `ThreadedConnectionPool` in `shared/db.py`.

**Infrastructure** (`infra/`): Bicep modules for PostgreSQL Flexible Server, Function App + App Service Plan, Key Vault, Azure OpenAI, Log Analytics + App Insights. Function App uses SystemAssigned managed identity with RBAC for Key Vault and OpenAI. `azuredeploy.json` at repo root is the compiled ARM template for the "Deploy to Azure" button.

## Key Design Decisions

- All dashboard API routes are POST (not GET) — body contains optional filters.
- DATABASE_URL is stored in Key Vault; Function App references it via `@Microsoft.KeyVault(...)` app setting — never in plain text.
- Collector uses ROPC (service account) auth — non-interactive, per-tenant credentials stored in Key Vault.
- Config uses pydantic-settings: `functions/shared/config.py` (`FunctionSettings`) and `collector/config.py` (`CollectorSettings`).

## CI/CD

GitHub Actions (`.github/workflows/deploy.yml`): push to `main` → deploy Functions via `Azure/functions-action@v1`. Uses OIDC federated credentials (no stored secrets). Schema migration and deploy steps are conditional on secrets being set.

## Code Style

- Python 3.11+, line length 120
- Ruff rules: E, F, I, W
- Black formatting
