// Azure OpenAI (Cognitive Services) — gpt-4o deployment

param openAiName string
param location string

resource openAi 'Microsoft.CognitiveServices/accounts@2024-04-01-preview' = {
  name: openAiName
  location: location
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: openAiName
    publicNetworkAccess: 'Enabled'
  }
}

resource gpt4oDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-04-01-preview' = {
  parent: openAi
  name: 'gpt-4o'
  sku: {
    name: 'Standard'
    capacity: 30
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-08-06'
    }
  }
}

output openAiEndpoint string = openAi.properties.endpoint
output openAiId string = openAi.id
output openAiName string = openAi.name
