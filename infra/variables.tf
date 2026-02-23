variable "env" {
  description = "Environment name (dev, prod)"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.env)
    error_message = "env must be one of: dev, staging, prod."
  }
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus"
}

variable "sql_admin_username" {
  description = "SQL Server administrator login"
  type        = string
}

variable "sql_admin_password" {
  description = "SQL Server administrator password"
  type        = string
  sensitive   = true
}

variable "function_subnet_id" {
  description = "Subnet ID for the Function App VNet integration and SQL firewall rule"
  type        = string
}

variable "security_alert_emails" {
  description = "Email addresses for SQL threat detection alerts"
  type        = list(string)
  default     = []
}

variable "cors_allowed_origins" {
  description = "Allowed CORS origins for the Function App. Use specific domains — never '*'."
  type        = list(string)
  default     = []
}
