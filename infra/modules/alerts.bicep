// Azure Monitor Metric Alerts

param functionAppId string
param openAiId string
param postgresServerId string
param alertEmailAddress string = ''

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = if (!empty(alertEmailAddress)) {
  name: 'cadvisor-alerts-ag'
  location: 'global'
  properties: {
    groupShortName: 'cadvisor'
    enabled: true
    emailReceivers: [
      {
        name: 'admin'
        emailAddress: alertEmailAddress
      }
    ]
  }
}

// Alert 1: Function App 5xx errors > 5 in 5 minutes
resource funcServerErrors 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'cadvisor-func-5xx'
  location: 'global'
  properties: {
    enabled: true
    severity: 1
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [functionAppId]
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'Http5xx'
          metricName: 'Http5xx'
          operator: 'GreaterThan'
          threshold: 5
          timeAggregation: 'Total'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: !empty(alertEmailAddress) ? [{ actionGroupId: actionGroup.id }] : []
  }
}

// Alert 2: Function App response time > 10s avg over 5 min
resource funcLatency 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'cadvisor-func-latency'
  location: 'global'
  properties: {
    enabled: true
    severity: 2
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [functionAppId]
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'AverageResponseTime'
          metricName: 'AverageResponseTime'
          operator: 'GreaterThan'
          threshold: 10
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: !empty(alertEmailAddress) ? [{ actionGroupId: actionGroup.id }] : []
  }
}

// Alert 3: OpenAI client errors > 10 in 5 min
resource openAiErrors 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'cadvisor-oai-errors'
  location: 'global'
  properties: {
    enabled: true
    severity: 2
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [openAiId]
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ClientErrors'
          metricName: 'ClientErrors'
          operator: 'GreaterThan'
          threshold: 10
          timeAggregation: 'Total'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: !empty(alertEmailAddress) ? [{ actionGroupId: actionGroup.id }] : []
  }
}

// Alert 4: PostgreSQL active connections > 680 (80% of D4ds_v4 max ~859)
resource pgConnections 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: 'cadvisor-pg-connections'
  location: 'global'
  properties: {
    enabled: true
    severity: 2
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [postgresServerId]
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ActiveConnections'
          metricName: 'active_connections'
          operator: 'GreaterThan'
          threshold: 680
          timeAggregation: 'Average'
          criterionType: 'StaticThresholdCriterion'
        }
      ]
    }
    actions: !empty(alertEmailAddress) ? [{ actionGroupId: actionGroup.id }] : []
  }
}
