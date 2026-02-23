resource "azurerm_key_vault" "this" {
  name                       = var.name
  resource_group_name        = var.resource_group_name
  location                   = var.location
  tenant_id                  = var.tenant_id
  sku_name                   = "standard"
  enable_rbac_authorization  = true
  soft_delete_retention_days = 90
  purge_protection_enabled   = true
  tags                       = var.tags
}

# Grant the Function App's system-assigned identity read-only access to secrets
resource "azurerm_role_assignment" "function_secrets_user" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = var.function_principal_id
}

# Store the AI Search admin key as a secret — never in app settings
resource "azurerm_key_vault_secret" "search_key" {
  name         = "azure-search-key"
  value        = var.search_admin_key
  key_vault_id = azurerm_key_vault.this.id

  lifecycle {
    ignore_changes = [value]  # Rotated externally; Terraform won't overwrite after first set
  }
}
