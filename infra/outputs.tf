output "function_app_name" {
  description = "Azure Function App name"
  value       = module.function.name
}

output "sql_server_fqdn" {
  description = "SQL Server FQDN"
  value       = module.sql.server_fqdn
  sensitive   = true   # Avoid leaking infrastructure topology in logs
}

output "search_endpoint" {
  description = "Azure AI Search endpoint"
  value       = module.search.endpoint
  sensitive   = true
}

output "key_vault_uri" {
  description = "Key Vault URI"
  value       = module.keyvault.vault_uri
  sensitive   = true
}

output "resource_group_name" {
  description = "Resource group name"
  value       = azurerm_resource_group.main.name
}

# ── AI Foundry ────────────────────────────────────────────────────────────────

output "ai_foundry_hub_id" {
  description = "Resource ID of the AI Foundry Hub workspace"
  value       = module.ai_foundry.hub_id
}

output "ai_foundry_project_id" {
  description = "Resource ID of the AI Foundry Project workspace"
  value       = module.ai_foundry.project_id
}

output "ai_foundry_project_discovery_url" {
  description = "Backend discovery URL for the AI Foundry Project (SDK authentication)"
  value       = module.ai_foundry.project_discovery_url
  sensitive   = true
}

output "openai_endpoint" {
  description = "Azure OpenAI HTTPS endpoint"
  value       = module.ai_foundry.openai_endpoint
  sensitive   = true
}

output "openai_deployment_name" {
  description = "Name of the GPT-4o model deployment"
  value       = module.ai_foundry.openai_deployment_name
}
