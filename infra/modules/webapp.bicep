// Azure Web App (Node 20 LTS, Linux, P1v3) — SPA frontend for Compliance Advisor

param webAppName string
param webAppPlanName string
param location string
param functionAppUrl string
param virtualNetworkSubnetId string = ''

// EasyAuth params
param entraClientId string = ''
param entraTenantId string = subscription().tenantId

resource webAppPlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: webAppPlanName
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

resource webApp 'Microsoft.Web/sites@2023-01-01' = {
  name: webAppName
  location: location
  kind: 'app,linux'
  properties: {
    serverFarmId: webAppPlan.id
    httpsOnly: true
    virtualNetworkSubnetId: !empty(virtualNetworkSubnetId) ? virtualNetworkSubnetId : null
    vnetRouteAllEnabled: !empty(virtualNetworkSubnetId)
    siteConfig: {
      alwaysOn: true
      linuxFxVersion: 'NODE|20-lts'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appCommandLine: 'pm2 serve /home/site/wwwroot --no-daemon --spa'
      appSettings: [
        { name: 'VITE_API_BASE_URL', value: functionAppUrl }
        { name: 'WEBSITE_VNET_ROUTE_ALL', value: !empty(virtualNetworkSubnetId) ? '1' : '0' }
      ]
    }
  }
}

// Entra ID SSO (EasyAuth) — redirects unauthenticated users to login
resource authSettings 'Microsoft.Web/sites/config@2023-01-01' = if (!empty(entraClientId)) {
  parent: webApp
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

output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
output webAppName string = webApp.name
