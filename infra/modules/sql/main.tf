resource "azurerm_mssql_server" "this" {
  name                         = var.server_name
  resource_group_name          = var.resource_group_name
  location                     = var.location
  version                      = "12.0"
  administrator_login          = var.admin_username
  administrator_login_password = var.admin_password
  minimum_tls_version          = "1.2"
  tags                         = var.tags
}

resource "azurerm_mssql_database" "this" {
  name         = var.database_name
  server_id    = azurerm_mssql_server.this.id
  collation    = "SQL_Latin1_General_CP1_CI_AS"
  license_type = "LicenseIncluded"
  tags         = var.tags

  # Serverless tier — auto-pauses after 60 min of inactivity
  sku_name                    = "GP_S_Gen5_1"
  min_capacity                = 0.5
  auto_pause_delay_in_minutes = 60
}

# ── Network: deny public internet; only allow from the Function App subnet ────
# Replace with a private endpoint + VNet rule for production workloads.
# The 0.0.0.0/0.0.0.0 "Allow Azure Services" rule is intentionally NOT used
# because it permits all Azure tenants globally, not just this subscription.
resource "azurerm_mssql_virtual_network_rule" "function_subnet" {
  name      = "allow-function-subnet"
  server_id = azurerm_mssql_server.this.id
  subnet_id = var.function_subnet_id
}

# ── Threat detection ──────────────────────────────────────────────────────────
resource "azurerm_mssql_server_security_alert_policy" "this" {
  resource_group_name = var.resource_group_name
  server_name         = azurerm_mssql_server.this.name
  state               = "Enabled"
  email_addresses     = var.security_alert_emails
  retention_days      = 30
}

# ── Short-term backup retention (35 days) ────────────────────────────────────
resource "azurerm_mssql_database_backup_short_term_retention_policy" "this" {
  database_id    = azurerm_mssql_database.this.id
  retention_days = 35
}

# ── Long-term backup retention ────────────────────────────────────────────────
resource "azurerm_mssql_database_long_term_retention_policy" "this" {
  database_id       = azurerm_mssql_database.this.id
  weekly_retention  = "P4W"
  monthly_retention = "P3M"
  yearly_retention  = "P1Y"
  week_of_year      = 1
}

# ── Server-level audit log → Storage Account ─────────────────────────────────
resource "azurerm_storage_account" "audit" {
  name                     = substr(replace("staudit${var.server_name}", "-", ""), 0, 24)
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  tags                     = var.tags
}

resource "azurerm_mssql_server_extended_auditing_policy" "this" {
  server_id              = azurerm_mssql_server.this.id
  storage_endpoint       = azurerm_storage_account.audit.primary_blob_endpoint
  storage_account_access_key = azurerm_storage_account.audit.primary_access_key
  retention_in_days      = 90
  log_monitoring_enabled = true
}
