// ============================================================
// Compliance Advisor — Azure AI Foundry Infrastructure
// Provisions: AIServices account (unified Foundry, identity required), GPT-4o deployment, AI Project
// Deploy: az deployment group create --resource-group rg-compliance-advisor --template-file infra/foundry.bicep
// ============================================================

@description('Azure region for all resources. Defaults to resource group location.')
param location string = resourceGroup().location

@description('Name for the AIServices account and child project.')
param projectName string = 'compliance-advisor'

@description('Name for the Azure AI Search service used for knowledge retrieval.')
param searchServiceName string = '${projectName}-search'

// ── Derived names ─────────────────────────────────────────────────────────────
var accountName    = projectName
var deploymentName = 'gpt-4o'

// ── AIServices account (unified Azure AI Foundry account) ─────────────────────
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: accountName
  location: location
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: accountName
    publicNetworkAccess: 'Enabled'
    allowProjectManagement: true
  }
}

// ── GPT-4o model deployment (GlobalStandard tier, 10K TPM) ───────────────────
resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-06-01' = {
  parent: aiServices
  name: deploymentName
  sku: {
    name: 'GlobalStandard'
    capacity: 10
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-08-06'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

// ── AI Project (child of AIServices account) ──────────────────────────────────
resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: aiServices
  name: projectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'Compliance Advisor conversational agent project'
  }
  dependsOn: [gpt4oDeployment]
}

// ── Azure AI Search service (knowledge index host) ─────────────────────────────
resource aiSearch 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchServiceName
  location: location
  sku: {
    name: 'basic'
  }
  properties: {
    partitionCount: 1
    replicaCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled'
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────────
@description('Paste this value into .env as AIPROJECT_ENDPOINT')
output endpoint string = 'https://${accountName}.services.ai.azure.com/api/projects/${projectName}'

@description('Paste this value into .env as AZURE_OPENAI_DEPLOYMENT')
output openAIDeploymentName string = deploymentName

@description('Paste this value into .env as AZURE_SEARCH_ENDPOINT')
output searchEndpoint string = 'https://${aiSearch.name}.search.windows.net'

@description('Paste this value into .env as AZURE_SEARCH_INDEX_NAME')
output searchIndexNameHint string = 'compliance-knowledge'
