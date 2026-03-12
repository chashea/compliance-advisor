# Copilot Instructions — compliance-advisor

## Build, Test, Lint

```bash
# Install collector CLI (editable)
pip install -e .

# Lint
ruff check .

# Format
black .

# Run all tests (49 tests)
python3.12 -m pytest tests/

# Run a single test file
python3.12 -m pytest tests/test_validation.py

# Run a single test by name
python3.12 -m pytest tests/test_validation.py -k "test_valid_payload"

# Run Function App locally
cd functions && pip install -r requirements.txt && func start

# Build Bicep → ARM
az bicep build --file infra/main.bicep --outfile azuredeploy.json
```

## Architecture

Multi-tenant GCC compliance platform. Two core runtime components share a PostgreSQL database (16 tables, schema in `sql/schema.sql`):

1. **Collector** (`collector/`) — Python CLI (`compliance-collect`) that authenticates to GCC tenants via MSAL client credentials, pulls 14 compliance workloads from Microsoft Graph API, and POSTs a JSON payload to the Function App's `/api/ingest` endpoint.

2. **Function App** (`functions/`) — Azure Functions v2 Python using decorator-based routing (no `function.json` files). All routes defined in `function_app.py`. Three categories:
   - **Ingest** (`/api/ingest`) — function-key auth, validates payload via JSON schema (`shared/validation.py`), upserts to PostgreSQL (`shared/db.py`).
   - **Dashboard APIs** (`/api/advisor/*`, 16 endpoints) — anonymous auth, all POST with optional `{department}` filter. SQL queries in `shared/dashboard_queries.py`. Two AI endpoints (`briefing`, `ask`) use `shared/ai_agent.py` → Azure AI Foundry Agent Service.
   - **Timer** (`compute_aggregates`) — daily 6am UTC, rolls up workload counts to `compliance_trend`.

**Infrastructure** (`infra/`): Bicep modules for PostgreSQL Flexible Server, Function App, Key Vault, Azure OpenAI, Log Analytics + App Insights. Function App uses SystemAssigned managed identity with RBAC for Key Vault and OpenAI. `azuredeploy.json` at repo root is the compiled ARM template.

## Key Conventions

- **All dashboard API routes are POST** (not GET) — body contains optional filters.
- **Config via pydantic-settings**: `functions/shared/config.py` (`FunctionSettings`) and `collector/config.py` (`CollectorSettings`). Environment variables, not config files.
- **DATABASE_URL** is a Key Vault reference in Function App settings. The managed identity has `Key Vault Secrets User` RBAC.
- **DLP and IRM alerts** use the legacy `/v1.0/security/alerts` endpoint filtered by `vendorInformation/provider` — not `alerts_v2`.
- **Sensitivity labels** use beta API with v1.0 fallback.
- **Audit log API is async**: POST query → poll status → GET records.
- **Improvement actions** default to `controlCategory eq 'Data'` via `--actions-category` / `ACTIONS_CATEGORY` env var.
- **Tests** add `functions/` to `sys.path` via `conftest.py` so `shared.*` imports resolve.
- **Python 3.11+**, line length **120**, Ruff rules `E, F, I, W`, Black formatting.
- **CI/CD**: GitHub Actions OIDC deploy to Azure Functions on push to `main` (`.github/workflows/deploy.yml`).

## Code Style

- Don't add docstrings, comments, or type annotations to code not being changed.
- Don't add features, error handling, or abstractions beyond what was asked.
- Fix all lint/type errors before committing.
