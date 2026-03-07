# Compliance Advisor

Multi-tenant GCC compliance dashboard that aggregates Microsoft Compliance Manager data across agencies into a single executive view.

## Architecture

```
GCC Tenant A ──┐
GCC Tenant B ──┤  collector/cli.py              Azure Function App
GCC Tenant C ──┘  (ROPC, service account)  ──▶  POST /api/ingest
                  compliance.microsoft.com         │
                                                   ▼
                                             PostgreSQL
                                             (posture_snapshots,
                                              assessments,
                                              improvement_actions)
                                                   │
                  Dashboard (browser)  ◀──── /api/advisor/* (7 endpoints)
                  Entra ID SSO                     │
                                                   ▼
                                             Azure OpenAI (GPT-4o)
                                             (briefing + Q&A)
```

## Features

- Cross-tenant compliance score dashboard with KPI cards and charts
- Agency/department dropdown filter for single-pane view
- Compliance Manager assessment summary with pass/fail rates
- Improvement actions table with point-value scoring (27/9/3/1)
- Week-over-week trend tracking
- AI-powered "Ask the Advisor" Q&A sidebar
- Executive briefing generator for leadership consumption
- Built-in demo data mode for demos without live data

## Prerequisites

- Python 3.11+
- Azure subscription (Commercial)
- Access to GCC tenant(s) with Compliance Manager
- Service account per tenant with Compliance Manager Reader role
- Azure CLI (`az`)

## Local Development

### 1. Set up PostgreSQL

```bash
# Start local Postgres (or use Azure)
createdb compliance_advisor
psql compliance_advisor -f sql/schema.sql
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your values
```

### 3. Run the collector (dry run)

```bash
pip install -e .
compliance-collect \
  --tenant-id <GUID> \
  --agency-id dept-of-education \
  --department Education \
  --display-name "Dept of Education" \
  --dry-run
```

### 4. Run the Function App locally

```bash
cd functions
pip install -r requirements.txt
func start
```

### 5. Serve the dashboard

```bash
python3 -m http.server 8080 --directory dashboard/
```

Open http://localhost:8080. Toggle "Demo data" checkbox for sample data, or point `env.js` at the local Function App.

## Collector Usage

```bash
# Collect from a single tenant
compliance-collect \
  --tenant-id 00000000-0000-0000-0000-000000000000 \
  --agency-id dept-of-finance \
  --department Finance \
  --display-name "Dept of Finance"

# Dry run (print payload, don't submit)
compliance-collect --tenant-id <GUID> --agency-id <NAME> --department <DEPT> --dry-run -v
```

## API Reference

All endpoints are `POST` to `/api/advisor/*`.

| Endpoint | Body | Description |
|---|---|---|
| `/api/advisor/status` | `{}` | Active tenants count, last sync date |
| `/api/advisor/compliance` | `{department?, days?}` | Scores, trends, week-over-week, department rollup |
| `/api/advisor/assessments` | `{department?}` | Assessments, top gaps, control families |
| `/api/advisor/regulations` | `{}` | Regulation coverage summary |
| `/api/advisor/actions` | `{department?}` | Improvement actions, summary, owner breakdown |
| `/api/advisor/briefing` | `{department?}` | AI-generated executive briefing |
| `/api/advisor/ask` | `{question}` | AI Q&A about compliance data |
| `/api/ingest` | Collector payload | Ingestion (function key auth) |

## Scoring Methodology

Compliance scores are pulled from the Compliance Manager portal API (`/api/ComplianceScore`). If unavailable, scores are self-calculated from improvement actions using Microsoft's published point values:

| Action Type | Points |
|---|---|
| Preventative mandatory | 27 |
| Preventative discretionary | 9 |
| Detective mandatory | 3 |
| Detective discretionary | 1 |
| Corrective mandatory | 3 |
| Corrective discretionary | 1 |

See: https://learn.microsoft.com/en-us/purview/compliance-manager-scoring

## Infrastructure Deployment

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2Fchashea%2Fcompliance-advisor%2Fmain%2Fazuredeploy.json)

```bash
# Create resource group
az group create --name rg-compliance-advisor --location eastus

# Deploy infrastructure
az deployment group create \
  --resource-group rg-compliance-advisor \
  --template-file infra/main.bicep \
  --parameters postgresAdminPassword='<PASSWORD>' \
               deployerObjectId='<YOUR-OBJECT-ID>' \
               entraClientId='<APP-CLIENT-ID>' \
               allowedTenantIds='<GUID1>,<GUID2>'

# Run schema migration
psql "$(az deployment group show -g rg-compliance-advisor -n main --query properties.outputs.postgresConnectionString.value -o tsv)" \
  -f sql/schema.sql
```

## Onboarding a New GCC Tenant

1. Create a service account in the GCC tenant with Compliance Manager Reader role
2. Store credentials in Key Vault:
   ```bash
   az keyvault secret set --vault-name <KV_NAME> --name "svc-<agency-id>-username" --value "<UPN>"
   az keyvault secret set --vault-name <KV_NAME> --name "svc-<agency-id>-password" --value "<PASSWORD>"
   ```
3. Add the tenant GUID to `ALLOWED_TENANT_IDS` in the Function App config
4. Run the collector:
   ```bash
   compliance-collect --tenant-id <GUID> --agency-id <NAME> --department <DEPT>
   ```

## Project Structure

```
compliance-advisor/
├── dashboard/          Static HTML/CSS/JS dashboard
├── collector/          Per-tenant data collector (Python CLI)
├── functions/          Azure Functions v2 API backend
├── sql/                PostgreSQL schema
├── infra/              Bicep IaC templates
└── .github/workflows/  CI/CD
```
