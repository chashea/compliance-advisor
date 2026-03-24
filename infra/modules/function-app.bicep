// Azure Function App (Python v2, Linux, P1v3 Premium)
// With Entra ID SSO (EasyAuth) for API consumers

param functionAppName string
param appServicePlanName string
param location string
param storageAccountName string
param appInsightsInstrumentationKey string
param appInsightsConnectionString string
param keyVaultUri string
param allowedTenantIds string

// Azure OpenAI
param azureOpenAiEndpoint string = ''

// VNet integration
param virtualNetworkSubnetId string = ''

// EasyAuth params
param entraClientId string = ''
param entraTenantId string = subscription().tenantId

resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: appServicePlanName
  location: location
  kind: 'linux'
  sku: {
    name: 'P1v3'
    tier: 'PremiumV3'
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
    virtualNetworkSubnetId: !empty(virtualNetworkSubnetId) ? virtualNetworkSubnetId : null
    vnetRouteAllEnabled: !empty(virtualNetworkSubnetId)
    siteConfig: {
      alwaysOn: true
      healthCheckPath: '/api/health'
      pythonVersion: '3.12'
      linuxFxVersion: 'PYTHON|3.12'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      cors: {
        allowedOrigins: ['https://cadvisor-web-prod.azurewebsites.net']
      }
      appSettings: [
        { name: 'AzureWebJobsStorage__accountName', value: storageAccountName }
        { name: 'FUNCTIONS_EXTENSION_VERSION', value: '~4' }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'AzureWebJobsFeatureFlags', value: 'EnableWorkerIndexing' }
        { name: 'ENABLE_ORYX_BUILD', value: 'true' }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'true' }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsightsInstrumentationKey }
        { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsightsConnectionString }
        { name: 'DATABASE_URL', value: '@Microsoft.KeyVault(SecretUri=${keyVaultUri}secrets/database-url/)' }
        { name: 'KEY_VAULT_URL', value: keyVaultUri }
        { name: 'WEBSITE_RUN_FROM_PACKAGE', value: '1' }
        { name: 'ALLOWED_TENANT_IDS', value: allowedTenantIds }
        { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAiEndpoint }
        { name: 'COLLECTOR_CLIENT_ID', value: '@Microsoft.KeyVault(SecretUri=${keyVaultUri}secrets/gcc-client-id/)' }
        { name: 'COLLECTOR_CLIENT_SECRET', value: '@Microsoft.KeyVault(SecretUri=${keyVaultUri}secrets/gcc-password/)' }
        { name: 'WEBSITE_CONTENTOVERVNET', value: !empty(virtualNetworkSubnetId) ? '1' : '0' }
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
      unauthenticatedClientAction: 'AllowAnonymous'
    }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: {
          clientId: entraClientId
          openIdIssuer: 'https://login.microsoftonline.com/${entraTenantId}/v2.0'
        }
        validation: {
          allowedAudiences: [
            'api://${entraClientId}'
          ]
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
