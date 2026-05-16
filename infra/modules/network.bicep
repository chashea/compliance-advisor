// Virtual Network with Private Endpoints for Key Vault, PostgreSQL, OpenAI,
// and the Function App's runtime Storage Account (blob/queue/table).
//
// Provides:
// - VNet with two subnets (function-app integration + private endpoints)
// - NSGs on both subnets
// - Private Endpoints for Key Vault, PostgreSQL, OpenAI, and Storage (blob/queue/table)
// - Private DNS Zones linked to VNet
//
// The storage private endpoints are required so the Functions host can read
// its function-key secret repository (blob), distributed rate-limit state
// (table), and host queue state (queue) once the storage account has
// publicNetworkAccess=Disabled.

param vnetName string
param location string
param keyVaultId string
param keyVaultName string
param postgresServerId string
param postgresServerName string
param openAiId string = ''
param openAiName string = ''
param storageAccountId string = ''
param storageAccountName string = ''

var vnetAddressPrefix = '10.0.0.0/16'
var funcIntegrationSubnetName = 'snet-func-integration'
var funcIntegrationSubnetPrefix = '10.0.1.0/24'
var privateEndpointsSubnetName = 'snet-private-endpoints'
var privateEndpointsSubnetPrefix = '10.0.2.0/24'

// ── Network Security Groups ────────────────────────────────────
resource nsgFunc 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: 'nsg-func-integration'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowVNetOutbound'
        properties: {
          priority: 100
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRanges: ['443', '5432']
        }
      }
      {
        name: 'AllowInternetOutbound'
        properties: {
          priority: 110
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'Internet'
          destinationPortRange: '443'
        }
      }
    ]
  }
}

resource nsgPe 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: 'nsg-private-endpoints'
  location: location
  properties: {
    securityRules: [
      {
        name: 'AllowFuncSubnetHttps'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: funcIntegrationSubnetPrefix
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '443'
        }
      }
      {
        name: 'AllowFuncSubnetPostgres'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: funcIntegrationSubnetPrefix
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '5432'
        }
      }
      {
        name: 'DenyAllInbound'
        properties: {
          priority: 4096
          direction: 'Inbound'
          access: 'Deny'
          protocol: '*'
          sourceAddressPrefix: '*'
          sourcePortRange: '*'
          destinationAddressPrefix: '*'
          destinationPortRange: '*'
        }
      }
    ]
  }
}

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
          networkSecurityGroup: {
            id: nsgFunc.id
          }
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
          networkSecurityGroup: {
            id: nsgPe.id
          }
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

// ── Private DNS Zone for PostgreSQL ───────────────────────────────
resource postgresPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = {
  name: 'privatelink.postgres.database.azure.com'
  location: 'global'
}

resource postgresDnsVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = {
  parent: postgresPrivateDnsZone
  name: '${vnetName}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

// ── Private Endpoint for PostgreSQL ───────────────────────────────
resource postgresPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-01-01' = {
  name: '${postgresServerName}-pe'
  location: location
  properties: {
    subnet: {
      id: vnet.properties.subnets[1].id
    }
    privateLinkServiceConnections: [
      {
        name: '${postgresServerName}-connection'
        properties: {
          privateLinkServiceId: postgresServerId
          groupIds: ['postgresqlServer']
        }
      }
    ]
  }
}

resource postgresPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = {
  parent: postgresPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-postgres-database-azure-com'
        properties: {
          privateDnsZoneId: postgresPrivateDnsZone.id
        }
      }
    ]
  }
}

// ── Private DNS Zone for OpenAI ──────────────────────────────────
resource openAiPrivateDnsZone 'Microsoft.Network/privateDnsZones@2024-06-01' = if (!empty(openAiId)) {
  name: 'privatelink.openai.azure.com'
  location: 'global'
}

resource openAiDnsVnetLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = if (!empty(openAiId)) {
  parent: openAiPrivateDnsZone
  name: '${vnetName}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}

// ── Private Endpoint for OpenAI ──────────────────────────────────
resource openAiPrivateEndpoint 'Microsoft.Network/privateEndpoints@2024-01-01' = if (!empty(openAiId)) {
  name: '${openAiName}-pe'
  location: location
  properties: {
    subnet: {
      id: vnet.properties.subnets[1].id
    }
    privateLinkServiceConnections: [
      {
        name: '${openAiName}-connection'
        properties: {
          privateLinkServiceId: openAiId
          groupIds: ['account']
        }
      }
    ]
  }
}

resource openAiPrivateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = if (!empty(openAiId)) {
  parent: openAiPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-openai-azure-com'
        properties: {
          privateDnsZoneId: openAiPrivateDnsZone.id
        }
      }
    ]
  }
}

// ── Storage Account Private Endpoints (blob / queue / table) ─────
// The Functions host stores its function-key secret repository in Blob
// Storage and uses Queue/Table for host state and the distributed rate
// limiter. When the storage account has publicNetworkAccess=Disabled, the
// host must reach these sub-resources via private endpoints over the VNet
// integration subnet, otherwise keyed routes return HTTP 500.

var storageSubResources = [
  { name: 'blob', dnsZone: 'privatelink.blob.${environment().suffixes.storage}' }
  { name: 'queue', dnsZone: 'privatelink.queue.${environment().suffixes.storage}' }
  { name: 'table', dnsZone: 'privatelink.table.${environment().suffixes.storage}' }
]

resource storagePrivateDnsZones 'Microsoft.Network/privateDnsZones@2024-06-01' = [for s in storageSubResources: if (!empty(storageAccountId)) {
  name: s.dnsZone
  location: 'global'
}]

resource storageDnsVnetLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (s, i) in storageSubResources: if (!empty(storageAccountId)) {
  parent: storagePrivateDnsZones[i]
  name: '${vnetName}-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}]

resource storagePrivateEndpoints 'Microsoft.Network/privateEndpoints@2024-01-01' = [for (s, i) in storageSubResources: if (!empty(storageAccountId)) {
  name: '${storageAccountName}-${s.name}-pe'
  location: location
  properties: {
    subnet: {
      id: vnet.properties.subnets[1].id
    }
    privateLinkServiceConnections: [
      {
        name: '${storageAccountName}-${s.name}-connection'
        properties: {
          privateLinkServiceId: storageAccountId
          groupIds: [s.name]
        }
      }
    ]
  }
}]

resource storagePrivateDnsZoneGroups 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = [for (s, i) in storageSubResources: if (!empty(storageAccountId)) {
  parent: storagePrivateEndpoints[i]
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: replace(s.dnsZone, '.', '-')
        properties: {
          privateDnsZoneId: storagePrivateDnsZones[i].id
        }
      }
    ]
  }
}]

// ── Outputs ─────────────────────────────────────────────────────
output vnetId string = vnet.id
output funcIntegrationSubnetId string = vnet.properties.subnets[0].id
output privateEndpointsSubnetId string = vnet.properties.subnets[1].id
