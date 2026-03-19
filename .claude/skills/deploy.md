---
name: deploy
description: Deploy compliance-advisor to Azure (infra, functions, frontend)
user_invocable: true
---

Deploy compliance-advisor to Azure. This follows the CI/CD pipeline logic but runs manually.

**Before deploying:**
1. Run tests: `python3.12 -m pytest tests/ -v` — abort if any fail.
2. Build frontend: `cd frontend && npm run build` — abort if build fails.
3. Compile Bicep: `az bicep build --file infra/main.bicep --outfile azuredeploy.json` — abort if errors.

**Ask the user** which components to deploy (or all):
1. **Infrastructure** — `az deployment group create --resource-group rg-compliance-advisor --template-file infra/main.bicep`
2. **Functions** — `cd functions && func azure functionapp publish cadvisor-func-prod --python`
3. **Frontend** — build and deploy to `cadvisor-web-prod` via Azure CLI

**After deploying:**
- Verify the Function App is running: `az functionapp show -n cadvisor-func-prod -g rg-compliance-advisor --query state`
- Verify the Web App is running: `az webapp show -n cadvisor-web-prod -g rg-compliance-advisor --query state`
- Report deployment status.
