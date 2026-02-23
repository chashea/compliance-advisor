terraform {
  required_version = ">= 1.7"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
    azapi = {
      source  = "azure/azapi"
      version = "~> 1.14"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }

  # Local state for development; switch to azurerm backend for production:
  # backend "azurerm" {
  #   resource_group_name  = "rg-tfstate"
  #   storage_account_name = "stcompliancetfstate"
  #   container_name       = "tfstate"
  #   key                  = "compliance-advisor.tfstate"
  # }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
  }
}

# azapi inherits authentication from the azurerm provider config above
provider "azapi" {}

data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "main" {
  name     = "rg-compliance-advisor-${var.env}"
  location = var.location
  tags     = local.tags
}

locals {
  prefix = "compliance-advisor-${var.env}"
  tags = {
    environment = var.env
    project     = "compliance-advisor"
    managed_by  = "terraform"
  }
}

# ── Modules ───────────────────────────────────────────────────────────────────

module "function" {
  source                       = "./modules/function"
  name                         = "func-${local.prefix}"
  resource_group_name          = azurerm_resource_group.main.name
  location                     = azurerm_resource_group.main.location
  sql_connection               = module.sql.connection_string
  key_vault_url                = module.keyvault.vault_uri
  search_endpoint              = module.search.endpoint
  openai_endpoint              = module.ai_foundry.openai_endpoint
  openai_deployment            = module.ai_foundry.openai_deployment_name
  appinsights_connection_string = module.ai_foundry.appinsights_connection_string
  cors_allowed_origins         = var.cors_allowed_origins
  tags                         = local.tags
}

module "keyvault" {
  source                = "./modules/keyvault"
  name                  = "kv-${local.prefix}"
  resource_group_name   = azurerm_resource_group.main.name
  location              = azurerm_resource_group.main.location
  tenant_id             = data.azurerm_client_config.current.tenant_id
  function_principal_id = module.function.principal_id
  search_admin_key      = module.search.primary_key
  tags                  = local.tags
}

module "sql" {
  source                = "./modules/sql"
  server_name           = "sql-${local.prefix}"
  database_name         = "ComplianceAdvisor"
  resource_group_name   = azurerm_resource_group.main.name
  location              = azurerm_resource_group.main.location
  admin_username        = var.sql_admin_username
  admin_password        = var.sql_admin_password
  function_subnet_id    = var.function_subnet_id
  security_alert_emails = var.security_alert_emails
  tags                  = local.tags
}

module "search" {
  source              = "./modules/search"
  name                = "srch-${local.prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  tags                = local.tags
}

module "ai_foundry" {
  source                = "./modules/ai_foundry"
  name                  = local.prefix
  resource_group_name   = azurerm_resource_group.main.name
  location              = azurerm_resource_group.main.location
  key_vault_id          = module.keyvault.id
  search_endpoint       = module.search.endpoint
  search_admin_key      = module.search.primary_key
  search_resource_id    = module.search.id
  function_principal_id = module.function.principal_id
  tags                  = local.tags
}
