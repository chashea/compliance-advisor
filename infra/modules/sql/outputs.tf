output "server_fqdn" {
  value = azurerm_mssql_server.this.fully_qualified_domain_name
}

output "connection_string" {
  value = "Server=tcp:${azurerm_mssql_server.this.fully_qualified_domain_name},1433;Database=${var.database_name};Authentication=Active Directory Managed Identity;"
}
