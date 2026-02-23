# ── Observability ─────────────────────────────────────────────────────────────

resource "azurerm_log_analytics_workspace" "this" {
  name                = "log-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_application_insights" "this" {
  name                = "appi-${var.name}"
  resource_group_name = var.resource_group_name
  location            = var.location
  workspace_id        = azurerm_log_analytics_workspace.this.id
  application_type    = "web"
  tags                = var.tags
}

# ── Storage — dedicated to the AI Hub ─────────────────────────────────────────
# AI Hub requires its own storage account; do not reuse the Function App storage.

resource "azurerm_storage_account" "this" {
  name                     = substr(replace("staih${var.name}", "-", ""), 0, 24)
  resource_group_name      = var.resource_group_name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  tags                     = var.tags
}

# ── Container Registry — required for Prompt Flow online deployments ───────────

resource "azurerm_container_registry" "this" {
  name                = substr(replace("acr${var.name}", "-", ""), 0, 50)
  resource_group_name = var.resource_group_name
  location            = var.location
  sku                 = "Basic"
  admin_enabled       = false   # authenticate via managed identity, not admin creds
  tags                = var.tags
}

# ── Azure OpenAI ───────────────────────────────────────────────────────────────

resource "azurerm_cognitive_account" "openai" {
  name                  = "oai-${var.name}"
  resource_group_name   = var.resource_group_name
  location              = var.location
  kind                  = "OpenAI"
  sku_name              = "S0"
  custom_subdomain_name = substr(replace("oai${var.name}", "-", ""), 0, 24)
  tags                  = var.tags
}

# GPT-4o deployment.
# Verify regional availability before applying:
# https://learn.microsoft.com/azure/ai-services/openai/concepts/models#standard-deployment-model-availability
resource "azurerm_cognitive_deployment" "gpt4o" {
  name                 = "gpt-4o"
  cognitive_account_id = azurerm_cognitive_account.openai.id

  model {
    format  = "OpenAI"
    name    = "gpt-4o"
    version = "2024-11-20"
  }

  sku {
    name     = "Standard"
    capacity = 10   # 10 K tokens-per-minute; raise to 40+ for production
  }
}

# Store the OpenAI API key in Key Vault.
# The Function App's managed identity already has Key Vault Secrets User on this vault.
resource "azurerm_key_vault_secret" "openai_api_key" {
  name         = "azure-openai-api-key"
  value        = azurerm_cognitive_account.openai.primary_access_key
  key_vault_id = var.key_vault_id

  lifecycle {
    ignore_changes = [value]   # allow external rotation without Terraform overwriting
  }
}

# ── AI Hub (Azure AI Foundry workspace) ───────────────────────────────────────

resource "azurerm_machine_learning_workspace" "hub" {
  name                    = "aih-${var.name}"
  resource_group_name     = var.resource_group_name
  location                = var.location
  kind                    = "Hub"
  application_insights_id = azurerm_application_insights.this.id
  key_vault_id            = var.key_vault_id
  storage_account_id      = azurerm_storage_account.this.id
  container_registry_id   = azurerm_container_registry.this.id

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# ── AI Project — scoped to compliance-advisor Prompt Flows ────────────────────

resource "azurerm_machine_learning_workspace" "project" {
  name                    = "aip-${var.name}"
  resource_group_name     = var.resource_group_name
  location                = var.location
  kind                    = "Project"
  hub_id                  = azurerm_machine_learning_workspace.hub.id
  application_insights_id = azurerm_application_insights.this.id
  key_vault_id            = var.key_vault_id
  storage_account_id      = azurerm_storage_account.this.id

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

# ── Role Assignments ──────────────────────────────────────────────────────────

# Function App → OpenAI  (direct SDK calls from Python nodes during dev/test)
resource "azurerm_role_assignment" "function_openai_user" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = var.function_principal_id
}

# AI Project identity → OpenAI  (Prompt Flow execution via the Hub connection)
resource "azurerm_role_assignment" "project_openai_contributor" {
  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI Contributor"
  principal_id         = azurerm_machine_learning_workspace.project.identity[0].principal_id
}

# AI Project identity → AI Search  (RAG retrieval inside Prompt Flows)
resource "azurerm_role_assignment" "project_search_reader" {
  scope                = var.search_resource_id
  role_definition_name = "Search Index Data Reader"
  principal_id         = azurerm_machine_learning_workspace.project.identity[0].principal_id
}

# AI Hub identity → Container Registry  (pull images for online endpoint deploys)
resource "azurerm_role_assignment" "hub_acr_pull" {
  scope                = azurerm_container_registry.this.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_machine_learning_workspace.hub.identity[0].principal_id
}

# ── Hub Connections (azapi — not yet in azurerm 3.x) ─────────────────────────
# Connections are defined on the Hub and are visible to all Projects under it.

resource "azapi_resource" "search_connection" {
  type      = "Microsoft.MachineLearningServices/workspaces/connections@2024-04-01"
  name      = "azure-ai-search"
  parent_id = azurerm_machine_learning_workspace.hub.id

  schema_validation_enabled = false

  body = jsonencode({
    properties = {
      authType = "ApiKey"
      credentials = {
        key = var.search_admin_key
      }
      category = "CognitiveSearch"
      target   = var.search_endpoint
    }
  })
}

resource "azapi_resource" "openai_connection" {
  type      = "Microsoft.MachineLearningServices/workspaces/connections@2024-04-01"
  name      = "azure-openai"
  parent_id = azurerm_machine_learning_workspace.hub.id

  schema_validation_enabled = false

  body = jsonencode({
    properties = {
      authType = "ApiKey"
      credentials = {
        key = azurerm_cognitive_account.openai.primary_access_key
      }
      category = "AzureOpenAI"
      target   = azurerm_cognitive_account.openai.endpoint
      metadata = {
        ApiType              = "Azure"
        ApiVersion           = "2024-05-01-preview"
        DeploymentApiVersion = "2023-10-01-preview"
      }
    }
  })
}
