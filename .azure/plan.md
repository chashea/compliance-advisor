# Azure Deployment Plan — Key Vault Private Link

## Status: Ready for Validation

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
