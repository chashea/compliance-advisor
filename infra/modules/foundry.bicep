// Azure AI Foundry (AI Services account + project)

param foundryAccountName string
param foundryProjectName string
param location string
param foundryProjectDisplayName string = 'Compliance Advisor'
param foundryProjectDescription string = 'Compliance Advisor Foundry project'

resource foundryAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: foundryAccountName
  location: location
  kind: 'AIServices'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: foundryAccountName
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
    allowProjectManagement: true
    defaultProject: foundryProjectName
  }
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-06-01' = {
  parent: foundryAccount
  name: foundryProjectName
  location: location
  properties: {
    displayName: foundryProjectDisplayName
    description: foundryProjectDescription
  }
}

output foundryAccountId string = foundryAccount.id
output foundryAccountName string = foundryAccount.name
output foundryAccountEndpoint string = foundryAccount.properties.endpoint
output foundryProjectId string = foundryProject.id
output foundryProjectName string = foundryProject.name
