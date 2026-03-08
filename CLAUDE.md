# CLAUDE.md — compliance-advisor

Project-specific guidance. Global conventions (communication style, git workflow, always/never, code style) are in `~/.claude/CLAUDE.md`.

## Project Identity

- **Repo:** `github.com/chashea/compliance-advisor`, branch `main`
- **Resource group:** `rg-compliance-advisor`
- **Current version:** v1.0.0

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

## Tests

No tests exist yet. `pyproject.toml` configures pytest with `testpaths = ["tests"]`.

## Code Style Overrides

- Line length: **120** (overrides global default)
- Ruff rules: `E, F, I, W`

## Architecture

Multi-tenant GCC compliance workload dashboard. Three independent components share a PostgreSQL database:

1. **Collector** (`collector/`) — Python CLI (`compliance-collect`) that authenticates to GCC tenants via MSAL ROPC, pulls compliance workload data from Microsoft Graph API (eDiscovery, sensitivity labels, retention labels/events, audit log, DLP alerts, protection scopes), and POSTs a payload to the Function App's `/api/ingest` endpoint.

2. **Function App** (`functions/`) — Azure Functions v2 Python (decorator-based, no `function.json` files). All routes defined in `function_app.py`. Two categories:
   - **Ingest** (`/api/ingest`) — FUNCTION-level auth, validates payload via JSON schema (`shared/validation.py`), upserts to PostgreSQL (`shared/db.py`).
   - **Dashboard APIs** (`/api/advisor/*`, 10 endpoints) — ANONYMOUS auth, all POST with optional `{department}` filter. SQL queries in `shared/dashboard_queries.py`. Two AI endpoints (`briefing`, `ask`) use `shared/ai_agent.py` → Azure OpenAI GPT-4o.
   - **Timer** (`compute_aggregates`) — daily 6am UTC, rolls up workload counts → `compliance_trend`.

3. **Dashboard** (`dashboard/`) — Static HTML/CSS/JS SPA. Config in `env.js` (`window.COMPLIANCE_API_BASE`, `window.COMPLIANCE_API_KEY`). No build step. Has built-in demo data mode toggled by checkbox.

**Database**: PostgreSQL with 9 tables: `tenants`, `ediscovery_cases`, `sensitivity_labels`, `retention_labels`, `retention_events`, `audit_records`, `dlp_alerts`, `protection_scopes`, `compliance_trend`. Schema in `sql/schema.sql`. Connection pool via psycopg2 `ThreadedConnectionPool` in `shared/db.py`.

**Infrastructure** (`infra/`): Bicep modules for PostgreSQL Flexible Server, Function App + App Service Plan, Key Vault, Azure OpenAI, Log Analytics + App Insights. Function App uses SystemAssigned managed identity with RBAC for Key Vault and OpenAI. `azuredeploy.json` at repo root is the compiled ARM template for the "Deploy to Azure" button.

## Key File Paths

| Component | File | Purpose |
|---|---|---|
| Function App | `functions/function_app.py` | All route definitions |
| DB layer | `functions/shared/db.py` | PostgreSQL connection pool + upserts |
| Dashboard queries | `functions/shared/dashboard_queries.py` | SQL for all dashboard endpoints |
| AI agent | `functions/shared/ai_agent.py` | Azure OpenAI GPT-4o integration |
| Validation | `functions/shared/validation.py` | JSON schema validation for ingest |
| Function config | `functions/shared/config.py` | `FunctionSettings` (pydantic-settings) |
| Collector client | `collector/compliance_client.py` | Graph API calls for 7 compliance workloads |
| Collector config | `collector/config.py` | `CollectorSettings` (pydantic-settings) |
| Payload | `collector/payload.py` | `CompliancePayload` dataclass |
| DB schema | `sql/schema.sql` | PostgreSQL table definitions |
| Infra entry | `infra/main.bicep` | Bicep entry point |
| CI/CD | `.github/workflows/deploy.yml` | OIDC deploy to Azure Functions |
| Dashboard config | `dashboard/env.js` | `COMPLIANCE_API_BASE`, `COMPLIANCE_API_KEY` |

## Key Design Decisions

- All dashboard API routes are POST (not GET) — body contains optional filters.
- DATABASE_URL is stored in Key Vault; Function App references it via `@Microsoft.KeyVault(...)` app setting — never in plain text.
- Collector uses ROPC (service account) auth — non-interactive, per-tenant credentials stored in Key Vault.
- Config uses pydantic-settings: `functions/shared/config.py` (`FunctionSettings`) and `collector/config.py` (`CollectorSettings`).
- Audit log API is async: POST query → poll status → GET records.
- Sensitivity labels use beta API with v1.0 fallback.

## CI/CD

GitHub Actions (`.github/workflows/deploy.yml`): push to `main` → deploy Functions via `Azure/functions-action@v1`. Uses OIDC federated credentials (no stored secrets). Schema migration and deploy steps are conditional on secrets being set.

## Code Style

- Python 3.11+, line length 120
- Ruff rules: E, F, I, W
- Black formatting
- Use `ruff` (lint), `black` (format), `mypy` (types), `pytest` (tests)
- Fix all lint/type errors before committing
- Don't add docstrings, comments, or type annotations to code not being changed
- Don't add features, error handling, or abstractions beyond what was asked

## Communication Style

- Be concise. Short bullet summaries after completing work.
- No emojis in prose. `✅`/`❌` in tables/checklists only.
- No unsolicited opinions or suggestions — just do what was asked.
- When presenting multiple options or tasks, number them so I can select by number.

## Git / GitHub Workflow

After every meaningful change:

1. Stage specific files (never `git add -A` or `git add .` indiscriminately).
2. Commit using HEREDOC format with a conventional prefix (`fix:`, `feat:`, `docs:`, `chore:`, `style:`):
   ```
   git commit -m "$(cat <<'EOF'
   feat: describe the change

   Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
   EOF
   )"
   ```
3. Push to `main`.
4. Bump the version (semantic versioning: patch for fixes, minor for features).
5. Create a GitHub release:
   ```
   gh release create vX.Y.Z --repo chashea/compliance-advisor --title "vX.Y.Z" --notes "..."
   ```
   Release notes should be a markdown bullet list of what changed.
6. Confirm with: `**vX.Y.Z** is live — <release URL>`.

**GitHub account:** `chashea` — repo at `github.com/chashea/compliance-advisor`, branch `main`.

## Always / Never

**Always:**
- Automate everything — no manual data ingestion steps.
- When reviewing the repo and asked "what's next," produce a numbered priority list.
- Remove things completely when told to — don't leave dead code behind.
- Keep readme up to date when changes are made.

**Never:**
- Invent or fabricate scores/metrics — only surface real data from APIs.
- Add unsolicited features or "improvements."
- Over-engineer demos — pull back security for demo/dev environments when asked.
- Use `--no-verify` or skip hooks unless explicitly asked.
