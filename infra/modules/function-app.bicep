// Azure Function App (Python v2, Linux, Consumption)
// With Entra ID SSO (EasyAuth) and CORS for dashboard

param functionAppName string
param appServicePlanName string
param location string
param storageAccountName string
param storageAccountId string
param appInsightsInstrumentationKey string
param appInsightsConnectionString string
param keyVaultUri string
param openAiEndpoint string
param openAiDeployment string
param foundryAccountEndpoint string = ''
param foundryProjectEndpoint string = ''
param foundryProjectName string = ''
param foundryProjectId string = ''
param foundryAgentId string = ''
param allowedTenantIds string

// EasyAuth params
param entraClientId string = ''
param entraTenantId string = subscription().tenantId

resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: appServicePlanName
  location: location
  kind: 'linux'
  sku: {
    name: 'Y1'
    tier: 'Dynamic'
  }
  properties: {
    reserved: true
  }
}

resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: functionAppName
  location: location
  kind: 'functionapp,linux'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      pythonVersion: '3.11'
      linuxFxVersion: 'PYTHON|3.11'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      cors: {
        allowedOrigins: ['*']
      }
      appSettings: [
        { name: 'AzureWebJobsStorage', value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};EndpointSuffix=core.windows.net;AccountKey=${listKeys(storageAccountId, '2023-01-01').keys[0].value}' }
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'AzureWebJobsFeatureFlags', value: 'EnableWorkerIndexing' }
        { name: 'ENABLE_ORYX_BUILD', value: 'true' }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsightsInstrumentationKey }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
        { name: 'DATABASE_URL', value: '@Microsoft.KeyVault(SecretUri=${keyVaultUri}secrets/database-url/)' }
        { name: 'KEY_VAULT_URL', value: keyVaultUri }
        { name: 'AZURE_OPENAI_ENDPOINT', value: openAiEndpoint }
        { name: 'AZURE_OPENAI_DEPLOYMENT', value: openAiDeployment }
        { name: 'AZURE_OPENAI_API_VERSION', value: '2024-08-01-preview' }
        { name: 'AZURE_FOUNDRY_ACCOUNT_ENDPOINT', value: foundryAccountEndpoint }
        { name: 'AZURE_FOUNDRY_PROJECT_ENDPOINT', value: foundryProjectEndpoint }
        { name: 'AZURE_FOUNDRY_PROJECT_NAME', value: foundryProjectName }
        { name: 'AZURE_FOUNDRY_PROJECT_ID', value: foundryProjectId }
        { name: 'AZURE_FOUNDRY_AGENT_ID', value: foundryAgentId }
        { name: 'ALLOWED_TENANT_IDS', value: allowedTenantIds }
      ]
    }
  }
}

// Entra ID SSO (EasyAuth)
resource authSettings 'Microsoft.Web/sites/config@2023-01-01' = if (!empty(entraClientId)) {
  parent: functionApp
  name: 'authsettingsV2'
  properties: {
    globalValidation: {
      requireAuthentication: true
      unauthenticatedClientAction: 'RedirectToLoginPage'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: entraClientId
          openIdIssuer: 'https://login.microsoftonline.com/${entraTenantId}/v2.0'
        }
      }
    }
    login: {
      tokenStore: {
        enabled: true
      }
    }
  }
}

output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output functionAppPrincipalId string = functionApp.identity.principalId
output functionAppName string = functionApp.name
output functionAppId string = functionApp.id
