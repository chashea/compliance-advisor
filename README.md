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
                                             (15 tables: tenants,
                                              ediscovery, labels, dlp,
                                              irm, audit, scores, ...)
                                                   │
                  Dashboard (browser)  ◀──── /api/advisor/* (16 endpoints)
                                                   │
                                                   ▼
                                             Azure OpenAI (GPT-4o)
                                             (briefing + Q&A)
```

## Compliance Workloads

| Workload | Data Source | API |
|---|---|---|
| eDiscovery | Cases, custodians, holds | `/security/cases/ediscoveryCases` |
| Information Protection | Sensitivity labels | `/beta/security/informationProtection/sensitivityLabels` |
| Records Management | Retention labels & events | `/security/labels/retentionLabels`, `/security/triggers/retentionEvents` |
| Audit Log | Compliance activity records | `/security/auditLog/queries` (async) |
| DLP | DLP alerts from Defender | `/security/alerts` filtered by `vendorInformation/provider eq 'Microsoft Data Loss Prevention'` |
| Insider Risk Management | IRM alerts from Defender | `/security/alerts` filtered by `vendorInformation/provider eq 'Microsoft Insider Risk Management'` |
| Data Security & Governance | Protection scopes | `/dataSecurityAndGovernance/protectionScopes/compute` |
| Secure Score | Overall + Data category score | `/security/secureScores` + `/security/secureScoreControlProfiles` |
| Improvement Actions | Secure Score control profiles (Data category) | `/security/secureScoreControlProfiles?$filter=controlCategory eq 'Data'` |
| Subject Rights Requests | Privacy/DSAR requests | `/beta/privacy/subjectRightsRequests` |
| Communication Compliance | Policy monitoring | `/beta/security/communicationCompliance/policies` |
| Information Barriers | Segment policies | `/beta/identityGovernance/informationBarriers/policies` |

> **Note:** DLP and IRM alerts use the legacy `/v1.0/security/alerts` endpoint (not `alerts_v2`) because IRM alerts have no valid `serviceSource` enum in `alerts_v2` and DLP alerts surface more reliably via the Defender product name filter.

## Features

- Cross-tenant compliance workload dashboard with KPI cards (Tenants, Secure Score Data, DLP Alerts, IRM Alerts)
- Secure Score Data category KPI showing `current / max` points and percentage
- Improvement Actions filtered to Data category by default with category/cost/tier filters
- Agency/department dropdown filter with active filter state summary and clear reset
- DLP alert monitoring with inline severity chart and severity/status/tenant filters
- Insider Risk Management alert monitoring with severity/status filters
- eDiscovery case tracking with custodian counts
- Sensitivity and retention label inventory
- Subject Rights Request tracking
- Communication Compliance policy monitoring
- Information Barriers policy visibility
- Audit log activity summaries by service and operation
- Data governance protection scope visibility
- AI-powered "Ask the Advisor" Q&A sidebar
- Executive briefing generator for leadership consumption
- Built-in demo data mode with 5 sample departments (IT, Legal, HR, Finance, Compliance)

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
| `SecurityAlert.Read.All` | DLP alerts, IRM alerts |
| `SecurityEvents.Read.All` | Secure Score, Improvement Actions |
| `Content.Process.All` | Data security & governance |
| `SubjectRightsRequest.Read.All` | Subject rights requests |
| `InformationBarriersPolicy.Read.All` | Information barriers |

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

## Collector Usage

```bash
# Collect from a single tenant (Improvement Actions default to Data category)
compliance-collect \
  --tenant-id 00000000-0000-0000-0000-000000000000 \
  --agency-id dept-of-finance \
  --department Finance \
  --display-name "Dept of Finance"

# Override Improvement Actions category
compliance-collect --tenant-id <GUID> --agency-id <NAME> --department <DEPT> \
  --actions-category Identity

# Collect all Improvement Action categories
compliance-collect --tenant-id <GUID> --agency-id <NAME> --department <DEPT> \
  --actions-category ""

# Dry run (print payload, don't submit)
compliance-collect --tenant-id <GUID> --agency-id <NAME> --department <DEPT> --dry-run -v
```

### Collector Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TENANT_ID` | — | Target tenant GUID |
| `AGENCY_ID` | — | Logical agency identifier |
| `DEPARTMENT` | — | Department name |
| `DISPLAY_NAME` | — | Human-readable tenant name |
| `ACTIONS_CATEGORY` | `Data` | Secure Score control category filter |
| `AUDIT_LOG_DAYS` | `1` | Audit log lookback window (days) |

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
| `/api/advisor/irm` | `{department?}` | Insider Risk Management alerts |
| `/api/advisor/governance` | `{department?}` | Protection scopes, Secure Score (overall + Data category) |
| `/api/advisor/trend` | `{department?, days?}` | Compliance workload counts over time |
| `/api/advisor/actions` | `{department?}` | Secure Score + improvement actions |
| `/api/advisor/subject-rights` | `{department?}` | Subject rights requests |
| `/api/advisor/comm-compliance` | `{department?}` | Communication compliance policies |
| `/api/advisor/info-barriers` | `{department?}` | Information barrier policies |
| `/api/advisor/briefing` | `{department?}` | AI-generated executive briefing |
| `/api/advisor/ask` | `{question}` | AI Q&A about compliance data |
| `/api/ingest` | Collector payload | Ingestion (function key auth) |

### `/api/advisor/governance` response shape (secure_score)

```json
{
  "secure_score": {
    "current_score": 142.0,
    "max_score": 500.0,
    "score_date": "2026-03-08",
    "data_current_score": 38.0,
    "data_max_score": 85.0
  }
}
```

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
psql "<CONNECTION_STRING>" -f sql/schema.sql
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
├── sql/                PostgreSQL schema (15 tables)
├── infra/              Bicep IaC templates
├── tests/              pytest test suite (42 tests)
└── .github/workflows/  CI/CD
```
