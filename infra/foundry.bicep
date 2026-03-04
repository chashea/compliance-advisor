// ============================================================
// Compliance Advisor — Azure AI Foundry Infrastructure
// Provisions: Azure OpenAI, GPT-4o deployment, AI Hub, AI Project
// Deploy: az deployment group create --resource-group rg-compliance-advisor --template-file infra/foundry.bicep
// ============================================================

@description('Azure region for all resources. Defaults to resource group location.')
param location string = resourceGroup().location

@description('Name for the AI Project (also used for Hub and OpenAI resource naming).')
param projectName string = 'compliance-advisor'

// ── Derived names ─────────────────────────────────────────────────────────────
var openAIName   = '${projectName}-openai'
var hubName      = '${projectName}-hub'
var deploymentName = 'gpt-4o'

// ── Azure OpenAI account ───────────────────────────────────────────────────────
resource openAI 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: openAIName
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: openAIName
    publicNetworkAccess: 'Enabled'
  }
}

// ── GPT-4o model deployment (Standard tier, 10K TPM) ──────────────────────────
resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = {
  parent: openAI
  name: deploymentName
  sku: {
    name: 'Standard'
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

// ── AI Hub (Machine Learning workspace, kind: Hub) ────────────────────────────
resource aiHub 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: hubName
  location: location
  kind: 'Hub'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: '${projectName} Hub'
    description: 'AI Hub for Compliance Advisor agent'
    publicNetworkAccess: 'Enabled'
  }
}

// ── Connection: Hub → Azure OpenAI ────────────────────────────────────────────
resource openAIConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-04-01' = {
  parent: aiHub
  name: 'openai-connection'
  properties: {
    category: 'AzureOpenAI'
    target: openAI.properties.endpoint
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: openAI.listKeys().key1
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: openAI.id
      DeploymentApiVersion: '2024-02-01'
    }
  }
  dependsOn: [gpt4oDeployment]
}

// ── AI Project (Machine Learning workspace, kind: Project) ────────────────────
resource aiProject 'Microsoft.MachineLearningServices/workspaces@2024-04-01' = {
  name: projectName
  location: location
  kind: 'Project'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    friendlyName: 'Compliance Advisor'
    description: 'Compliance Advisor conversational agent project'
    hubResourceId: aiHub.id
    publicNetworkAccess: 'Enabled'
  }
}

// ── Outputs ───────────────────────────────────────────────────────────────────
@description('Paste this value into .env as AIPROJECT_CONNECTION_STRING')
output connectionString string = '${location}.api.azureml.ms;${subscription().subscriptionId};${resourceGroup().name};${projectName}'

@description('Paste this value into .env as AZURE_OPENAI_DEPLOYMENT')
output openAIDeploymentName string = deploymentName
