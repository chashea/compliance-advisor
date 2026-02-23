resource "azurerm_storage_account" "this" {
  name                     = substr(replace("st${var.name}", "-", ""), 0, 24)
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  tags                     = var.tags
}

resource "azurerm_service_plan" "this" {
  name                = "asp-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  os_type             = "Linux"
  sku_name            = "Y1"   # Consumption plan
  tags                = var.tags
}

resource "azurerm_linux_function_app" "this" {
  name                       = var.name
  resource_group_name        = var.resource_group_name
  location                   = var.location
  service_plan_id            = azurerm_service_plan.this.id
  storage_account_name       = azurerm_storage_account.this.name
  storage_account_access_key = azurerm_storage_account.this.primary_access_key
  https_only                 = true
  tags                       = var.tags

  identity {
    type = "SystemAssigned"
  }

  site_config {
    minimum_tls_version = "1.2"
    ftps_state          = "Disabled"   # Disable FTP entirely

    application_stack {
      python_version = "3.11"
    }

    cors {
      allowed_origins     = var.cors_allowed_origins
      support_credentials = false
    }
  }

  app_settings = {
    FUNCTIONS_EXTENSION_VERSION            = "~4"
    FUNCTIONS_WORKER_RUNTIME               = "python"
    MSSQL_CONNECTION                       = var.sql_connection
    KEY_VAULT_URL                          = var.key_vault_url
    AZURE_SEARCH_ENDPOINT                  = var.search_endpoint
    AZURE_SEARCH_INDEX_NAME                = "compliance-posture"
    AZURE_OPENAI_ENDPOINT                  = var.openai_endpoint
    AZURE_OPENAI_DEPLOYMENT_NAME           = var.openai_deployment
    AZURE_OPENAI_API_VERSION               = var.openai_api_version
    APPLICATIONINSIGHTS_CONNECTION_STRING   = var.appinsights_connection_string
    # Secrets (search key, OpenAI API key) are fetched from Key Vault at runtime
    # via managed identity — never stored as plain app settings
  }
}
