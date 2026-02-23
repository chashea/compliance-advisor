variable "name" {
  description = "Base name used to derive all resource names in the module"
  type        = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "key_vault_id" {
  description = "ID of the shared Key Vault — OpenAI API key is stored here as a secret"
  type        = string
}

variable "search_endpoint" {
  description = "Azure AI Search HTTPS endpoint (used for the Hub connection)"
  type        = string
}

variable "search_admin_key" {
  description = "Azure AI Search admin key (stored only in the Hub connection, not in app settings)"
  type        = string
  sensitive   = true
}

variable "search_resource_id" {
  description = "Resource ID of the AI Search service (used for RBAC role assignment)"
  type        = string
}

variable "function_principal_id" {
  description = "Object ID of the Function App's system-assigned managed identity"
  type        = string
}

variable "tags" {
  type    = map(string)
  default = {}
}
