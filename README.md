# Compliance Advisor

Multi-tenant GCC compliance workload dashboard that aggregates Microsoft 365 compliance data across agencies into a single executive view.

## Architecture

```
GCC Tenant A ──┐
GCC Tenant B ──┤  collector/cli.py              Azure Function App
GCC Tenant C ──┘  (ROPC, service account)  ──▶  POST /api/ingest
                  Microsoft Graph API              │
                                                   ▼
                                             PostgreSQL
                                             (ediscovery_cases,
                                              sensitivity_labels,
                                              retention_labels,
                                              dlp_alerts, ...)
                                                   │
                  Dashboard (browser)  ◀──── /api/advisor/* (10 endpoints)
                  Entra ID SSO                     │
                                                   ▼
                                             Azure OpenAI (GPT-4o)
                                             (briefing + Q&A)
```

## Compliance Workloads

| Workload | Data Source | API |
|---|---|---|
| eDiscovery | Cases, custodians, holds | `/security/cases/ediscoveryCases` |
| Information Protection | Sensitivity labels | `/security/informationProtection/sensitivityLabels` |
| Records Management | Retention labels & events | `/security/labels/retentionLabels`, `/security/triggers/retentionEvents` |
| Audit Log | Compliance activity records | `/security/auditLog/queries` (async) |
| DLP (Data Security) | DLP alerts | `/security/alerts_v2` (filtered to DLP) |
| Data Security & Governance | Protection scopes | `/dataSecurityAndGovernance/protectionScopes/compute` |

## Features

- Cross-tenant compliance workload dashboard with KPI cards and charts
- Agency/department dropdown filter for single-pane view
- Active filter state summary with clear reset action
- eDiscovery case tracking with custodian counts
- Sensitivity and retention label inventory
- DLP alert monitoring with severity breakdown
- Audit log activity summaries by service and operation
- Data governance protection scope visibility
- Compliance trend tracking over time
- AI-powered "Ask the Advisor" Q&A sidebar
- Executive briefing generator for leadership consumption
- Built-in demo data mode for demos without live data

## Prerequisites

- Python 3.11+
- Azure subscription (Commercial)
- Access to GCC tenant(s) with Microsoft 365 compliance workloads
- Service account per tenant with appropriate Graph API permissions
- Azure CLI (`az`)

### Required Graph API Permissions

| Permission | Workload |
|---|---|
| `eDiscovery.Read.All` | eDiscovery cases |
| `InformationProtectionPolicy.Read.All` | Sensitivity labels |
| `RecordsManagement.Read.All` | Retention labels & events |
| `AuditLogsQuery.Read.All` | Audit log queries |
| `SecurityAlert.Read.All` | DLP alerts |
| `Content.Process.All` | Data security & governance |

## Local Development

### 1. Set up PostgreSQL

```bash
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
Use the **Clear filters** button to reset Department and Trend period back to the default dashboard view.

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
| `/api/advisor/overview` | `{department?}` | KPI summary (cases, labels, alerts, audit) |
| `/api/advisor/ediscovery` | `{department?}` | eDiscovery cases and status breakdown |
| `/api/advisor/labels` | `{department?}` | Sensitivity labels, retention labels, events |
| `/api/advisor/audit` | `{department?}` | Audit log records, service/operation breakdown |
| `/api/advisor/dlp` | `{department?}` | DLP alerts, severity/policy breakdown |
| `/api/advisor/governance` | `{department?}` | Protection scopes |
| `/api/advisor/trend` | `{department?, days?}` | Compliance workload counts over time |
| `/api/advisor/briefing` | `{department?}` | AI-generated executive briefing |
| `/api/advisor/ask` | `{question}` | AI Q&A about compliance data |
| `/api/ingest` | Collector payload | Ingestion (function key auth) |

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

1. Create a service account in the GCC tenant with the required Graph API permissions
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
