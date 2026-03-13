# Copilot Instructions — compliance-advisor

## Build, Test, and Lint

```bash
# Backend setup
pip install -e .

# Python lint/format
ruff check .
black .

# Run all backend tests
python3.11 -m pytest tests/

# Run one test file
python3.11 -m pytest tests/test_validation.py

# Run one specific test
python3.11 -m pytest tests/test_validation.py::test_valid_payload_no_allowlist

# Run Function App locally
cd functions && pip install -r requirements.txt && func start

# Frontend local dev
cd frontend && npm install --legacy-peer-deps && npm run dev

# Frontend lint/build
cd frontend && npm run lint
cd frontend && npm run build

# Build Bicep -> ARM template
az bicep build --file infra/main.bicep --outfile azuredeploy.json

# Apply DB schema locally
createdb compliance_advisor && psql compliance_advisor -f sql/schema.sql
```

## High-Level Architecture

Compliance Advisor is a multi-tenant ingestion + analytics platform with three runtime components over one PostgreSQL schema (`sql/schema.sql`, 17 tables).

1. **Collector CLI** (`collector/`)
   - Entrypoint: `compliance-collect` (`collector/cli.py`).
   - Uses MSAL client credentials, collects 14 compliance workloads from Microsoft Graph, then POSTs a single payload to Function App `/api/ingest`.
   - Supports `--actions-category` (default `Data`) for Secure Score improvement actions.

2. **Function App API** (`functions/function_app.py`)
   - Azure Functions v2 decorator model; all routes are defined in one file.
   - `/api/ingest` (FUNCTION auth) validates payload and upserts to PostgreSQL.
   - `/api/advisor/*` endpoints (ANONYMOUS auth) serve dashboard responses.
   - `compute_aggregates` timer runs daily at `0 0 6 * * *` (6 AM UTC) and writes rollups to `compliance_trend`.

3. **Frontend SPA** (`frontend/`)
   - React + TypeScript + Vite app.
   - Uses `frontend/src/api/client.ts` helper that always POSTs to `/api/advisor/{endpoint}`.
   - `VITE_API_BASE_URL` overrides API host; otherwise dev proxy targets production Function App (see `frontend/vite.config.ts`).

4. **Data model + query layer**
   - Ingestion writes snapshot-based records keyed by `snapshot_date` and entity identifiers.
   - Dashboard SQL lives in `functions/shared/dashboard_queries.py` and generally reads latest snapshots via `MAX(snapshot_date)` queries.
   - Ingestion dedupes via SHA256 payload hash in `ingestion_log`.

5. **Infrastructure + CI/CD**
   - `infra/main.bicep` provisions PostgreSQL Flexible Server, Function App, Key Vault, Azure OpenAI resources, and monitoring.
   - `.github/workflows/deploy.yml` runs lint/tests first, then OIDC-based infra/function/frontend deployment.
   - `.github/workflows/app-hours.yml` controls weekday ET start/stop scheduling for Function App and Web App.

## Key Conventions

- **Dashboard endpoints are POST-only** and take optional `{ "department": "..." }` filters.
- **Auth split is intentional:** `/api/ingest` requires function key (`x-functions-key`), `/api/advisor/*` is anonymous.
- **Config is env-first with pydantic-settings:** `collector/config.py` and `functions/shared/config.py`; both load from `.env`.
- **Tenant allow-list behavior:** `ALLOWED_TENANT_IDS=""` means allow all (dev mode); non-empty values enforce validation in `shared/validation.py`.
- **Graph API quirks to preserve:**
  - DLP + IRM use legacy `/v1.0/security/alerts` with `vendorInformation/provider` filters.
  - Sensitivity labels call beta endpoint first, then v1.0 fallback.
  - Audit log is async: create query -> poll status -> fetch records.
  - Protection scopes use `POST /dataSecurityAndGovernance/protectionScopes/compute`.
- **DB writes are idempotent:** ingestion duplicate check + `ON CONFLICT` upserts.
- **Tests rely on import path bootstrap:** `tests/conftest.py` inserts `functions/` into `sys.path` so `shared.*` imports resolve.
- **Repo formatting/lint baselines:** Python 3.11+, line length 120, Ruff `E,F,I,W`, Black formatting; frontend lint uses ESLint.
- **Operational schedule:** `app-hours.yml` evaluates `America/New_York` local time hourly and applies weekday 9:00 AM start / 8:00 PM stop for both apps.
- **Scope discipline:** avoid unrelated refactors or feature additions in routine fixes.
