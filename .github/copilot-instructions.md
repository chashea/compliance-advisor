# copilot-instructions.md

Project-specific guidance for GitHub Copilot. See also `.claude/CLAUDE.md` for Claude Code guidance.

## Safety Rules (non-negotiable)

1. All tenants are Microsoft 365 GCC or Commercial — never assume other licensing
2. No document content may leave any tenant
3. No user-level PII may be stored centrally
4. Solution must align to CJIS-aware and sovereign boundary requirements
5. Must be Zero Trust aligned
6. Never fabricate scores/metrics — only surface real data from APIs
7. Never use `--no-verify` or skip hooks unless explicitly asked

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

154 tests across 13 files. Run all with:
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

Multi-tenant compliance workload platform. Three core runtime components share a PostgreSQL database:

1. **Collector** (`collector/`) — Python CLI (`compliance-collect`) that authenticates to tenants via MSAL client credentials (app-only), pulls compliance workload data from Microsoft Graph API (sensitivity labels, retention labels/events, audit log, DLP alerts, IRM alerts, protection scopes, Secure Score with Data category breakdown, improvement actions, subject rights requests, communication compliance, information barriers, compliance assessments, Purview incidents, threat assessments, sensitive info types), and POSTs a payload to the Function App's `/api/ingest` endpoint. DLP and IRM alerts use `/v1.0/security/alerts_v2` filtered by `serviceSource`. Use `--actions-category` (env: `ACTIONS_CATEGORY`, default: `Data`) to control which Secure Score category is collected.

2. **Threat Hunter** (`collector/hunter/`) — AI-powered threat hunting pipeline. Generates KQL queries via Azure OpenAI, executes them against Microsoft Graph's `runHuntingQuery` API, uses AI to analyze results and iteratively refine queries. Templates in `hunter/templates.py`, AI logic in `hunter/ai.py`, Graph client in `hunter/graph.py`.

3. **Function App** (`functions/`) — Azure Functions v2 Python (decorator-based, no `function.json` files). All 27 routes defined in `function_app.py`. Categories:
   - **Ingest** (`/api/ingest`) — FUNCTION-level auth, validates payload via JSON schema (`shared/validation.py`), upserts to PostgreSQL (`shared/db.py`).
   - **Dashboard APIs** (`/api/advisor/*`, 20+ endpoints) — ANONYMOUS auth, all POST with optional `{department}` filter. SQL queries in `shared/dashboard_queries.py`. Includes AI-powered `/advisor/briefing` and `/advisor/ask` endpoints via Azure OpenAI Assistants API (rate-limited: 10 req/60s per IP).
   - **Tenant Management** (`/api/tenants`, `/api/tenants/callback`) — Registration and Azure AD admin consent. Both auto-trigger collection for the new tenant via background thread.
   - **On-demand Collection** (`/api/collect/{tenant_id}`) — FUNCTION-level auth, triggers collection for a single tenant.
   - **Timers** — `collect_tenants` (daily 2am UTC, all registered tenants), `compute_aggregates` (daily 6am UTC, rolls up trend data).

4. **Frontend** (`frontend/`) — React 19 SPA with TypeScript, Vite, Tailwind CSS v4, Recharts, React Router v7. 10 pages mapping to dashboard API endpoints. Has a demo mode (`npm run demo`) that uses mock data without a backend. Deployed to `cadvisor-web-prod` (Azure App Service).

**Database**: PostgreSQL with 24 tables (schema in `sql/schema.sql`). Connection pool via psycopg2 `ThreadedConnectionPool` in `shared/db.py`.

**Infrastructure** (`infra/`): Bicep modules for PostgreSQL Flexible Server, Function App + App Service Plan, Key Vault, Azure OpenAI, Log Analytics + App Insights. Function App uses SystemAssigned managed identity with RBAC for Key Vault and Azure OpenAI (Cognitive Services OpenAI User). `azuredeploy.json` at repo root is the compiled ARM template for the "Deploy to Azure" button.

## Key File Paths

| Component | File | Purpose |
|---|---|---|
| Function App | `functions/function_app.py` | All 27 route/timer definitions |
| DB layer | `functions/shared/db.py` | PostgreSQL connection pool + upserts |
| Dashboard queries | `functions/shared/dashboard_queries.py` | SQL for all dashboard endpoints |
| Validation | `functions/shared/validation.py` | JSON schema validation for ingest |
| AI Advisor | `functions/shared/ai_advisor.py` | Azure OpenAI Assistants API integration |
| Collector client | `collector/compliance_client.py` | Graph API calls for compliance workloads |
| Threat hunter | `collector/hunter/` | AI-powered KQL threat hunting pipeline |
| DB schema | `sql/schema.sql` | PostgreSQL table definitions |
| Infra entry | `infra/main.bicep` | Bicep entry point |
| CI/CD Deploy | `.github/workflows/deploy.yml` | OIDC deploy for infra, Functions, and frontend |

## Key Design Decisions

- All dashboard API routes are POST (not GET) — body contains optional filters.
- DATABASE_URL is stored as a Key Vault reference in Function App app settings (`@Microsoft.KeyVault(SecretUri=...)`). The Function App's SystemAssigned managed identity has `Key Vault Secrets User` RBAC.
- Collector uses client credentials (app-only) auth via MSAL `ConfidentialClientApplication` — `CLIENT_ID` + `CLIENT_SECRET` in `.env`.
- Config uses pydantic-settings: `functions/shared/config.py` (`FunctionSettings`) and `collector/config.py` (`CollectorSettings`).
- Audit log API is async: POST query, poll status, GET records.
- Sensitivity labels: v1.0 GA `dataSecurityAndGovernance/sensitivityLabels` is primary; beta `informationProtection` fallback is deprecated.
- DLP and IRM alerts use `/v1.0/security/alerts_v2` filtered by `serviceSource` (`microsoftDataLossPrevention`, `microsoftInsiderRiskManagement`).
- Improvement actions default to `controlCategory eq 'Data'` via `--actions-category` / `ACTIONS_CATEGORY` env var.
- Secure Score snapshot cross-references `controlScores` with Data category profiles to compute `data_current_score` / `data_max_score`.
- Six beta endpoints remain: info barriers, DLP policies, IRM policies, sensitive info types, compliance assessments, sensitivity labels fallback. Monitor Graph changelog for GA promotions.

## Known Gotchas

1. **Key Vault references may not resolve** — After deployment, `@Microsoft.KeyVault(SecretUri=...)` app settings can fail to resolve due to RBAC propagation delay. `FunctionSettings` has a `model_validator` fallback that fetches secrets directly via `azure-keyvault-secrets` + `DefaultAzureCredential`. If you see `invalid dsn` errors, this is why.
2. **Sensitivity labels beta endpoint is deprecated** — The beta `informationProtection` fallback logs a warning. If the v1.0 `dataSecurityAndGovernance` endpoint fails, check that `SensitivityLabel.Read` permission is granted.
3. **Audit log API is async** — POST to create query, poll status until complete, then GET records. Do not treat it as a synchronous call.
4. **Secure Score `controlScores` filtering** — `controlCategory eq 'Data'` is the default. Changing `--actions-category` affects both improvement actions and the data score calculation. These must stay in sync.
5. **`app-hours.yml` stops apps at 8 PM ET** — If debugging after hours, the Function App and Web App may be stopped. Check `az webapp show --query state` before assuming a deployment failure.
6. **`WEBSITE_RUN_FROM_PACKAGE=1`** — The Function App runs from a zip. Local file writes inside the app won't persist.
7. **Retention labels return 403 with app-only auth** — The `retentionLabels` endpoint doesn't support application permissions. Handled gracefully as empty list.

## CI/CD

GitHub Actions (OIDC, no stored secrets):
- `deploy.yml`: push to `main` → run tests → deploy infra/functions/frontend.
- `app-hours.yml`: hourly scheduler with local-time checks (`America/New_York`) that starts apps at 8:00 AM ET and stops at 8:00 PM ET on weekdays.

## Code Style

- Python 3.12+, line length 120
- Ruff rules: `E, F, I, W` (configured in `pyproject.toml`)
- Black formatting (configured in `pyproject.toml`)
