---
name: collect
description: Run the compliance data collector against a tenant
user_invocable: true
---

Run the compliance-advisor collector CLI to pull data from a Microsoft 365 tenant.

**Prerequisites:**
- `.env` file must have `CLIENT_ID` and `CLIENT_SECRET` for the collector app registration (28ce4587-667e-4eec-8740-190dee3634da).
- Collector must be installed: `pip install -e .`

**Usage:**
- Ask the user for: `--tenant-id`, `--agency-id`, `--department`, `--display-name`
- Default to `--dry-run` unless the user says to ingest for real.
- Default actions category is `Data`. Use `--actions-category` to override.

**Command:**
```bash
compliance-collect \
  --tenant-id <GUID> \
  --agency-id <ID> \
  --department <DEPT> \
  --display-name "<NAME>" \
  --dry-run
```

**After collection:**
- Report what workloads were collected (labels, DLP, IRM, etc.)
- Report any Graph API errors or missing permissions.
