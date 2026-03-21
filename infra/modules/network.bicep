// Virtual Network with Private Endpoint for Key Vault
//
// Provides:
// - VNet with two subnets (function-app integration + private endpoints)
// - Private Endpoint for Key Vault
// - Private DNS Zone (privatelink.vaultcore.azure.net) linked to VNet

param vnetName string
param location string
param keyVaultId string
param keyVaultName string

var vnetAddressPrefix = '10.0.0.0/16'
var funcIntegrationSubnetName = 'snet-func-integration'
var funcIntegrationSubnetPrefix = '10.0.1.0/24'
var privateEndpointsSubnetName = 'snet-private-endpoints'
var privateEndpointsSubnetPrefix = '10.0.2.0/24'

// ── Virtual Network ─────────────────────────────────────────────
resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: vnetName
  location: location
  properties: {
    addressSpace: {
      addressPrefixes: [vnetAddressPrefix]
    }
    subnets: [
      {
        name: funcIntegrationSubnetName
        properties: {
          addressPrefix: funcIntegrationSubnetPrefix
          delegations: [
            {
              name: 'delegation-web'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ]
        }
      }
      {
        name: privateEndpointsSubnetName
        properties: {
          addressPrefix: privateEndpointsSubnetPrefix
        }
      }
    ]
  }
}

// ── Private DNS Zone for Key Vault ──────────────────────────────
resource privateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.vaultcore.azure.net'
  location: 'global'
}

resource dnsVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: privateDnsZone
  name: '${vnetName}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

// ── Private Endpoint for Key Vault ──────────────────────────────
resource keyVaultPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-01-01' = {
  name: '${keyVaultName}-pe'
  location: location
  properties: {
    subnet: {
      id: vnet.properties.subnets[1].id
    }
    privateLinkServiceConnections: [
      {
        name: '${keyVaultName}-connection'
        properties: {
          privateLinkServiceId: keyVaultId
          groupIds: ['vault']
        }
      }
    ]
  }
}

resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = {
  parent: keyVaultPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-vaultcore-azure-net'
        properties: {
          privateDnsZoneId: privateDnsZone.id
        }
      }
    ]
  }
}

// ── Outputs ─────────────────────────────────────────────────────
output vnetId string = vnet.id
output funcIntegrationSubnetId string = vnet.properties.subnets[0].id
output privateEndpointsSubnetId string = vnet.properties.subnets[1].id
