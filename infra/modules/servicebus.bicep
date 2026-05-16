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
//
// NOTE: Role assignments live in main.bicep (sbSenderRole +
// sbReceiverRole) instead of here to avoid a circular dependency with
// the function-app module — main.bicep already references the function
// app's MI for other RBAC, so the SB grants belong there too.

param namespaceName string
param location string

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

output namespaceName string = namespace.name
output namespaceId string = namespace.id
output namespaceFqdn string = '${namespace.name}.servicebus.windows.net'
output queueName string = collectQueue.name
