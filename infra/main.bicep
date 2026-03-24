// ──────────────────────────────────────────────────────────────────
// Compliance Advisor — Azure Commercial Infrastructure
//
// Deploys: PostgreSQL, Function App, Key Vault, OpenAI, Monitoring
//
// Usage:
//   az deployment group create \
//     --resource-group rg-compliance-advisor \
//     --template-file infra/main.bicep \
//     --parameters infra/parameters/prod.bicepparam
// ──────────────────────────────────────────────────────────────────

targetScope = 'resourceGroup'

@allowed(['dev', 'prod'])
param environmentName string = 'prod'

param location string = resourceGroup().location

@description('Comma-separated list of allowed tenant GUIDs for ingestion')
param allowedTenantIds string = ''

@description('Object ID of the deployer for Key Vault access policies')
param deployerObjectId string = ''

@description('Entra ID client ID for API SSO (leave empty to skip EasyAuth)')
param entraClientId string = ''

@secure()
@description('PostgreSQL administrator password')
param postgresAdminPassword string

var prefix = 'cadvisor'
var uniqueSuffix = uniqueString(resourceGroup().id)
var storageName = '${prefix}st${take(uniqueSuffix, 11)}'
var functionAppName = '${prefix}-func-${environmentName}'
var keyVaultName = '${prefix}-kv-${take(uniqueSuffix, 10)}'
var appInsightsName = '${prefix}-ai-${environmentName}'
var logAnalyticsName = '${prefix}-la-${environmentName}'
var diagnosticSettingName = 'send-to-cadvisor-law'
var appServicePlanName = '${prefix}-asp-${environmentName}'
var postgresServerName = '${prefix}-pg-${uniqueSuffix}'
var webAppName = '${prefix}-web-${environmentName}'
var webAppPlanName = '${prefix}-wasp-${environmentName}'
var openAiName = '${prefix}-oai-${uniqueSuffix}'
var vnetName = '${prefix}-vnet-${environmentName}'

// ── Storage Account (for Azure Functions runtime) ───────────────
// Functions runtime requires a storage account for triggers/bindings
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowSharedKeyAccess: false
    publicNetworkAccess: 'Enabled'
  }
}

// ── PostgreSQL ──────────────────────────────────────────────────
module postgres 'modules/postgres.bicep' = {
  name: 'postgres'
  params: {
    serverName: postgresServerName
    location: location
    administratorPassword: postgresAdminPassword
  }
}

// ── Key Vault ───────────────────────────────────────────────────
module keyVault 'modules/keyvault.bicep' = {
  name: 'keyvault'
  params: {
    keyVaultName: keyVaultName
    location: location
    deployerObjectId: deployerObjectId
    databaseUrl: postgres.outputs.connectionString
  }
}

// ── Monitoring (Log Analytics + App Insights) ───────────────────
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: logAnalyticsName
    appInsightsName: appInsightsName
    location: location
  }
}

// ── Azure OpenAI ───────────────────────────────────────────────
module openai 'modules/openai.bicep' = {
  name: 'openai'
  params: {
    openAiName: openAiName
    location: location
  }
}

// ── Networking (VNet + Key Vault Private Endpoint) ──────────────
module network 'modules/network.bicep' = {
  name: 'network'
  params: {
    vnetName: vnetName
    location: location
    keyVaultId: keyVault.outputs.keyVaultId
    keyVaultName: keyVaultName
    postgresServerId: postgres.outputs.serverId
    postgresServerName: postgresServerName
  }
}

// ── Function App ────────────────────────────────────────────────
module functionApp 'modules/function-app.bicep' = {
  name: 'functionApp'
  params: {
    functionAppName: functionAppName
    appServicePlanName: appServicePlanName
    location: location
    storageAccountName: storageAccount.name
    appInsightsInstrumentationKey: monitoring.outputs.appInsightsInstrumentationKey
    appInsightsConnectionString: monitoring.outputs.appInsightsConnectionString
    keyVaultUri: keyVault.outputs.keyVaultUri
    allowedTenantIds: allowedTenantIds
    entraClientId: entraClientId
    azureOpenAiEndpoint: openai.outputs.openAiEndpoint
    virtualNetworkSubnetId: network.outputs.funcIntegrationSubnetId
  }
}

// ── Web App (React SPA frontend) ──────────────────────────────────
module webApp 'modules/webapp.bicep' = {
  name: 'webApp'
  params: {
    webAppName: webAppName
    webAppPlanName: webAppPlanName
    location: location
    functionAppUrl: functionApp.outputs.functionAppUrl
    virtualNetworkSubnetId: network.outputs.funcIntegrationSubnetId
    entraClientId: entraClientId
  }
}

// ── RBAC: Function App Managed Identity → Key Vault ─────────────

// Key Vault Secrets User
resource kvRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, keyVaultName, functionAppName, '4633458b-17de-408a-b874-0445c86b69e6')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: functionApp.outputs.functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── RBAC: Function App Managed Identity → Storage Account ────────

// Storage Blob Data Owner (manage blobs: leases, secrets, timer state)
resource storageBlobRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: '5290cfeb-9780-4e97-80e8-d7e9183d6d47'
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b')
    principalId: functionApp.outputs.functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Storage Queue Data Contributor (function host queue operations)
resource storageQueueRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: '410e6877-3c25-4c13-b582-85821cb4e201'
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88')
    principalId: functionApp.outputs.functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── RBAC: Function App Managed Identity → Azure OpenAI ───────────

// Cognitive Services OpenAI User
resource openAiRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, openAiName, functionAppName, '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: functionApp.outputs.functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ── Diagnostic settings ────────────────────────────────────────────
resource functionAppResource 'Microsoft.Web/sites@2023-01-01' existing = {
  name: functionAppName
}

resource openAiAccount 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' existing = {
  name: openAiName
}

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' existing = {
  name: postgresServerName
}

resource functionAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: functionAppResource
  name: diagnosticSettingName
  dependsOn: [
    functionApp
  ]
  properties: {
    workspaceId: monitoring.outputs.logAnalyticsId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

resource openAiDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: openAiAccount
  name: diagnosticSettingName
  dependsOn: [
    openai
  ]
  properties: {
    workspaceId: monitoring.outputs.logAnalyticsId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

resource postgresDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  scope: postgresServer
  name: diagnosticSettingName
  dependsOn: [
    postgres
  ]
  properties: {
    workspaceId: monitoring.outputs.logAnalyticsId
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

// ── Outputs ─────────────────────────────────────────────────────
output functionAppUrl string = functionApp.outputs.functionAppUrl
output functionAppName string = functionAppName
output keyVaultUri string = keyVault.outputs.keyVaultUri
output keyVaultName string = keyVault.outputs.keyVaultName
output postgresServerFqdn string = postgres.outputs.serverFqdn
output appInsightsName string = appInsightsName
output webAppUrl string = webApp.outputs.webAppUrl
output webAppName string = webApp.outputs.webAppName
output openAiEndpoint string = openai.outputs.openAiEndpoint
