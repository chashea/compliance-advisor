# Compliance Advisor — Multi-Tenant Microsoft Purview Dashboard on Azure AI Foundry

An AI-powered compliance advisor that aggregates Microsoft Secure Score data
across multiple M365 tenants and delivers natural-language insights via
Azure AI Foundry Prompt Flows.

## Architecture

```
M365 Tenants (Graph API)
        │
        ▼
Azure Durable Functions (daily fan-out)
        │
        ▼
Azure SQL  ──►  Azure AI Search  ──►  Azure AI Foundry (GPT-4o)
                                              │
                              ┌───────────────┼───────────────┐
                              ▼               ▼               ▼
                      CISO Dashboard    Teams Bot        REST API
                      (Static Web App)
```

## Quick Start

### 1. Deploy Infrastructure
```bash
cd infra

terraform init

terraform apply \
  -var="env=prod" \
  -var="sql_admin_username=sqladmin" \
  -var="sql_admin_password=<password>"
```

### 2. Apply SQL Schema
```bash
sqlcmd -S <server>.database.windows.net -d ComplianceAdvisor -i sql/schema.sql
```

### 3. Create AI Search Indexes and Seed Framework Data
```bash
pip install azure-search-documents azure-identity azure-keyvault-secrets

# Create index schemas
python scripts/setup_search_index.py \
  --endpoint https://<search-name>.search.windows.net \
  --key <admin-key>

# Seed the compliance-frameworks index with NIST, ISO 27001, SOC 2, CIS data
export AZURE_SEARCH_ENDPOINT=https://<search-name>.search.windows.net
export AZURE_SEARCH_KEY=<admin-key>
python scripts/seed_frameworks_index.py
```

### 4. Onboard Your First Tenant

In each source M365 tenant, create an App Registration:
- **API permission**: `SecurityEvents.Read.All` (Application)
- Grant admin consent
- Create a client secret

Then run:
```bash
chmod +x scripts/onboard_tenant.sh
./scripts/onboard_tenant.sh \
  --tenant-id      "<entra-tenant-guid>" \
  --display-name   "Contoso Europe" \
  --region         "EU" \
  --department     "Finance" \
  --department-head "Jane Smith" \
  --risk-tier      "High" \
  --app-id         "<app-registration-client-id>" \
  --key-vault      "kv-compliance-advisor-prod" \
  --sql-server     "sql-compliance-advisor-prod.database.windows.net" \
  --sql-db         "ComplianceAdvisor"
```

The client secret is read from **stdin** (not a CLI flag) to avoid appearing in
shell history or process listings.

## Dashboard

A lightweight CISO-facing dashboard that visualises posture, trends, and
department-level breakdowns using Chart.js.

### Run Locally

```bash
# From the repo root – any static file server works
npx serve dashboard/
# or
python -m http.server 8080 --directory dashboard
```

Open `http://localhost:8080` (or whichever port your server reports).

By default the dashboard assumes the API is at the same origin. To point at a
remote Function App for local development, edit `dashboard/env.js`:
```js
window.COMPLIANCE_API_BASE = "https://<your-function-app>.azurewebsites.net/api/advisor";
window.COMPLIANCE_API_KEY  = "<your-function-key>";  // omit when using SWA auth
```

In production, CI/CD generates `env.js` automatically from the Terraform outputs.

### Deploy as Azure Static Web App

The `dashboard/` folder is ready to deploy as an Azure Static Web App:

```bash
az staticwebapp create \
  --name swa-compliance-dashboard \
  --resource-group rg-compliance-advisor \
  --source . \
  --app-location dashboard \
  --output-location dashboard

# Link the Function App as the API backend
az staticwebapp backends link \
  --name swa-compliance-dashboard \
  --resource-group rg-compliance-advisor \
  --backend-resource-id /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.Web/sites/<func-app>
```

The included `staticwebapp.config.json` enforces Entra ID authentication on
API routes and adds security headers (CSP, X-Frame-Options, etc.).

## Prompt Flow: Compliance Advisor

Ask natural-language questions about your compliance posture:

- *"What are our top 5 gaps against NIST 800-53?"*
- *"Which tenant has the lowest score this week?"*
- *"Summarize our Identity controls across all tenants."*
- *"Which improvement actions would gain us the most points?"*

## Prompt Flow: Executive Briefing

Generates a structured CISO briefing for leadership consumption:

- Enterprise posture summary with week-over-week trends
- Department/agency scorecard with risk-tier breakdown
- Top recommended actions prioritized by business impact
- Risk escalations requiring leadership attention

Call via the HTTP API:
```bash
curl -X POST https://<function-app>.azurewebsites.net/api/advisor/briefing \
  -H "x-functions-key: <function-key>" \
  -H "Content-Type: application/json" \
  -d '{"department": "Finance"}'     # optional — omit for enterprise-wide
```

## HTTP API

The compliance advisor exposes a REST API for dashboards, bots, and integrations:

| Endpoint | Description |
|----------|-------------|
| `POST /api/advisor/ask` | Ask the AI advisor a natural-language question |
| `POST /api/advisor/briefing` | Generate an executive briefing (optionally filtered by department) |
| `POST /api/advisor/compliance` | Compliance Manager scores, trends, and week-over-week changes |
| `POST /api/advisor/assessments` | Assessment summary, control pass rates, and top gaps |
| `POST /api/advisor/regulations` | Regulation coverage — pass rates per framework across all tenants |
| `POST /api/advisor/actions` | Improvement actions with implementation steps and test plans |
| `POST /api/advisor/trends` | Secure Score trends, week-over-week changes, and category breakdowns |
| `POST /api/advisor/departments` | Department/agency rollup with risk-tier summary |
| `POST /api/advisor/status` | Health check — tenant count and sync timestamps |

## Prompt Flow: Weekly Digest

Scheduled flow that posts a GPT-4o generated summary to Teams every Monday.

The Teams webhook URL is read at runtime from Key Vault (`teams-webhook-url` secret).
Store it once with:
```bash
az keyvault secret set \
  --vault-name kv-compliance-advisor-prod \
  --name       teams-webhook-url \
  --value      "<your-teams-incoming-webhook-url>"
```

The schedule (every Monday at 08:00 UTC) is configured automatically on each deploy
via `scripts/configure_weekly_schedule.py`. To configure it manually:
```bash
export AZURE_SUBSCRIPTION_ID=<sub-id>
export AZURE_RESOURCE_GROUP=rg-compliance-advisor-prod
export AI_FOUNDRY_WORKSPACE=aip-compliance-advisor-prod
python scripts/configure_weekly_schedule.py
```

## CI/CD

Push to `main` triggers the GitHub Actions workflow which:
1. Runs unit tests, Terraform security scan, and dependency audit in parallel
2. Deploys Terraform infrastructure (manual approval gate)
3. Creates/updates AI Search indexes and seeds framework data
4. Deploys Azure Functions
5. Deploys Prompt Flows to AI Foundry and configures the weekly digest schedule
6. Deploys the CISO dashboard to Azure Static Web Apps

**Required GitHub Secrets:**

| Secret | Description |
|--------|-------------|
| `SQL_ADMIN_USER` | SQL server admin username |
| `SQL_ADMIN_PASSWORD` | SQL server admin password |
| `AZURE_SEARCH_ADMIN_KEY` | AI Search admin key |
| `AI_FOUNDRY_WORKSPACE` | AI Foundry project workspace name |
| `SWA_DEPLOYMENT_TOKEN` | Static Web App deployment token (`az staticwebapp secrets list`) |

**Required GitHub Variables (`vars.`):**

| Variable | Description |
|----------|-------------|
| `AZURE_CLIENT_ID` | Service principal / managed identity client ID (OIDC federation) |
| `AZURE_TENANT_ID` | Entra ID tenant ID |
| `AZURE_SUBSCRIPTION_ID` | Azure subscription ID |
| `FUNCTION_SUBNET_ID` | VNet subnet resource ID for Function App VNet integration |
| `SECURITY_ALERT_EMAILS` | Comma-separated emails for SQL security alerts |
| `CORS_ALLOWED_ORIGINS` | Comma-separated allowed origins for the Function App |

The pipeline uses **OIDC federation** — no long-lived credentials are stored as secrets.
The service principal needs **Contributor** on the resource group and **User Access Administrator**
to assign the Key Vault Secrets User role to the Function App's managed identity.

## Project Structure

```
compliance-advisor/
├── infra/                  # Terraform IaC (Key Vault, SQL, Search, Functions)
├── src/
│   ├── functions/          # Azure Durable Functions (timer, orchestrator, activities, HTTP API)
│   └── shared/             # auth, graph_client, sql_client helpers
├── sql/                    # Schema, views, trend queries
├── prompt_flows/
│   ├── compliance_advisor/ # RAG Q&A agent
│   ├── executive_briefing/ # CISO executive briefing generator
│   └── weekly_digest/      # Scheduled Teams report with trends
├── dashboard/              # CISO dashboard (Chart.js static web app)
├── scripts/
│   ├── onboard_tenant.sh            # Tenant onboarding runbook
│   ├── offboard_tenant.sh           # Tenant offboarding / deactivation
│   ├── setup_search_index.py        # Create AI Search index schemas
│   ├── seed_frameworks_index.py     # Seed compliance-frameworks index
│   └── configure_weekly_schedule.py # Configure weekly digest cron schedule
└── .github/workflows/      # CI/CD pipeline
```
