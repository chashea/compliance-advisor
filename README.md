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

- **React SPA frontend** with 8 pages: Overview, Audit, Alerts (DLP + IRM + Purview Incidents), Assessments, Trend, Threat Assessments, Purview Insights, Threat Hunting
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
- Audit log activity summaries by service and operation
- Data governance protection scope visibility
- **AI Advisor** — executive compliance briefings and Q&A powered by Azure OpenAI Assistants API with managed identity auth
- **Demo mode** — `npm run demo` runs the full UI with static data, no backend required

## Prerequisites

- Python 3.12+
- Azure subscription (Commercial)
- Access to Microsoft 365 tenant(s) with compliance workloads
- Multi-tenant Entra app registration with client credentials (client secret)
- Azure CLI (`az`)

### Required Graph API Permissions (Application)

All permissions are **Application** type (not delegated) granted to the multi-tenant app registration.

| Permission | Workload |
|---|---|
| `SensitivityLabels.Read.All` | Sensitivity labels (`/v1.0/security/dataSecurityAndGovernance/sensitivityLabels`) |
| `InformationProtectionPolicy.Read.All` | Legacy fallback for the deprecated `/beta/security/informationProtection/sensitivityLabels` and sensitive info types |
| `RecordsManagement.Read.All` | Retention events + retention event types (retention labels themselves are delegated-only and skipped under app auth) |
| `AuditLogsQuery.Read.All` | Audit log queries (catch-all). For least privilege, narrow to per-service variants: `AuditLogsQuery-Entra.Read.All`, `AuditLogsQuery-Exchange.Read.All`, `AuditLogsQuery-SharePoint.Read.All`, `AuditLogsQuery-OneDrive.Read.All`, `AuditLogsQuery-Endpoint.Read.All`, `AuditLogsQuery-CRM.Read.All` |
| `SecurityEvents.Read.All` | Secure Score, improvement actions |
| `SecurityAlert.Read.All` | DLP alerts, IRM alerts (alerts_v2) |
| `SecurityIncident.Read.All` | Purview incidents |
| `ThreatHunting.Read.All` | KQL hunting queries (Defender XDR) |
| `Policy.Read.All` | Information barriers, DLP/IRM policies, protection scopes |
| `User.Read.All` | User enumeration (for content policy probing) |
| `MailboxSettings.Read` | User content policies |

> **Removed in this release:** `ThreatAssessment.ReadWrite` — the `/v1.0/informationProtection/threatAssessmentRequests` endpoint only supports delegated authentication, so the multi-tenant collector cannot use it. The collector no longer calls it; existing rows in the `threat_assessment_requests` table remain visible in the dashboard for historical reference.

## Local Development

### 1. Set up PostgreSQL

```bash
createdb compliance_advisor
# Apply all yoyo migrations
yoyo apply --database "postgresql://localhost/compliance_advisor" sql/migrations
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
npm install
npm run dev
```

The dev server proxies `/api` requests to `cadvisor-func-prod.azurewebsites.net`. To use a local Function App, set `VITE_API_BASE_URL=http://localhost:7071` in a `frontend/.env` file.

### 6. Demo mode (no backend required)

```bash
cd frontend
npm run demo
```

Launches the frontend with static demo data — no Azure credentials, Function App, or database needed. All 8 pages render with 3 sample tenants across 2 departments. An amber "DEMO MODE" banner appears at the top. Demo data is tree-shaken from production builds.

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
| `/api/advisor/overview` | `{department?}` | KPI summary (labels, alerts, audit) |
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

Deploy via Azure CLI from a Bicep source-of-truth (no committed ARM template — it would drift from `infra/main.bicep`):

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

# Apply schema migrations (via the in-VNet Function App admin endpoint)
KEY=$(az functionapp keys list -g rg-compliance-advisor -n cadvisor-func-prod --query functionKeys.default -o tsv)
curl -fsS "https://cadvisor-func-prod.azurewebsites.net/api/admin/migrate?code=${KEY}" -X POST
```

## CI/CD Deployment

GitHub Actions workflow `.github/workflows/deploy.yml` now supports infra deployment (Bicep what-if + apply) before function deployment.

### Required GitHub Actions secrets

Repository (or environment) secrets:

- `POSTGRES_ADMIN_PASSWORD` — break-glass admin password (used only for initial provisioning; Entra ID is the primary auth path)
- `ENTRA_CLIENT_ID` — **required**; CI fails fast if unset to prevent deploying with EasyAuth disabled
- `DATABASE_URL` — only used for ad-hoc schema migrations
- `ALERT_EMAIL` — optional; metric alert email recipient
- `POSTGRES_HA_MODE` — optional; `Disabled` (default) or `ZoneRedundant`

Optional (rarely changed) secrets:

- `DEPLOYER_OBJECT_ID`
- `ALLOWED_TENANT_IDS`
- `ENTRA_TENANT_ID` — for the SPA's MSAL configuration

### Required GitHub Actions repository variables

Set these as **variables** (not secrets) so deploys are portable across environments:

- `AZURE_CLIENT_ID` — federated identity client ID for OIDC login
- `AZURE_TENANT_ID` — Azure AD tenant ID
- `AZURE_SUBSCRIPTION_ID` — target subscription
- `AZURE_RESOURCE_GROUP` (e.g. `rg-compliance-advisor`)
- `FUNCTION_APP_NAME` (e.g. `cadvisor-func-prod`)
- `WEB_APP_NAME` (e.g. `cadvisor-web-prod`)
- `PG_SERVER_NAME` (e.g. `cadvisor-pg-7zez2cj3gamky`)
- `VITE_API_BASE_URL` (e.g. `https://cadvisor-func-prod.azurewebsites.net`)

### Scheduled App Hours (GitHub Actions)

Workflow: `.github/workflows/app-hours.yml`

- Runs hourly and evaluates local time in `America/New_York`.
- Auto-starts both Function App + Web App at **8:00 AM ET** on weekdays.
- Auto-stops both Function App + Web App at **8:00 PM ET** on weekdays.
- Includes `workflow_dispatch` with actions: `auto`, `start`, `stop`, `status`.

Uses the same secrets/variables as `deploy.yml` — `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` (secrets) plus `AZURE_RESOURCE_GROUP`, `FUNCTION_APP_NAME`, `WEB_APP_NAME`, `PG_SERVER_NAME` (variables).

## Onboarding a New Tenant

1. Grant admin consent for the `compliance-advisor-collector` app in the target tenant:
   - Navigate to `https://login.microsoftonline.com/<TENANT_ID>/adminconsent?client_id=<CLIENT_ID>`
   - Or use the Entra admin center → Enterprise applications → Grant admin consent
2. Add the tenant GUID to `ALLOWED_TENANT_IDS` in the Function App config (if allowlist is enabled)
3. Run the collector:
   ```bash
   compliance-collect --tenant-id <GUID> --agency-id <NAME> --department <DEPT> --display-name "<NAME>"
   ```

## Production Hardening

### Network and credentials
- **PostgreSQL**: `publicNetworkAccess: Disabled`, `passwordAuth: Disabled`. The server is reachable only via its private endpoint inside the VNet, and authentication is exclusively Microsoft Entra ID. The administrator password is required by the ARM API but is never used at runtime — rotate it post-deploy.
- **Function App → PostgreSQL**: the system-assigned managed identity authenticates using `DefaultAzureCredential`. The connection pool transparently rebuilds when the AAD access token has fewer than 5 minutes of validity left.
- **Schema migrations**: PG is private-network-only, so the deploy pipeline calls `POST /api/admin/migrate` (function-key auth) instead of `psql` from the runner. The endpoint applies pending [yoyo](https://ollycope.com/software/yoyo/latest/) migrations from `sql/migrations/` from inside the VNet using the MI.
- **Collector authentication**: by default the in-Azure collector uses the multi-tenant app's client secret stored in Key Vault (rotation: see "Collector secret rotation" below). When `COLLECTOR_USE_FEDERATED=true` is set (Bicep param `collectorUseFederated=true`), the Function App's MI obtains a federation assertion (`api://AzureADTokenExchange`) and passes it to MSAL as `client_assertion` — eliminating the long-lived secret entirely. The CLI collector running outside Azure always uses the secret because no MI is available.

### Collector secret rotation
Two strategies, depending on which one the deployment is using:

**(Recommended) Federated workload identity** — no secret to rotate.
After the first deploy of the multi-tenant app + the Function App MI, register the federated credential on the app registration (one-time, cross-tenant operation in the home tenant):

```bash
FUNC_MI_OBJECT_ID=$(az functionapp show -g rg-compliance-advisor -n cadvisor-func-prod \
  --query identity.principalId -o tsv)
ISSUER_URL="https://login.microsoftonline.com/<HOME_TENANT_ID>/v2.0"

az ad app federated-credential create \
  --id <COLLECTOR_APP_OBJECT_ID> \
  --parameters "{
    \"name\": \"compliance-advisor-functionapp\",
    \"issuer\": \"${ISSUER_URL}\",
    \"subject\": \"${FUNC_MI_OBJECT_ID}\",
    \"audiences\": [\"api://AzureADTokenExchange\"]
  }"

az functionapp config appsettings set -g rg-compliance-advisor -n cadvisor-func-prod \
  --settings COLLECTOR_USE_FEDERATED=true
```

After this, the `gcc-password` Key Vault secret can be deleted.

**(Fallback) Client secret** — manual rotation procedure:
```bash
NEW_SECRET=$(az ad app credential reset --id <COLLECTOR_APP_OBJECT_ID> \
  --display-name "rotated-$(date +%Y%m%d)" --years 1 --query password -o tsv)
az keyvault secret set --vault-name <KV_NAME> --name gcc-password --value "$NEW_SECRET"
# Restart the Function App to flush its in-process Key-Vault reference cache:
az functionapp restart -g rg-compliance-advisor -n cadvisor-func-prod
```

### Post-deploy bootstrap (one-time per deployment)
After the first `azd`/Bicep deploy, the deployer (registered as the PG Entra admin) must register the Function App's MI as a PostgreSQL principal:

```bash
# As the Entra admin (deployerObjectId / deployerPrincipalName), connect via
# psql with an AAD token from a workstation with VNet/jumpbox access:
PGPASSWORD=$(az account get-access-token \
  --resource-type oss-rdbms --query accessToken -o tsv) \
psql "host=<pg-host> dbname=compliance_advisor user=<admin-upn> sslmode=require"

# Inside psql, register the function app's MI and grant database access:
SELECT pgaadauth_create_principal('<function-app-name>', false, false);
GRANT CONNECT ON DATABASE compliance_advisor TO "<function-app-name>";
GRANT USAGE, CREATE ON SCHEMA public TO "<function-app-name>";
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO "<function-app-name>";
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO "<function-app-name>";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL PRIVILEGES ON TABLES TO "<function-app-name>";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT ALL PRIVILEGES ON SEQUENCES TO "<function-app-name>";
```

### Ingest authentication
The `/api/ingest` endpoint validates an Entra-issued JWT instead of a shared function key:

- The collector acquires an app-only token for the `INGEST_AUDIENCE` resource using its existing client credentials.
- The Function App validates the token's signature (per-tenant JWKS), the `aud`/`exp`/`iat` claims, and that the `tid` claim is in `ALLOWED_TENANT_IDS` and matches the payload's `tenant_id`.
- When `INGEST_EXPECTED_APPID` is set, the token's `appid`/`azp` must match the collector's app registration ID.
- A compromised function key (the previous shared-secret model) can no longer be used to ingest data as any tenant.

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
- **Metric alerts** (5 rules):
  - Function App HTTP 5xx errors > 5 in 5 min (severity 1)
  - Function App average response time > 10s over 5 min (severity 2)
  - Azure OpenAI client errors > 10 in 5 min (severity 2)
  - PostgreSQL active connections > 680 in 5 min (severity 2)
  - PostgreSQL CPU > 80% over 10 min (severity 2; pairs with `pg_stat_statements` for slow-query investigation)
- **Action group**: optional email notifications via `alertEmailAddress` parameter / `ALERT_EMAIL` secret

## Load Testing

```bash
pip install locust
locust -f loadtest/locustfile.py --host https://cadvisor-func-prod.azurewebsites.net
```

18 weighted tasks covering all dashboard and AI endpoints. AI endpoints have low weight to respect rate limiting (10 req/min/IP).

A non-blocking weekly load test runs automatically via `.github/workflows/loadtest.yml` (Mondays 03:00 UTC, 2 minutes / 10 users by default; override via `workflow_dispatch`). Reports upload as workflow artifacts (`loadtest-report-<run_id>`) and never block deploys — they exist purely for trend observation.

## Reliability — durable tenant collection

Per-tenant collection (triggered by registration, admin consent, or the daily timer) is handed off through an **Azure Service Bus queue** (`tenant-collect`) rather than the in-process `ThreadPoolExecutor` previously used. This guarantees:

- Work survives Function App instance recycle, scale-in, and 230s timeouts.
- Failed jobs retry up to 5 times with exponential backoff; after that they land in the dead-letter queue for operator review.
- Duplicate posts within 10 minutes (same `tenant_id`) are swallowed by Service Bus duplicate detection.

The Function App MI has **Service Bus Data Sender + Receiver** at the namespace scope — no shared access keys. When `SERVICE_BUS_NAMESPACE` is unset (local dev), the collector falls back to the legacy `ThreadPoolExecutor`.

## Deployment — staging slot + smoke gate

The deploy workflow targets a `staging` slot first, runs `/api/health/deep` against it (DB + Key Vault + OpenAI reachability), and only swaps into production on green. A failed smoke test aborts the deploy so a broken build never reaches the prod hostname. The slot inherits all production app settings except a small list of explicitly slot-bound names (`AzureWebJobsStorage__accountName`, `ServiceBus__fullyQualifiedNamespace`, `SERVICE_BUS_NAMESPACE`, `AUTH_REQUIRED`).

## Project Structure

```
compliance-advisor/
├── frontend/          React 19 + TypeScript + Vite SPA (8 pages)
├── collector/          Per-tenant data collector (Python CLI + threat hunter)
├── functions/          Azure Functions v2 API backend (routes/ subpackage)
├── sql/migrations/     yoyo-migrations (numbered .sql files; applied via /api/admin/migrate)
├── infra/              Bicep IaC (PostgreSQL, Function App, Key Vault, OpenAI, VNet, Monitoring, Alerts)
├── loadtest/           Locust load testing
├── tests/              pytest test suite (unit + integration; ~218 tests)
├── graph-auth/         One-off Microsoft Graph admin-consent helper scripts (not part of runtime)
├── .azure/             Azure Developer CLI (azd) config; safe to ignore for manual deploys
├── .claude/            Claude Code project guidance (CLAUDE.md mirrors copilot-instructions.md)
└── .github/workflows/  CI/CD (deploy + app-hours scheduler)
```
