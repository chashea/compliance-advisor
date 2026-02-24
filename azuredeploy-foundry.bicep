// ─────────────────────────────────────────────────────────────────────────────
// Compliance Advisor — AI Foundry-only deployment
//
// Deploys: Key Vault · AI Foundry Hub + Project · Hub Connections (OpenAI + Search)
// References existing: App Insights · Storage · ACR · OpenAI · AI Search
// ─────────────────────────────────────────────────────────────────────────────

@description('Short environment label used in resource names.')
@allowed(['dev', 'staging', 'prod'])
param environmentName string = 'dev'

param location string = resourceGroup().location

@description('Object ID of the deployer for Key Vault RBAC.')
param deployerObjectId string

@allowed(['User', 'ServicePrincipal', 'Group'])
param deployerPrincipalType string = 'User'

// ── Naming ────────────────────────────────────────────────────────────────────
var prefix = 'compliance-advisor-${environmentName}'
var uniq   = uniqueString(resourceGroup().id)

var tags = {
  environment: environmentName
  project    : 'compliance-advisor'
  managedBy  : 'arm-template'
}

// ── Role Definition IDs ───────────────────────────────────────────────────────
var roleKvSecretsOfficer     = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
var roleCogOpenAIContributor = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a001fd3d-188f-4b5d-821b-7da978bf7442')
var roleSearchIndexDataReader = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
var roleAcrPull              = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

// ── Reference existing resources ──────────────────────────────────────────────
resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: 'appi-${prefix}'
}

resource storageHub 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: 'staih${uniq}'
}

resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: 'acr${uniq}'
}

resource openai 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' existing = {
  name: 'oai-${prefix}'
}

resource search 'Microsoft.Search/searchServices@2024-03-01-preview' existing = {
  name: 'srch-${prefix}'
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
    softDeleteRetentionInDays: 90
  }
}

resource kvDeployerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(keyVault.id, deployerObjectId, 'SecretsOfficer')
  scope: keyVault
  properties: {
    roleDefinitionId: roleKvSecretsOfficer
    principalId     : deployerObjectId
    principalType   : deployerPrincipalType
  }
}

// ── Key Vault Secrets ─────────────────────────────────────────────────────────
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
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Hub Connections
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
// Role Assignments
// ─────────────────────────────────────────────────────────────────────────────

// AI Project → OpenAI Contributor
resource raProjectOpenAI 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(openai.id, aiProject.id, 'OpenAIContributor')
  scope: openai
  properties: {
    roleDefinitionId: roleCogOpenAIContributor
    principalId     : aiProject.identity.principalId
    principalType   : 'ServicePrincipal'
  }
}

// AI Project → Search Index Data Reader
resource raProjectSearch 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name : guid(search.id, aiProject.id, 'SearchIndexDataReader')
  scope: search
  properties: {
    roleDefinitionId: roleSearchIndexDataReader
    principalId     : aiProject.identity.principalId
    principalType   : 'ServicePrincipal'
  }
}

// AI Hub → ACR Pull
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
// Outputs
// ─────────────────────────────────────────────────────────────────────────────
output keyVaultUri          string = keyVault.properties.vaultUri
output aiFoundryHubName     string = aiHub.name
output aiFoundryProjectName string = aiProject.name
output openaiEndpoint       string = openai.properties.endpoint
output searchEndpoint       string = 'https://${search.name}.search.windows.net'
