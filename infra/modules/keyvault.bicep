// Azure Key Vault

param keyVaultName string
param location string
param deployerObjectId string

@secure()
param databaseUrl string = ''

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: location
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 90
    enablePurgeProtection: true
    publicNetworkAccess: 'Disabled'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

// Store database connection string
resource dbSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (!empty(databaseUrl)) {
  parent: keyVault
  name: 'database-url'
  properties: {
    value: databaseUrl
  }
}

// Grant deployer Key Vault Administrator role
resource deployerRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (!empty(deployerObjectId)) {
  name: guid(keyVault.id, deployerObjectId, '00482a5a-887f-4fb3-b363-3b7fe8e74483')
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '00482a5a-887f-4fb3-b363-3b7fe8e74483')
    principalId: deployerObjectId
    principalType: 'User'
  }
}

output keyVaultUri string = keyVault.properties.vaultUri
output keyVaultId string = keyVault.id
output keyVaultName string = keyVault.name
