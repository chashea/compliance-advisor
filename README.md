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

### 3. Create AI Search Indexes
```bash
pip install azure-search-documents
python scripts/setup_search_index.py \
  --endpoint https://<search-name>.search.windows.net \
  --key <admin-key>
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

### 5. Upload Compliance Manager Data (Optional)

Export from Compliance Manager UI:
> Improvement actions → Export actions → Save .xlsx

Then call the ingestion API (or upload via the portal UI you build on top):
```python
from src.ingestion.cm_parser import parse_and_store

with open("cm_export.xlsx", "rb") as f:
    rows = parse_and_store(tenant_id="<guid>", xlsx_bytes=f.read())
print(f"Loaded {rows} improvement actions")
```

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
remote Function App, edit `CONFIG.apiBase` in `dashboard/app.js`:
```js
const CONFIG = {
  apiBase: "https://<your-function-app>.azurewebsites.net",
  functionKey: "<your-function-key>"
};
```

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
| `POST /api/advisor/trends` | Get score trends, week-over-week changes, and category breakdowns |
| `POST /api/advisor/departments` | Get department/agency rollup with risk-tier summary |
| `POST /api/advisor/status` | Health check — tenant count and sync timestamps |

## Prompt Flow: Weekly Digest

Scheduled flow that posts a GPT-4o generated summary to Teams every Monday.

Configure the Teams webhook URL in AI Foundry as a scheduled run input.

## CI/CD

Push to `main` triggers the GitHub Actions workflow which:
1. Deploys Terraform infrastructure
2. Creates/updates AI Search indexes
3. Deploys Azure Functions
4. Deploys Prompt Flows to AI Foundry

**Required GitHub Secrets:**

| Secret | Description |
|--------|-------------|
| `AZURE_CREDENTIALS` | Service principal JSON (`az ad sp create-for-rbac --sdk-auth`) |
| `SQL_ADMIN_USER` | SQL server admin username |
| `SQL_ADMIN_PASSWORD` | SQL server admin password |
| `AZURE_SEARCH_ADMIN_KEY` | AI Search admin key |
| `AI_FOUNDRY_WORKSPACE` | AI Foundry workspace name |

The service principal in `AZURE_CREDENTIALS` needs **Contributor** on the resource group and **User Access Administrator** to assign the Key Vault role to the Function App's managed identity.

## Project Structure

```
compliance-advisor/
├── infra/                  # Terraform IaC (Key Vault, SQL, Search, Functions)
├── src/
│   ├── functions/          # Azure Durable Functions (timer, orchestrator, activities, HTTP API)
│   ├── shared/             # auth, graph_client, sql_client helpers
│   └── ingestion/          # Compliance Manager Excel parser
├── sql/                    # Schema, views, trend queries
├── prompt_flows/
│   ├── compliance_advisor/ # RAG Q&A agent
│   ├── executive_briefing/ # CISO executive briefing generator
│   └── weekly_digest/      # Scheduled Teams report with trends
├── dashboard/              # CISO dashboard (Chart.js static web app)
├── scripts/
│   ├── onboard_tenant.sh   # Tenant onboarding runbook
│   └── setup_search_index.py
└── .github/workflows/      # CI/CD pipeline
```
