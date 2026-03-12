// Azure Web App (Node 20 LTS, Linux, B1) — SPA frontend for Compliance Advisor

param webAppName string
param webAppPlanName string
param location string
param functionAppUrl string

resource webAppPlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: webAppPlanName
  location: location
  kind: 'linux'
  sku: {
    name: 'B1'
    tier: 'Basic'
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
    siteConfig: {
      linuxFxVersion: 'NODE|20-lts'
      minTlsVersion: '1.2'
      ftpsState: 'Disabled'
      appCommandLine: 'pm2 serve /home/site/wwwroot/dist --no-daemon --spa'
      appSettings: [
        { name: 'VITE_API_BASE_URL', value: functionAppUrl }
      ]
    }
  }
}

output webAppUrl string = 'https://${webApp.properties.defaultHostName}'
output webAppName string = webApp.name
