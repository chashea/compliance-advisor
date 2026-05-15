// Azure Service Bus — namespace + tenant collection queue
//
// Used to durably hand off per-tenant collection jobs from the
// fire-and-forget /api/tenants and /api/tenants/callback endpoints to
// a queue-triggered Function. Replaces the in-process ThreadPoolExecutor
// that silently dropped work on instance recycle / scale-in.
//
// Standard SKU because we need:
//   - Dead-letter queue (Basic doesn't expose it for management)
//   - Message TTL > 14 days (Basic caps at 14)
//   - Authorization rules disabled — managed-identity-only access

param namespaceName string
param location string
@description('Object ID of the Function App MI that needs Send + Receive on the queue.')
param functionAppPrincipalId string

resource namespace 'Microsoft.ServiceBus/namespaces@2024-01-01' = {
  name: namespaceName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Standard'
  }
  properties: {
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
    disableLocalAuth: true
  }
}

resource collectQueue 'Microsoft.ServiceBus/namespaces/queues@2024-01-01' = {
  parent: namespace
  name: 'tenant-collect'
  properties: {
    maxDeliveryCount: 5
    defaultMessageTimeToLive: 'P7D'
    deadLetteringOnMessageExpiration: true
    enableBatchedOperations: true
    lockDuration: 'PT5M'
    duplicateDetectionHistoryTimeWindow: 'PT10M'
    requiresDuplicateDetection: true
  }
}

// Azure Service Bus Data Sender — for posting from registration/callback handlers
resource sbSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(namespace.id, functionAppPrincipalId, '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39')
  scope: namespace
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39'
    )
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Azure Service Bus Data Receiver — for the queue-trigger function
resource sbReceiverRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(namespace.id, functionAppPrincipalId, '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0')
  scope: namespace
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0'
    )
    principalId: functionAppPrincipalId
    principalType: 'ServicePrincipal'
  }
}

output namespaceName string = namespace.name
output namespaceId string = namespace.id
output namespaceFqdn string = '${namespace.name}.servicebus.windows.net'
output queueName string = collectQueue.name
