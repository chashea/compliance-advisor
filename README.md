# Compliance Advisor

Multi-tenant compliance workload platform that aggregates Microsoft 365 compliance data across agencies into a single executive view, with AI-powered compliance advisory via Azure OpenAI.

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
┌─── VNet (10.0.0.0/16) ──────────────────────────────┐
│                                                       │
│  snet-func-integration (10.0.1.0/24)                 │
│  ┌─────────────────────────────────────────────┐     │
│  │ Azure Function App (`cadvisor-func-prod`)   │     │
│  │  - Ingest API: `/api/ingest`                │     │
│  │  - Dashboard APIs: POST `/api/advisor/*`    │     │
│  │  - AI Advisor: `/briefing`, `/ask`          │     │
│  │  - EasyAuth (Entra ID, conditional)         │     │
│  └──────┬──────────┬───────────┬───────────────┘     │
│         │          │           │                      │
│  snet-private-endpoints (10.0.2.0/24)                │
│  ┌──────▼──┐ ┌─────▼────┐ ┌───▼──────────────┐      │
│  │ PG (22  │ │ Key Vault│ │ Azure OpenAI     │      │
│  │ tables) │ │ (secrets)│ │ (gpt-4o)         │      │
│  └─────────┘ └──────────┘ └──────────────────┘      │
│              Private Endpoints (no public access)     │
└───────────────────────────────────────────────────────┘
      ▲                           │
      │                    ┌──────▼──────┐
React SPA                 │ App Insights │
(`cadvisor-web-prod`)     │ + Log Analyt.│
                          └─────────────┘
```

## Compliance Workloads

| Workload | Data Source | API |
|---|---|---|
| eDiscovery | Cases, custodians, holds | `/security/cases/ediscoveryCases` |
| Information Protection | Sensitivity labels | `/beta/security/informationProtection/sensitivityLabels` |
| Records Management | Retention labels & events | `/security/labels/retentionLabels`, `/security/triggers/retentionEvents` |
| Audit Log | Compliance activity records | `/security/auditLog/queries` (async) |
| DLP | DLP alerts from Defender | `/security/alerts_v2?$filter=serviceSource eq 'microsoftDataLossPrevention'` |
| Insider Risk Management | IRM alerts from Defender | `/security/alerts_v2?$filter=serviceSource eq 'microsoftInsiderRiskManagement'` |
| Data Security & Governance | Protection scopes | `/dataSecurityAndGovernance/protectionScopes/compute` |
| Secure Score | Overall + Data category score | `/security/secureScores` + `/security/secureScoreControlProfiles` |
| Improvement Actions | Secure Score control profiles (Data category) | `/security/secureScoreControlProfiles?$filter=controlCategory eq 'Data'` |
| Information Barriers | Segment policies | `/beta/identityGovernance/informationBarriers/policies` |
| Purview Incidents | Security incidents with Purview-correlated alerts | `/security/incidents` filtered by Purview service sources |

> **Note:** DLP and IRM alerts use the `/v1.0/security/alerts_v2` endpoint with `serviceSource` filtering. Alert responses include classification, determination, evidence arrays, MITRE ATT&CK techniques, and incident correlation.

## Features

- **React SPA frontend** with 12 pages: Overview, eDiscovery, Labels, Audit, Alerts (DLP + IRM + Purview Incidents), Info Barriers, Governance, Trend, Actions, Assessments, Threat Assessments, Purview Insights
- Secure Score Data category KPI showing `current / max` points and percentage
- Improvement Actions filtered to Data category by default with category/cost/tier filters
- Agency/department dropdown filter with active filter state summary and clear reset
- DLP alert monitoring with inline severity chart and severity/status/tenant filters
- Insider Risk Management alert monitoring with severity/status filters
- Purview Incidents tracking with severity, status, classification, and alert correlation
- Purview Insights analytics page with:
  - Effectiveness KPIs (closure rate, true-positive rate, MTTR, repeat offenders)
  - Classification coverage percentages by applicable surface
  - Policy drift and risk-spike correlation timeline
  - Weighted Data-at-Risk score and risk level
  - CJIS/NIST-oriented control mapping with evidence links
  - Owner-prioritized action queue
  - Collection freshness and completeness indicators per tenant
- eDiscovery case tracking with custodian counts
- Sensitivity and retention label inventory
- Information Barriers policy visibility
- Audit log activity summaries by service and operation
- Data governance protection scope visibility
- **AI Advisor** — executive compliance briefings and Q&A powered by Azure OpenAI Assistants API with managed identity auth
- **Demo mode** — `npm run demo` runs the full UI with static data, no backend required

## Prerequisites

- Python 3.12+
- Azure subscription (Commercial)
- Access to Microsoft 365 tenant(s) with compliance workloads
- Multi-tenant Entra app registration with client credentials (client secret)
- App service principal registered via `Connect-IPPSSession` and added to **eDiscovery Administrator** role group in Purview
- Azure CLI (`az`)

### Required Graph API Permissions (Application)

All permissions are **Application** type (not delegated) granted to the multi-tenant app registration.

| Permission | Workload |
|---|---|
| `eDiscovery.Read.All` | eDiscovery cases |
| `InformationProtectionPolicy.Read.All` | Sensitivity labels, sensitive info types |
| `RecordsManagement.Read.All` | Retention labels & events |
| `AuditLogsQuery.Read.All` | Audit log queries |
| `SecurityEvents.Read.All` | Secure Score, Improvement Actions |
| `SecurityAlert.Read.All` | DLP alerts, IRM alerts |
| `SecurityIncident.Read.All` | Purview incidents |
| `Policy.Read.All` | Information barriers, DLP/IRM policies, protection scopes |
| `User.Read.All` | User enumeration (for content policy probing) |
| `MailboxSettings.Read` | User content policies |

Additionally, the app's service principal must be registered in the **Security & Compliance PowerShell** context and assigned to the **eDiscovery Administrator** role group in each tenant. This is required for the eDiscovery Graph API to work with app-only auth:

```powershell
# Install module if needed: Install-Module ExchangeOnlineManagement
Import-Module ExchangeOnlineManagement

# Connect to Security & Compliance (NOT Connect-ExchangeOnline)
Connect-IPPSSession

# Register the service principal (use the SP Object ID from Entra in that tenant)
New-ServicePrincipal -AppId <CLIENT_ID> -ObjectId <SP_OBJECT_ID> -DisplayName "compliance-advisor-collector"

# Add as eDiscovery Case Admin (required for app-only eDiscovery API access)
Add-eDiscoveryCaseAdmin -User <SP_OBJECT_ID>

# Verify
Get-ServicePrincipal
Get-eDiscoveryCaseAdmin
```

Then add the service principal to the **eDiscovery Administrator** role group in the [Microsoft Purview portal](https://purview.microsoft.com) → Roles & Scopes → Permissions.

> **Note:** To find the SP Object ID in each tenant: `az ad sp show --id <CLIENT_ID> --query id -o tsv`. Role changes can take up to 60 minutes to propagate. The `Connect-IPPSSession` step is critical — registering via `Connect-ExchangeOnline` alone is not sufficient.

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

### 6. Demo mode (no backend required)

```bash
cd frontend
npm run demo
```

Launches the frontend with static demo data — no Azure credentials, Function App, or database needed. All 12 pages render with 3 sample tenants across 2 departments. An amber "DEMO MODE" banner appears at the top. Demo data is tree-shaken from production builds.

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
| `/api/advisor/info-barriers` | `{department?}` | Information barrier policies |
| `/api/advisor/briefing` | `{department?}` | AI-generated executive compliance briefing |
| `/api/advisor/ask` | `{question, department?}` | AI-powered compliance Q&A |
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
- `ALERT_EMAIL` — email address for metric alert notifications
- `POSTGRES_HA_MODE` — `Disabled` (default) or `ZoneRedundant`

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
2. Register the app's service principal via `Connect-IPPSSession` + `New-ServicePrincipal` and add it to the **eDiscovery Administrator** role group in Purview (see PowerShell steps above)
3. Add the tenant GUID to `ALLOWED_TENANT_IDS` in the Function App config (if allowlist is enabled)
4. Run the collector:
   ```bash
   compliance-collect --tenant-id <GUID> --agency-id <NAME> --department <DEPT> --display-name "<NAME>"
   ```

## Production Hardening

### CORS
API CORS is locked to `https://cadvisor-web-prod.azurewebsites.net`. Cross-origin requests from other domains are rejected.

### Rate Limiting
AI endpoints (`/advisor/briefing`, `/advisor/ask`) are rate-limited to 10 requests per minute per client IP. Exceeding this returns HTTP 429.

### Query Pagination
All dashboard list queries are capped at 1000 rows. Audit records are capped at 500.

### Database Indexes
Standalone `snapshot_date` indexes exist on `audit_records`, `dlp_alerts`, and `compliance_trend` for efficient date-filtered queries.

### Known Trade-offs
- **PostgreSQL HA** — defaults to single-server (`Disabled`). Set `postgresHaMode=ZoneRedundant` to enable zone-redundant HA (approximately doubles PostgreSQL cost).
- **Entra ID auth** — API endpoints use ANONYMOUS auth level. EasyAuth is conditionally deployed when `ENTRA_CLIENT_ID` is set. The CI/CD pipeline warns when it is missing.

## Network Security

Zero Trust network architecture with no public access to backend services.

- **VNet**: `cadvisor-vnet-prod` (10.0.0.0/16) with two subnets
  - `snet-func-integration` (10.0.1.0/24) — Function App VNet integration
  - `snet-private-endpoints` (10.0.2.0/24) — private endpoints for KV, PG, OpenAI
- **Private endpoints**: Key Vault, PostgreSQL, and Azure OpenAI are accessible only via private endpoints within the VNet
- **OpenAI public access**: `Disabled` — all traffic routes through private endpoint
- **NSGs**:
  - Func subnet: allows VNet outbound (HTTPS + PostgreSQL 5432) and internet outbound (HTTPS 443)
  - PE subnet: allows inbound only from func subnet (HTTPS 443 + PostgreSQL 5432), deny-all-else (priority 4096)
- **Function App**: VNet-integrated with `vnetRouteAllEnabled: true` — all outbound traffic routes through the VNet

## Monitoring

- **Log Analytics**: `cadvisor-la-prod` — 90-day retention, PerGB2018 SKU
- **Application Insights**: `cadvisor-ai-prod` — connected to Log Analytics, ingestion mode `LogAnalytics`
- **Diagnostic settings**: Function App, Azure OpenAI, and PostgreSQL all send `allLogs` + `AllMetrics` to Log Analytics
- **Metric alerts** (4 rules):
  - Function App HTTP 5xx errors > 5 in 5 min (severity 1)
  - Function App average response time > 10s over 5 min (severity 2)
  - Azure OpenAI client errors > 10 in 5 min (severity 2)
  - PostgreSQL active connections > 680 in 5 min (severity 2)
- **Action group**: optional email notifications via `alertEmailAddress` parameter / `ALERT_EMAIL` secret

## Load Testing

```bash
pip install locust
locust -f loadtest/locustfile.py --host https://cadvisor-func-prod.azurewebsites.net
```

18 weighted tasks covering all dashboard and AI endpoints. AI endpoints have low weight to respect rate limiting (10 req/min/IP).

## Project Structure

```
compliance-advisor/
├── frontend/          React 19 + TypeScript + Vite SPA (12 pages)
├── collector/          Per-tenant data collector (Python CLI)
├── functions/          Azure Functions v2 API backend
├── sql/                PostgreSQL schema (22 tables)
├── infra/              Bicep IaC (PostgreSQL, Function App, Key Vault, OpenAI, VNet, Monitoring, Alerts)
├── loadtest/           Locust load testing
├── tests/              pytest test suite
└── .github/workflows/  CI/CD (deploy + app-hours scheduler)
```
