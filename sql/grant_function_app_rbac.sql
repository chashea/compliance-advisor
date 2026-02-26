-- ============================================================
-- Compliance Advisor — Grant Function App (Managed Identity) DB access
-- ============================================================
-- Run this script AFTER deployment so the Function App can connect
-- with Authentication=ActiveDirectoryManagedIdentity.
--
-- Replace <FunctionAppName> with your Function App name (e.g. func-compliance-advisor-prod).
-- Get it from deployment output: functionAppName
--
-- Run as a SQL user with sufficient rights (e.g. Entra ID admin):
--   sqlcmd -S <server>.database.windows.net -d ComplianceAdvisor -i sql/grant_function_app_rbac.sql
-- Or set the variable below and run in SSMS / Azure Data Studio.
-- ============================================================

-- Set the Function App name (same as the managed identity display name in Azure AD)
DECLARE @FunctionAppName NVARCHAR(128) = N'func-compliance-advisor-prod';  -- CHANGE ME

-- Create user from Azure AD managed identity (external provider)
-- The name must match the Function App's system-assigned MI display name
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = @FunctionAppName AND type = 'E')
BEGIN
  DECLARE @Sql NVARCHAR(500) = N'CREATE USER [' + REPLACE(@FunctionAppName, N']', N']]') + N'] FROM EXTERNAL PROVIDER';
  EXEC sp_executesql @Sql;
  PRINT 'Created user: ' + @FunctionAppName;
END
ELSE
  PRINT 'User already exists: ' + @FunctionAppName;

-- Least privilege: allow read/write for app and Durable Functions (MSSQL provider)
-- db_datareader / db_datawriter: tables used by the app and durable task state
DECLARE @SafeName NVARCHAR(258) = QUOTENAME(REPLACE(@FunctionAppName, N']', N']]'));
EXEC sp_executesql N'ALTER ROLE db_datareader ADD MEMBER ' + @SafeName;
EXEC sp_executesql N'ALTER ROLE db_datawriter ADD MEMBER ' + @SafeName;

-- Required for Durable Tasks (MSSQL): create/alter tables in dbo or the durable task schema
EXEC sp_executesql N'ALTER ROLE db_ddladmin ADD MEMBER ' + @SafeName;

-- Optional: for stricter control, create a custom role with only the tables the app needs
-- and grant EXECUTE on specific stored procedures. Then revoke db_ddladmin if you
-- pre-create the Durable Task tables (e.g. dt.*) and grant only those objects.

PRINT 'RBAC granted: db_datareader, db_datawriter, db_ddladmin for Function App.';
