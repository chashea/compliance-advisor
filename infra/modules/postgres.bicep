// Azure Database for PostgreSQL Flexible Server
//
// Production posture: public network DISABLED, password auth DISABLED.
// Authentication is exclusively via Microsoft Entra ID (managed identities
// + Entra admin principals). The administratorPassword is required by the
// Bicep API but is never used at runtime; it acts as a sealed break-glass
// credential. Rotate immediately after deployment and store in Key Vault.

param serverName string
param location string
param administratorLogin string = 'cadvisor_admin'

@secure()
@description('Required by the API; never used at runtime once passwordAuth is disabled. Rotate post-deploy.')
param administratorPassword string

@description('Object ID of the Entra principal that becomes the PostgreSQL Entra admin (deployer or break-glass group).')
param entraAdminObjectId string = ''

@description('Display name (UPN or group name) of the Entra admin principal. Required when entraAdminObjectId is set.')
param entraAdminPrincipalName string = ''

@allowed(['User', 'Group', 'ServicePrincipal'])
param entraAdminPrincipalType string = 'User'

param skuName string = 'Standard_D4ds_v4'
param skuTier string = 'GeneralPurpose'
param storageSizeGB int = 32

@allowed(['Disabled', 'ZoneRedundant'])
param highAvailabilityMode string = 'Disabled'

resource postgresServer 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: serverName
  location: location
  sku: {
    name: skuName
    tier: skuTier
  }
  properties: {
    version: '16'
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorPassword
    storage: {
      storageSizeGB: storageSizeGB
    }
    backup: {
      backupRetentionDays: 35
      geoRedundantBackup: 'Enabled'
    }
    highAvailability: {
      mode: highAvailabilityMode
    }
    authConfig: {
      activeDirectoryAuth: 'Enabled'
      passwordAuth: 'Disabled'
      tenantId: subscription().tenantId
    }
    network: {
      publicNetworkAccess: 'Disabled'
    }
  }
}

// Database
resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: postgresServer
  name: 'compliance_advisor'
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

// ── pg_stat_statements (server-side query observability) ────────
// Enabling the extension requires two steps:
//   1. Set shared_preload_libraries=pg_stat_statements (server config; restart on change).
//   2. CREATE EXTENSION pg_stat_statements (per-database; runs in migration 0004).
resource preloadLibsConfig 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2023-06-01-preview' = {
  parent: postgresServer
  name: 'shared_preload_libraries'
  properties: {
    value: 'pg_stat_statements'
    source: 'user-override'
  }
}

resource pgssTrackConfig 'Microsoft.DBforPostgreSQL/flexibleServers/configurations@2023-06-01-preview' = {
  parent: postgresServer
  name: 'pg_stat_statements.track'
  properties: {
    value: 'all'
    source: 'user-override'
  }
}

// Entra ID administrator (deployer or break-glass group). Required for
// running schema migrations and bootstrapping role grants for the Function
// App's managed identity.
resource entraAdmin 'Microsoft.DBforPostgreSQL/flexibleServers/administrators@2023-06-01-preview' = if (!empty(entraAdminObjectId) && !empty(entraAdminPrincipalName)) {
  parent: postgresServer
  name: entraAdminObjectId
  properties: {
    principalType: entraAdminPrincipalType
    principalName: entraAdminPrincipalName
    tenantId: subscription().tenantId
  }
}

output serverFqdn string = postgresServer.properties.fullyQualifiedDomainName
output serverId string = postgresServer.id
output serverName string = postgresServer.name
output databaseName string = database.name
// NOTE: connectionString output intentionally removed — it embedded the
// admin password in plaintext and surfaced in deployment history. Runtime
// access is now Entra-only; consumers build connection strings at call
// time using the host/database outputs and a freshly acquired AAD token.
