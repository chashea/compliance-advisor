# Azure Deployment Plan — Key Vault Private Link

## Status: Deployed

## Overview
Secure Key Vault with Private Link so the Function App accesses secrets over a private endpoint instead of the public internet. This prevents the public-access-disabled outage from recurring and aligns with Zero Trust / CJIS requirements.

## Mode
MODIFY — Adding VNet + Private Endpoint to existing infrastructure

## Architecture Changes

### New Resources
1. **Virtual Network** (`cadvisor-vnet-prod`) — 10.0.0.0/16
2. **Subnet: func-integration** — 10.0.1.0/24 — delegated to `Microsoft.Web/serverFarms` for Function App VNet integration
3. **Subnet: private-endpoints** — 10.0.2.0/24 — hosts Private Endpoints
4. **Private Endpoint** for Key Vault — in private-endpoints subnet
5. **Private DNS Zone** — `privatelink.vaultcore.azure.net` — linked to VNet

### Modified Resources
- **Key Vault** — `publicNetworkAccess: 'Disabled'`, `defaultAction: 'Deny'`
- **Function App** — `virtualNetworkSubnetId` set to func-integration subnet

### Unchanged
- PostgreSQL (already uses firewall rule for Azure services)
- Web App (frontend SPA, doesn't access Key Vault)
- Storage Account, OpenAI, Monitoring

## Implementation Steps

1. Create `infra/modules/network.bicep` — VNet, subnets, Private Endpoint, Private DNS Zone
2. Update `infra/modules/keyvault.bicep` — disable public access
3. Update `infra/modules/function-app.bicep` — add VNet integration
4. Update `infra/main.bicep` — wire network module, pass subnet IDs
5. Rebuild `azuredeploy.json`
6. Validate with `az deployment group what-if`

## Recipe
Bicep (existing pattern)

## Validation Proof

Validated on **2026-03-21 16:27:21 UTC**.

- `az bicep build --file infra/main.bicep --outfile /tmp/azuredeploy.validate.json`  
  Result: **Passed** (compiled successfully; linter warnings only).
- `python3.12 -m pytest tests/ -q`  
  Result: **Passed** (`73 passed`).
- `cd frontend && npm run build --silent`  
  Result: **Passed** (Vite production build completed).
- `az functionapp show --name cadvisor-func-prod --resource-group rg-compliance-advisor --query "{name:name,state:state,defaultHostName:defaultHostName}" -o json`  
  Result: **Passed** (`state=Running`).
- `az deployment group validate --resource-group rg-compliance-advisor --template-file infra/main.bicep --parameters postgresAdminPassword='DummyPassw0rd!234' deployerObjectId='' entraClientId='' allowedTenantIds='' -o json`  
  Result: **Passed** (`provisioningState=Succeeded`).
- `az deployment group what-if --resource-group rg-compliance-advisor --template-file infra/main.bicep --parameters postgresAdminPassword='DummyPassw0rd!234' deployerObjectId='' entraClientId='' allowedTenantIds='' --result-format ResourceIdOnly -o json`  
  Result: **Passed** (`status=Succeeded`, `change_count=30`).

Notes:
- `what-if` initially returned a transient connection reset, then succeeded on retry.
- Existing Bicep linter warnings observed:
  - `outputs-should-not-contain-secrets` in `infra/modules/postgres.bicep`
  - `no-hardcoded-env-urls` in `infra/modules/function-app.bicep`

## Deployment Result

Deployed on **2026-03-21**.

- Function App code deployed to `cadvisor-func-prod` using zip deploy with **remote build**.
- Frontend static assets deployed to `cadvisor-web-prod` using zip deploy.
- Post-deploy API health check:
  - `POST /api/advisor/status` returned `200` with active tenant data.
- Post-deploy eDiscovery verification:
  - `POST /api/collect/{tenant_id}` returned `200`
  - response now includes `diagnostics.ediscovery`
  - current diagnostic shows Graph success with zero returned cases (`http_status=200`, `count=0`), indicating no dashboard aggregation bug in this path.
