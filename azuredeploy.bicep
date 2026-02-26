// ─────────────────────────────────────────────────────────────────────────────
// Compliance Advisor — One-click Azure deployment (Microsoft Foundry)
//
// Provisions: Key Vault · Azure SQL · AI Search · Microsoft Foundry (AIServices)
//             Foundry Project · Azure Functions · Application Insights ·
//             Storage Accounts
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

@description('Azure region for the Function App and its App Service Plan. Override when the primary region lacks App Service quota.')
param functionAppLocation string = location

@description('Azure region for SQL Server. Override when the primary region is not accepting new SQL servers.')
param sqlLocation string = location

@description('SQL Server administrator login name (used as a fallback; Entra ID is the primary auth).')
param sqlAdminUsername string

@description('SQL Server administrator password (used as a fallback; Entra ID is the primary auth).')
@secure()
param sqlAdminPassword string

@description('Display name of the Entra ID admin for SQL Server.')
param sqlEntraAdminName string = 'Charles Shea'

@description('Object ID of the Entra ID admin for SQL Server (defaults to deployer).')
param sqlEntraAdminObjectId string = deployerObjectId

@description('Login (UPN) of the Entra ID admin for SQL Server.')
param sqlEntraAdminLogin string = ''

@description('Email address for SQL Defender threat-detection alerts. Leave blank to skip.')
param securityAlertEmail string = ''

@description('Object ID of the user/service principal running this deployment. Grants Key Vault Secrets Officer so secrets can be written during deployment. Run: az ad signed-in-user show --query id -o tsv')
param deployerObjectId string

@description('Principal type of the deployer — "User" for interactive portal/CLI deployments, "ServicePrincipal" for CI/CD pipelines.')
@allowed(['User', 'ServicePrincipal', 'Group'])
param deployerPrincipalType string = 'User'

@description('Optional: object IDs granted Reader on the resource group for monitoring/audit (e.g. security team). Leave empty to skip.')
param readerPrincipalIds array = []

@description('Principal type for readerPrincipalIds — usually User or Group.')
@allowed(['User', 'ServicePrincipal', 'Group'])
param readerPrincipalType string = 'User'

@description('Leave empty for commercial and M365 GCC (global endpoints). Set to "usgovernment" only for GCC High/DoD (uses .us endpoints).')
@allowed(['', 'usgovernment'])
param graphNationalCloud string = ''

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
var roleCogOpenAIContributor    = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a001fd3d-188f-4b5d-821b-7da978bf7442')
var roleSearchIndexDataReader   = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
var roleSearchServiceContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7ca78c08-252a-4471-8644-bb5ff32d4ba0')
var roleStorageBlobDataContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
var roleAzureAIUser             = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b556d68e-0be0-4f35-a333-ad7ee1ce17ea')
var roleReader                  = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'acdd72a7-3385-48ef-bd42-f606fba81ae7')

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
  name    : 'kv-compadv-${environmentName}'
  location: location
  tags    : tags
  properties: {
    tenantId               : subscription().tenantId
    sku                    : { family: 'A', name: 'standard' }
    enableRbacAuthorization: true
    softDeleteRetentionInDays: 7
    enablePurgeProtection  : false
  }
}

// Deployer gets Secrets Officer so we can write secrets during this deployment
resource kvDeployerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(keyVault.id, deployerObjectId, 'SecretsOfficer')
  scope: keyVault
  properties: {
    roleDefinitionId: roleKvSecretsOfficer
    principalId     : deployerObjectId
    principalType   : deployerPrincipalType
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
// Storage — Agent file storage (used by Foundry Agent Service)
// ─────────────────────────────────────────────────────────────────────────────

resource storageAgent 'Microsoft.Storage/storageAccounts@2023-05-01' = {
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
// Microsoft Foundry Account (AIServices)
//
// Microsoft Foundry (AIServices): hosts model deployments and
// project management for Foundry Agent Service.
// ─────────────────────────────────────────────────────────────────────────────

var foundryName = 'aif-${prefix}'

resource foundry 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name    : foundryName
  location: location
  tags    : tags
  kind    : 'AIServices'
  sku     : { name: 'S0' }
  identity: { type: 'SystemAssigned' }
  properties: {
    allowProjectManagement : true
    customSubDomainName    : 'aif${uniq}'
    publicNetworkAccess    : 'Enabled'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Model Deployment (under the Foundry account)
// ─────────────────────────────────────────────────────────────────────────────

resource gpt4o 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = {
  parent: foundry
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
// Foundry Project
// ─────────────────────────────────────────────────────────────────────────────

var aiProjectName = 'aip-${prefix}'

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent  : foundry
  name    : aiProjectName
  location: location
  tags    : tags
  identity: { type: 'SystemAssigned' }
  properties: {
    description: 'Compliance Advisor Foundry project — agents and RAG'
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Foundry Connections (AI Search + Storage — visible to all projects)
// ─────────────────────────────────────────────────────────────────────────────

var searchConnectionName  = 'azure-ai-search'
var storageConnectionName = 'agent-storage'

resource searchConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  parent: foundry
  name  : searchConnectionName
  properties: {
    category   : 'CognitiveSearch'
    target     : 'https://${search.name}.search.windows.net'
    authType   : 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType   : 'Azure'
      ResourceId: search.id
      location  : search.location
    }
  }
}

resource storageConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  parent: foundry
  name  : storageConnectionName
  properties: {
    category   : 'AzureStorageAccount'
    target     : storageAgent.properties.primaryEndpoints.blob
    authType   : 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType   : 'Azure'
      ResourceId: storageAgent.id
      location  : storageAgent.location
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Capability Hosts (enable Foundry Agent Service)
// ─────────────────────────────────────────────────────────────────────────────

resource accountCapabilityHost 'Microsoft.CognitiveServices/accounts/capabilityHosts@2025-04-01-preview' = {
  parent: foundry
  name  : 'default'
  properties: {
    capabilityHostKind: 'Agents'
  }
  dependsOn: [searchConnection, storageConnection]
}

resource projectCapabilityHost 'Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-04-01-preview' = {
  parent: aiProject
  name  : 'default'
  properties: {
    aiServicesConnections   : [searchConnectionName, storageConnectionName]
  }
  dependsOn: [accountCapabilityHost]
}

// ─────────────────────────────────────────────────────────────────────────────
// SQL Server + Database
// ─────────────────────────────────────────────────────────────────────────────

resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name    : 'sql-${prefix}'
  location: sqlLocation
  tags    : tags
  properties: {
    administratorLogin        : sqlAdminUsername
    administratorLoginPassword: sqlAdminPassword
    minimalTlsVersion         : '1.2'
    administrators: {
      administratorType        : 'ActiveDirectory'
      principalType            : 'User'
      login                    : !empty(sqlEntraAdminLogin) ? sqlEntraAdminLogin : sqlEntraAdminName
      sid                      : sqlEntraAdminObjectId
      tenantId                 : subscription().tenantId
      azureADOnlyAuthentication: true
    }
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
  location: sqlLocation
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
  location: functionAppLocation
  tags    : tags
  kind    : 'linux'
  sku     : { name: 'B1', tier: 'Basic' }
  properties: { reserved: true }
}

resource functionApp 'Microsoft.Web/sites@2023-12-01' = {
  name    : 'func-${prefix}'
  location: functionAppLocation
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
        { name: 'AZURE_OPENAI_ENDPOINT',                value: foundry.properties.endpoint }
        { name: 'AZURE_OPENAI_DEPLOYMENT_NAME',         value: gpt4o.name }
        { name: 'AZURE_OPENAI_API_VERSION',             value: '2024-05-01-preview' }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
        { name: 'PROJECT_ENDPOINT',                     value: 'https://aif${uniq}.services.ai.azure.com/api/projects/${aiProjectName}' }
        { name: 'MSSQL_CONNECTION',                     value: 'Driver={ODBC Driver 18 for SQL Server};Server=tcp:${sqlServer.properties.fullyQualifiedDomainName},1433;Database=ComplianceAdvisor;Authentication=ActiveDirectoryManagedIdentity;Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;' }
        { name: 'GRAPH_NATIONAL_CLOUD',                 value: graphNationalCloud }
      ]
    }
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Role Assignments (RBAC — least privilege)
// ─────────────────────────────────────────────────────────────────────────────
// All access is via Azure RBAC or SQL database roles. Key Vault uses RBAC only
// (enableRbacAuthorization: true). Deployer role (kvDeployerRole) is defined
// after Key Vault; restrict or remove deployer from Key Vault in production if desired.

// Function App (MI) → Key Vault Secrets User (read secrets at runtime)
resource raFuncKv 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(keyVault.id, functionApp.id, 'SecretsUser')
  scope: keyVault
  properties: {
    roleDefinitionId: roleKvSecretsUser
    principalId     : functionApp.identity.principalId
    principalType   : 'ServicePrincipal'
  }
}

// Function App (MI) → Azure AI User on Foundry Project (invoke agents)
resource raFuncAIUser 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(aiProject.id, functionApp.id, 'AzureAIUser')
  scope: aiProject
  properties: {
    roleDefinitionId: roleAzureAIUser
    principalId     : functionApp.identity.principalId
    principalType   : 'ServicePrincipal'
  }
}

// Foundry Project (MI) → OpenAI Contributor on Foundry account (model access for agents)
resource raProjectOpenAI 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(foundry.id, aiProject.id, 'OpenAIContributor')
  scope: foundry
  properties: {
    roleDefinitionId: roleCogOpenAIContributor
    principalId     : aiProject.identity.principalId
    principalType   : 'ServicePrincipal'
  }
}

// Foundry Project (MI) → Search Index Data Reader (RAG retrieval)
resource raProjectSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(search.id, aiProject.id, 'SearchIndexDataReader')
  scope: search
  properties: {
    roleDefinitionId: roleSearchIndexDataReader
    principalId     : aiProject.identity.principalId
    principalType   : 'ServicePrincipal'
  }
}

// Foundry Project (MI) → Search Service Contributor (index management)
resource raProjectSearchContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(search.id, aiProject.id, 'SearchServiceContributor')
  scope: search
  properties: {
    roleDefinitionId: roleSearchServiceContributor
    principalId     : aiProject.identity.principalId
    principalType   : 'ServicePrincipal'
  }
}

// Foundry Project (MI) → Storage Blob Data Contributor (agent file storage)
resource raProjectStorage 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(storageAgent.id, aiProject.id, 'StorageBlobDataContributor')
  scope: storageAgent
  properties: {
    roleDefinitionId: roleStorageBlobDataContributor
    principalId     : aiProject.identity.principalId
    principalType   : 'ServicePrincipal'
  }
}

// Optional: Readers on resource group (e.g. security/ops — read-only)
resource raReaders 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (readerId, i) in readerPrincipalIds: {
  name : guid(resourceGroup().id, readerId, 'Reader-${i}')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: roleReader
    principalId     : readerId
    principalType   : readerPrincipalType
  }
}]

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
  properties: { value: foundry.listKeys().key1 }
  dependsOn: [kvDeployerRole]
}

// ─────────────────────────────────────────────────────────────────────────────
// Outputs
// ─────────────────────────────────────────────────────────────────────────────

output functionAppName      string = functionApp.name
output sqlServerFqdn        string = sqlServer.properties.fullyQualifiedDomainName
output searchEndpoint       string = 'https://${search.name}.search.windows.net'
output keyVaultUri          string = keyVault.properties.vaultUri
output foundryProjectName   string = aiProject.name
output foundryEndpoint      string = foundry.properties.endpoint
output projectEndpoint      string = 'https://aif${uniq}.services.ai.azure.com/api/projects/${aiProjectName}'
output resourceGroupName    string = resourceGroup().name
