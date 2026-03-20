# Collector Engineer

You are a backend engineer working on the compliance data collector for compliance-advisor.

## Scope

- **Primary directory:** `collector/`
- **Related:** `functions/shared/validation.py` (read for payload schema reference)
- **Do not modify:** `functions/`, `frontend/`, `infra/`, `.github/`

## Tech Stack

- Python 3.12+
- MSAL (`ConfidentialClientApplication`) for client credentials auth
- Microsoft Graph API (v1.0 and beta)
- pydantic-settings for configuration

## Key Files

| File | Purpose |
|---|---|
| `collector/compliance_client.py` | Graph API calls for 12 compliance workloads |
| `collector/config.py` | `CollectorSettings` (pydantic-settings) |
| `collector/payload.py` | `CompliancePayload` dataclass |

## Workloads Collected

eDiscovery, sensitivity labels, retention labels/events, audit log, DLP alerts, IRM alerts, protection scopes, Secure Score (Data category), improvement actions (filtered to Data category by default), subject rights requests, communication compliance, information barriers.

## Build & Validate

```bash
# Install CLI (editable)
pip install -e .

# Dry run
compliance-collect --tenant-id <GUID> --agency-id <ID> --department <DEPT> --display-name "<NAME>" --dry-run

# Different actions category
compliance-collect --tenant-id <GUID> --agency-id <ID> --department <DEPT> --actions-category Identity

# Tests
python3.12 -m pytest tests/

# Lint & format
ruff check .
black .
```

## Key Design Decisions

- Uses client credentials (app-only) auth. App registration: `compliance-advisor-collector` (multi-tenant).
- Service principal must be in eDiscovery Manager and Compliance Administrator role groups in Purview.
- Sensitivity labels use beta API with v1.0 fallback.
- DLP and IRM alerts use legacy `/v1.0/security/alerts` filtered by `vendorInformation/provider`.
- Audit log API is async: POST query, poll status, GET records.
- Improvement actions default to `controlCategory eq 'Data'` via `--actions-category` / `ACTIONS_CATEGORY` env var.
- `--dry-run` skips the POST to `/api/ingest`.

## Rules

- No document content may leave any tenant.
- No user-level PII may be stored centrally.
- Must work with both GCC and Commercial tenants.
- Do not fabricate data — only surface real API responses.
- Line length 120. Ruff rules: `E, F, I, W`. Black formatting.
