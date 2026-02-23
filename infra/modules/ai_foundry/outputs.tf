output "hub_id" {
  description = "Resource ID of the AI Foundry Hub workspace"
  value       = azurerm_machine_learning_workspace.hub.id
}

output "project_id" {
  description = "Resource ID of the AI Foundry Project workspace"
  value       = azurerm_machine_learning_workspace.project.id
}

output "project_discovery_url" {
  description = "Backend discovery URL for the AI Foundry Project (used for SDK authentication)"
  value       = azurerm_machine_learning_workspace.project.discovery_url
}

output "openai_endpoint" {
  description = "Azure OpenAI HTTPS endpoint — safe to use as a plain app setting"
  value       = azurerm_cognitive_account.openai.endpoint
}

output "openai_deployment_name" {
  description = "Name of the GPT-4o model deployment"
  value       = azurerm_cognitive_deployment.gpt4o.name
}

output "appinsights_connection_string" {
  description = "Application Insights connection string for the Function App"
  value       = azurerm_application_insights.this.connection_string
  sensitive   = true
}
