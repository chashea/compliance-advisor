// Azure OpenAI Service (Commercial)

param openAiName string
param location string
param deploymentModel string = 'gpt-4o'

resource openAi 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: openAiName
  location: location
  kind: 'OpenAI'
  sku: { name: 'S0' }
  properties: {
    customSubDomainName: openAiName
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openAi
  name: deploymentModel
  sku: {
    name: 'Standard'
    capacity: 30
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: deploymentModel
      version: '2024-08-06'
    }
  }
}

output openAiEndpoint string = openAi.properties.endpoint
output openAiId string = openAi.id
output openAiName string = openAi.name
