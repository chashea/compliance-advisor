variable "server_name" {
  type = string
}

variable "database_name" {
  type = string
}

variable "resource_group_name" {
  type = string
}

variable "location" {
  type = string
}

variable "admin_username" {
  type = string
}

variable "admin_password" {
  type      = string
  sensitive = true
}

variable "function_subnet_id" {
  type        = string
  description = "Subnet ID of the Function App for the VNet SQL firewall rule"
}

variable "security_alert_emails" {
  type        = list(string)
  description = "Email addresses for SQL threat detection alerts"
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}
