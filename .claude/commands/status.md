---
name: status
description: Check health and status of all compliance-advisor components
user_invocable: true
---

Check the current status of all compliance-advisor components.

Run these checks in parallel where possible:

1. **Git status**: `git status` + `git log --oneline -5` — current branch, uncommitted changes, recent commits.
2. **Tests**: `python3.12 -m pytest tests/ -q` — pass/fail summary.
3. **Frontend build**: `cd frontend && npm run build` — compiles cleanly?
4. **Azure resources** (if logged in):
   - Function App: `az functionapp show -n cadvisor-func-prod -g rg-compliance-advisor --query "{state:state, defaultHostName:defaultHostName}" -o table`
   - Web App: `az webapp show -n cadvisor-web-prod -g rg-compliance-advisor --query "{state:state, defaultHostName:defaultHostName}" -o table`

Report a summary table of each component's health.
