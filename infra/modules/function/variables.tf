variable "name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "sql_connection" {
  type      = string
  sensitive = true
}

variable "key_vault_url" {
  type = string
}

variable "search_endpoint" {
  type = string
}

variable "openai_endpoint" {
  description = "Azure OpenAI HTTPS endpoint — stored as a plain app setting (not a secret)"
  type        = string
}

variable "openai_deployment" {
  description = "Name of the GPT-4o model deployment"
  type        = string
}

variable "appinsights_connection_string" {
  description = "Application Insights connection string for distributed tracing"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_api_version" {
  description = "Azure OpenAI API version used by SDK calls"
  type        = string
  default     = "2024-12-01-preview"
}

variable "cors_allowed_origins" {
  type        = list(string)
  description = "Allowed CORS origins. Use specific domains — never '*'."
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
