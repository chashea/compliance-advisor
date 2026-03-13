# Compliance Advisor

Multi-tenant compliance workload platform that aggregates Microsoft 365 compliance data across agencies into a single executive view.

## Architecture

```
Tenant A ──┐
Tenant B ──┤
Tenant C ──┘
      │
      ▼
Compliance Agent (`collector/cli.py`)
  - Auth: client credentials (MSAL)
  - Source: Microsoft Graph API
  - Action: POST `/api/ingest`
      │
      ▼
Azure Function App (`cadvisor-func-prod`)
  - Ingest API: `/api/ingest`
  - Dashboard APIs: POST `/api/advisor/*`
      │
      ▼
PostgreSQL (17 tables: tenants, ediscovery, labels, dlp, irm, audit, scores, ...)
      ▲
      │
React SPA (`cadvisor-web-prod`)
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

- **React SPA frontend** with 12 pages: Overview, eDiscovery, Labels, Audit, DLP, IRM, Subject Rights, Comm Compliance, Info Barriers, Governance, Trend, Actions
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

## Prerequisites

- Python 3.11+
- Azure subscription (Commercial)
- Access to Microsoft 365 tenant(s) with compliance workloads
- Multi-tenant Entra app registration with client credentials (client secret)
- App service principal added to eDiscovery Manager and Compliance Administrator role groups in Microsoft Purview
- Azure CLI (`az`)

### Required Graph API Permissions (Application)

All permissions are **Application** type (not delegated) granted to the multi-tenant app registration.

| Permission | Workload |
|---|---|
| `eDiscovery.Read.All` | eDiscovery cases |
| `InformationProtectionPolicy.Read.All` | Sensitivity labels |
| `RecordsManagement.Read.All` | Retention labels & events |
| `AuditLogsQuery.Read.All` | Audit log queries |
| `SecurityEvents.Read.All` | DLP alerts, IRM alerts, Secure Score, Improvement Actions |
| `SubjectRightsRequest.Read.All` | Subject rights requests |
| `Policy.Read.All` | Information barriers |
| `User.Read.All` | User enumeration (for content policy probing) |

Additionally, the app's service principal must be added to these role groups in [compliance.microsoft.com](https://compliance.microsoft.com) → Permissions:
- **eDiscovery Manager**
- **Compliance Administrator**

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

### 5. Run the React frontend locally

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

The dev server proxies `/api` requests to `cadvisor-func-prod.azurewebsites.net`. To use a local Function App, set `VITE_API_BASE_URL=http://localhost:7071` in a `frontend/.env` file.

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
| `CLIENT_ID` | — | App registration client ID |
| `CLIENT_SECRET` | — | App registration client secret |
| `TENANT_ID` | — | Target tenant GUID |
| `AGENCY_ID` | — | Logical agency identifier |
| `DEPARTMENT` | — | Department name |
| `DISPLAY_NAME` | — | Human-readable tenant name |
| `FUNCTION_APP_URL` | — | Ingest endpoint URL |
| `FUNCTION_APP_KEY` | — | Function-level API key |
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

## CI/CD Deployment

GitHub Actions workflow `.github/workflows/deploy.yml` now supports infra deployment (Bicep what-if + apply) before function deployment.

Required secrets for infra deployment:

- `AZURE_RESOURCE_GROUP`
- `POSTGRES_ADMIN_PASSWORD`

Optional secrets:

- `DEPLOYER_OBJECT_ID`
- `ENTRA_CLIENT_ID`
- `ALLOWED_TENANT_IDS`

Frontend deployment secrets:

- `WEB_APP_NAME` — Azure Web App name (e.g., `cadvisor-web-prod`)
- `VITE_API_BASE_URL` — Function App URL (e.g., `https://cadvisor-func-prod.azurewebsites.net`)

### Scheduled App Hours (GitHub Actions)

Workflow: `.github/workflows/app-hours.yml`

- Runs hourly and evaluates local time in `America/New_York`.
- Auto-starts both Function App + Web App at **9:00 AM ET** on weekdays.
- Auto-stops both Function App + Web App at **8:00 PM ET** on weekdays.
- Includes `workflow_dispatch` with actions: `auto`, `start`, `stop`, `status`.

Required secrets:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_RESOURCE_GROUP`
- `FUNCTION_APP_NAME`
- `WEB_APP_NAME`

## Onboarding a New Tenant

1. Grant admin consent for the `compliance-advisor-collector` app in the target tenant:
   - Navigate to `https://login.microsoftonline.com/<TENANT_ID>/adminconsent?client_id=<CLIENT_ID>`
   - Or use the Entra admin center → Enterprise applications → Grant admin consent
2. Add the app's service principal to **eDiscovery Manager** and **Compliance Administrator** role groups in the tenant's [Microsoft Purview compliance portal](https://compliance.microsoft.com) → Permissions
3. Add the tenant GUID to `ALLOWED_TENANT_IDS` in the Function App config (if allowlist is enabled)
4. Run the collector:
   ```bash
   compliance-collect --tenant-id <GUID> --agency-id <NAME> --department <DEPT> --display-name "<NAME>"
   ```

## Project Structure

```
compliance-advisor/
├── frontend/          React 18 + TypeScript + Vite SPA
├── collector/          Per-tenant data collector (Python CLI)
├── functions/          Azure Functions v2 API backend
├── sql/                PostgreSQL schema (17 tables)
├── infra/              Bicep IaC templates (+ webapp.bicep)
├── tests/              pytest test suite
└── .github/workflows/  CI/CD (deploy + app-hours scheduler)
```
