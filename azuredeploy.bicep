// ─────────────────────────────────────────────────────────────────────────────
// Compliance Advisor — One-click Azure deployment
//
// Provisions: Key Vault · Azure SQL · AI Search · Azure OpenAI · AI Foundry
//             Hub + Project · Azure Functions · Application Insights ·
//             Container Registry · Storage Accounts
//
// Usage:
//   az deployment group create \
//     --resource-group rg-compliance-advisor \
//     --template-file azuredeploy.bicep \
//     --parameters environmentName=prod sqlAdminUsername=sqladmin \
//                  sqlAdminPassword=<password> deployerObjectId=$(az ad signed-in-user show --query id -o tsv)
// ─────────────────────────────────────────────────────────────────────────────

@description('Short environment label used in resource names (max 8 chars).')
@maxLength(8)
@allowed(['dev', 'staging', 'prod'])
param environmentName string = 'prod'

@description('Azure region for all resources. Must support Azure OpenAI GPT-4o — see https://aka.ms/oai/models.')
param location string = resourceGroup().location

@description('SQL Server administrator login name.')
param sqlAdminUsername string

@description('SQL Server administrator password (≥ 12 chars, must include upper, lower, digit, symbol).')
@minLength(12)
@secure()
param sqlAdminPassword string

@description('Email address for SQL Defender threat-detection alerts. Leave blank to skip.')
param securityAlertEmail string = ''

@description('Object ID of the user/service principal running this deployment. Grants Key Vault Secrets Officer so secrets can be written during deployment. Run: az ad signed-in-user show --query id -o tsv')
param deployerObjectId string

// ── Naming ────────────────────────────────────────────────────────────────────

var prefix = 'compliance-advisor-${environmentName}'
// uniqueString gives a 13-char deterministic suffix — keeps storage names globally unique
var uniq   = uniqueString(resourceGroup().id)

var tags = {
  environment: environmentName
  project    : 'compliance-advisor'
  managedBy  : 'arm-template'
}

// ── Role Definition IDs (built-in) ────────────────────────────────────────────

var roleKvSecretsOfficer        = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
var roleKvSecretsUser           = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var roleCogOpenAIUser           = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
var roleCogOpenAIContributor    = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a001fd3d-188f-4b5d-821b-7da978bf7442')
var roleSearchIndexDataReader   = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
var roleAcrPull                 = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

// ─────────────────────────────────────────────────────────────────────────────
// Observability
// ─────────────────────────────────────────────────────────────────────────────

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name    : 'log-${prefix}'
  location: location
  tags    : tags
  properties: {
    sku              : { name: 'PerGB2018' }
    retentionInDays  : 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name    : 'appi-${prefix}'
  location: location
  kind    : 'web'
  tags    : tags
  properties: {
    Application_Type  : 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Key Vault
// ─────────────────────────────────────────────────────────────────────────────

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name    : 'kv-${prefix}'
  location: location
  tags    : tags
  properties: {
    tenantId               : subscription().tenantId
    sku                    : { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection  : true
  }
}

// Deployer gets Secrets Officer so we can write secrets during this deployment
resource kvDeployerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(keyVault.id, deployerObjectId, 'SecretsOfficer')
  scope: keyVault
  properties: {
    roleDefinitionId: roleKvSecretsOfficer
    principalId     : deployerObjectId
    principalType   : 'User'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Search
// ─────────────────────────────────────────────────────────────────────────────

resource search 'Microsoft.Search/searchServices@2024-03-01-preview' = {
  name    : 'srch-${prefix}'
  location: location
  tags    : tags
  sku     : { name: 'basic' }
  properties: {
    replicaCount  : 1
    partitionCount: 1
    semanticSearch: 'free'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Azure OpenAI
// ─────────────────────────────────────────────────────────────────────────────

resource openai 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name    : 'oai-${prefix}'
  location: location
  kind    : 'OpenAI'
  tags    : tags
  sku     : { name: 'S0' }
  properties: {
    customSubDomainName: 'oai${uniq}'
  }
}

resource gpt4o 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openai
  name  : 'gpt-4o'
  sku   : { name: 'Standard', capacity: 10 }
  properties: {
    model: {
      format : 'OpenAI'
      name   : 'gpt-4o'
      version: '2024-11-20'
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// SQL Server + Database
// ─────────────────────────────────────────────────────────────────────────────

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name    : 'sql-${prefix}'
  location: location
  tags    : tags
  properties: {
    administratorLogin        : sqlAdminUsername
    administratorLoginPassword: sqlAdminPassword
    minimalTlsVersion         : '1.2'
  }
}

// Allow Azure-internal traffic (tighten to a VNet rule post-deployment)
resource sqlFirewall 'Microsoft.Sql/servers/firewallRules@2023-08-01-preview' = {
  parent: sqlServer
  name  : 'AllowAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

resource sqlDb 'Microsoft.Sql/servers/databases@2023-08-01-preview' = {
  parent  : sqlServer
  name    : 'ComplianceAdvisor'
  location: location
  tags    : tags
  sku     : { name: 'GP_S_Gen5_1', tier: 'GeneralPurpose', family: 'Gen5', capacity: 1 }
  properties: {
    collation    : 'SQL_Latin1_General_CP1_CI_AS'
    licenseType  : 'LicenseIncluded'
    minCapacity  : json('0.5')
    autoPauseDelay: 60
  }
}

resource sqlDefender 'Microsoft.Sql/servers/securityAlertPolicies@2023-08-01-preview' = {
  parent: sqlServer
  name  : 'Default'
  properties: {
    state          : 'Enabled'
    emailAddresses : empty(securityAlertEmail) ? [] : [securityAlertEmail]
    retentionDays  : 30
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Storage — AI Hub (separate from Function App storage)
// ─────────────────────────────────────────────────────────────────────────────

resource storageHub 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name    : 'staih${uniq}'
  location: location
  tags    : tags
  kind    : 'StorageV2'
  sku     : { name: 'Standard_LRS' }
  properties: {
    minimumTlsVersion    : 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Container Registry (required for Prompt Flow online deployments)
// ─────────────────────────────────────────────────────────────────────────────

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name    : 'acr${uniq}'
  location: location
  tags    : tags
  sku     : { name: 'Basic' }
  properties: { adminUserEnabled: false }
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Foundry Hub
// ─────────────────────────────────────────────────────────────────────────────

resource aiHub 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name    : 'aih-${prefix}'
  location: location
  kind    : 'Hub'
  tags    : tags
  identity: { type: 'SystemAssigned' }
  properties: {
    applicationInsights: appInsights.id
    keyVault           : keyVault.id
    storageAccount     : storageHub.id
    containerRegistry  : acr.id
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// AI Foundry Project
// ─────────────────────────────────────────────────────────────────────────────

resource aiProject 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name    : 'aip-${prefix}'
  location: location
  kind    : 'Project'
  tags    : tags
  identity: { type: 'SystemAssigned' }
  properties: {
    hubResourceId      : aiHub.id
    applicationInsights: appInsights.id
    keyVault           : keyVault.id
    storageAccount     : storageHub.id
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Hub Connections (OpenAI + AI Search visible to all Projects)
// ─────────────────────────────────────────────────────────────────────────────

resource openaiConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-04-01' = {
  parent: aiHub
  name  : 'azure-openai'
  properties: {
    authType: 'ApiKey'
    category: 'AzureOpenAI'
    target  : openai.properties.endpoint
    credentials: { key: openai.listKeys().key1 }
    metadata: {
      ApiType             : 'Azure'
      ApiVersion          : '2024-05-01-preview'
      DeploymentApiVersion: '2023-10-01-preview'
    }
  }
}

resource searchConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-04-01' = {
  parent: aiHub
  name  : 'azure-ai-search'
  properties: {
    authType: 'ApiKey'
    category: 'CognitiveSearch'
    target  : 'https://${search.name}.search.windows.net'
    credentials: { key: search.listAdminKeys().primaryKey }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Function App (Storage + Plan + App)
// ─────────────────────────────────────────────────────────────────────────────

resource storageFunc 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name    : 'stfunc${uniq}'
  location: location
  tags    : tags
  kind    : 'StorageV2'
  sku     : { name: 'Standard_LRS' }
  properties: {
    minimumTlsVersion    : 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name    : 'asp-${prefix}'
  location: location
  tags    : tags
  kind    : 'linux'
  sku     : { name: 'Y1', tier: 'Dynamic' }
  properties: { reserved: true }
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name    : 'func-${prefix}'
  location: location
  kind    : 'functionapp,linux'
  tags    : tags
  identity: { type: 'SystemAssigned' }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly   : true
    siteConfig  : {
      linuxFxVersion    : 'Python|3.11'
      minTlsVersion     : '1.2'
      ftpsState         : 'Disabled'
      appSettings: [
        { name: 'FUNCTIONS_EXTENSION_VERSION',          value: '~4' }
        { name: 'FUNCTIONS_WORKER_RUNTIME',             value: 'python' }
        { name: 'AzureWebJobsStorage',                  value: 'DefaultEndpointsProtocol=https;AccountName=${storageFunc.name};AccountKey=${storageFunc.listKeys().keys[0].value};EndpointSuffix=${environment().suffixes.storage}' }
        { name: 'KEY_VAULT_URL',                        value: keyVault.properties.vaultUri }
        { name: 'AZURE_SEARCH_ENDPOINT',                value: 'https://${search.name}.search.windows.net' }
        { name: 'AZURE_SEARCH_INDEX_NAME',              value: 'compliance-posture' }
        { name: 'AZURE_OPENAI_ENDPOINT',                value: openai.properties.endpoint }
        { name: 'AZURE_OPENAI_DEPLOYMENT_NAME',         value: gpt4o.name }
        { name: 'AZURE_OPENAI_API_VERSION',             value: '2024-05-01-preview' }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
        { name: 'MSSQL_CONNECTION',                     value: 'Driver={ODBC Driver 18 for SQL Server};Server=tcp:${sqlServer.properties.fullyQualifiedDomainName},1433;Database=ComplianceAdvisor;Uid=${sqlAdminUsername};Pwd=${sqlAdminPassword};Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;' }
      ]
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Role Assignments
// ─────────────────────────────────────────────────────────────────────────────

// Function App → Key Vault Secrets User
resource raFuncKv 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(keyVault.id, functionApp.id, 'SecretsUser')
  scope: keyVault
  properties: {
    roleDefinitionId: roleKvSecretsUser
    principalId     : functionApp.identity.principalId
    principalType   : 'ServicePrincipal'
  }
}

// Function App → OpenAI User
resource raFuncOpenAI 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(openai.id, functionApp.id, 'OpenAIUser')
  scope: openai
  properties: {
    roleDefinitionId: roleCogOpenAIUser
    principalId     : functionApp.identity.principalId
    principalType   : 'ServicePrincipal'
  }
}

// AI Project → OpenAI Contributor (Prompt Flow execution)
resource raProjectOpenAI 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(openai.id, aiProject.id, 'OpenAIContributor')
  scope: openai
  properties: {
    roleDefinitionId: roleCogOpenAIContributor
    principalId     : aiProject.identity.principalId
    principalType   : 'ServicePrincipal'
  }
}

// AI Project → Search Index Data Reader (RAG retrieval in Prompt Flows)
resource raProjectSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(search.id, aiProject.id, 'SearchIndexDataReader')
  scope: search
  properties: {
    roleDefinitionId: roleSearchIndexDataReader
    principalId     : aiProject.identity.principalId
    principalType   : 'ServicePrincipal'
  }
}

// AI Hub → ACR Pull (online endpoint deployments)
resource raHubAcr 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(acr.id, aiHub.id, 'AcrPull')
  scope: acr
  properties: {
    roleDefinitionId: roleAcrPull
    principalId     : aiHub.identity.principalId
    principalType   : 'ServicePrincipal'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Key Vault Secrets
// ─────────────────────────────────────────────────────────────────────────────

resource secretSearchKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name  : 'azure-search-key'
  properties: { value: search.listAdminKeys().primaryKey }
  dependsOn: [kvDeployerRole]
}

resource secretOpenAIKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: keyVault
  name  : 'azure-openai-api-key'
  properties: { value: openai.listKeys().key1 }
  dependsOn: [kvDeployerRole]
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output functionAppName      string = functionApp.name
output sqlServerFqdn        string = sqlServer.properties.fullyQualifiedDomainName
output searchEndpoint       string = 'https://${search.name}.search.windows.net'
output keyVaultUri          string = keyVault.properties.vaultUri
output aiFoundryProjectName string = aiProject.name
output openaiEndpoint       string = openai.properties.endpoint
output resourceGroupName    string = resourceGroup().name
