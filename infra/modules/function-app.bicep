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

// PostgreSQL (Entra-ID-only auth from this app)
param postgresHost string
param postgresDatabase string = 'compliance_advisor'

// Azure OpenAI
param azureOpenAiEndpoint string = ''

// VNet integration
param virtualNetworkSubnetId string = ''

// EasyAuth params
param entraClientId string = ''
param entraTenantId string = subscription().tenantId

// Per-tenant ingest auth (Entra-issued bearer tokens)
@description('Audience claim required on ingest JWTs (e.g. api://compliance-advisor-ingest).')
param ingestAudience string = ''
@description('Expected appid/azp claim on ingest JWTs (the collector app registration client ID).')
param ingestExpectedAppId string = ''

// Service Bus (queue trigger for tenant collection)
@description('Fully qualified Service Bus namespace, e.g. cadvisor-sb-xxxxx.servicebus.windows.net')
param serviceBusNamespace string = ''
@description('Queue name for tenant collection messages.')
param serviceBusQueueName string = 'tenant-collect'

@description('When true, the collector uses federated workload identity (no CLIENT_SECRET in Key Vault).')
param collectorUseFederated bool = false

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
        // PostgreSQL via Entra ID — no password. The MI's name in PG must
        // match the Function App name (registered via pgaadauth_create_principal
        // by the deployer post-deploy).
        { name: 'PG_USE_AAD', value: 'true' }
        { name: 'PG_HOST', value: postgresHost }
        { name: 'PG_DATABASE', value: postgresDatabase }
        { name: 'PG_USER', value: functionAppName }
        { name: 'KEY_VAULT_URL', value: keyVaultUri }
        { name: 'WEBSITE_RUN_FROM_PACKAGE', value: '1' }
        { name: 'ALLOWED_TENANT_IDS', value: allowedTenantIds }
        { name: 'AZURE_OPENAI_ENDPOINT', value: azureOpenAiEndpoint }
        { name: 'COLLECTOR_CLIENT_ID', value: '@Microsoft.KeyVault(SecretUri=${keyVaultUri}secrets/gcc-client-id/)' }
        { name: 'COLLECTOR_CLIENT_SECRET', value: collectorUseFederated ? '' : '@Microsoft.KeyVault(SecretUri=${keyVaultUri}secrets/gcc-password/)' }
        { name: 'COLLECTOR_USE_FEDERATED', value: collectorUseFederated ? 'true' : 'false' }
        { name: 'WEBSITE_CONTENTOVERVNET', value: !empty(virtualNetworkSubnetId) ? '1' : '0' }
        { name: 'AUTH_REQUIRED', value: !empty(entraClientId) ? 'true' : 'false' }
        { name: 'INGEST_REQUIRE_JWT', value: !empty(ingestAudience) ? 'true' : 'false' }
        { name: 'INGEST_AUDIENCE', value: ingestAudience }
        { name: 'INGEST_EXPECTED_APPID', value: ingestExpectedAppId }
        { name: 'RATE_LIMIT_BACKEND', value: 'table' }
        { name: 'RATE_LIMIT_STORAGE_ACCOUNT', value: storageAccountName }
        { name: 'RATE_LIMIT_MAX', value: '10' }
        { name: 'RATE_LIMIT_WINDOW_SECONDS', value: '60' }
        // Service Bus identity-based binding. Trigger refers to "ServiceBus__fullyQualifiedNamespace"
        // via the connection string "ServiceBus" in the @bp.service_bus_queue_trigger decorator.
        { name: 'ServiceBus__fullyQualifiedNamespace', value: serviceBusNamespace }
        { name: 'SERVICE_BUS_NAMESPACE', value: serviceBusNamespace }
        { name: 'SERVICE_BUS_QUEUE_NAME', value: serviceBusQueueName }
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
      unauthenticatedClientAction: 'Return401'
      excludedPaths: [
        '/api/health'
        '/api/tenants/callback'
        '/api/ingest'
        '/api/collect/{tenant_id}'
        '/api/hunt/{tenant_id}'
        '/api/tenants'
        '/api/admin/migrate'
      ]
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

// ── Staging deployment slot (#22) ────────────────────────────────
// Used by the deploy workflow: deploy → smoke-test → swap on green.
// Inherits the production app settings except those marked sticky here.
// The slot uses the same managed identity (parent's MI) so RBAC carries
// over. The slot also uses the same database — bad staging deploys can
// corrupt data; mitigation is the smoke test gate plus PG backups.

resource stagingSlot 'Microsoft.Web/sites/slots@2023-01-01' = {
  parent: functionApp
  name: 'staging'
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
      // Same app settings as production. The slot-setting list below
      // marks the few that should NOT be swapped (so production keeps
      // its own RATE_LIMIT_BACKEND, etc.) — see slotConfigNames below.
      appSettings: functionApp.properties.siteConfig.appSettings
    }
  }
}

// Mark which app-setting names stay with the slot during a swap.
// AzureWebJobsStorage and the Service Bus binding stay with their
// environment so staging never accidentally writes to a prod-only queue.
resource slotConfigNames 'Microsoft.Web/sites/config@2023-01-01' = {
  parent: functionApp
  name: 'slotConfigNames'
  properties: {
    appSettingNames: [
      'AzureWebJobsStorage__accountName'
      'ServiceBus__fullyQualifiedNamespace'
      'SERVICE_BUS_NAMESPACE'
      'AUTH_REQUIRED'
    ]
  }
}

output functionAppUrl string = 'https://${functionApp.properties.defaultHostName}'
output stagingSlotUrl string = 'https://${stagingSlot.properties.defaultHostName}'
output functionAppPrincipalId string = functionApp.identity.principalId
output stagingSlotPrincipalId string = stagingSlot.identity.principalId
output functionAppName string = functionApp.name
output functionAppId string = functionApp.id
