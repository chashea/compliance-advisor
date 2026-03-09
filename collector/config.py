"""
Collector configuration using Pydantic Settings.

Uses client credentials flow to authenticate to the Microsoft Graph compliance APIs.

GCC (standard) uses:
  - login.microsoftonline.com
  - graph.microsoft.com
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CollectorSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Multi-tenant app registration (registered in home tenant)
    CLIENT_ID: str = Field(..., description="Application (client) ID of the multi-tenant app")
    CLIENT_SECRET: str = Field(..., description="Client secret for the app registration")

    # Key Vault (for retrieving credentials if not set directly)
    KEY_VAULT_URL: str = Field(default="", description="Key Vault URL, e.g. https://<vault>.vault.azure.net/")

    # Target tenant for this collection run
    TENANT_ID: str = Field(..., description="Customer tenant GUID to collect from")
    AGENCY_ID: str = Field(..., description="Logical agency identifier (e.g., dept-of-education)")
    DEPARTMENT: str = Field(..., description="Department name for dashboard filtering")
    DISPLAY_NAME: str = Field(default="", description="Human-readable tenant name")

    # Azure Function App ingestion endpoint
    FUNCTION_APP_URL: str = Field(..., description="e.g., https://cadvisor-func.azurewebsites.net/api/ingest")
    FUNCTION_APP_KEY: str = Field(default="", description="Function-level API key")

    # Audit log query lookback window
    AUDIT_LOG_DAYS: int = Field(default=1, description="Days of audit log history to query")

    # Monitoring
    APPINSIGHTS_CONNECTION_STRING: str = Field(default="", description="Application Insights connection string")

    @property
    def login_authority(self) -> str:
        return "https://login.microsoftonline.com"

    @property
    def graph_scope(self) -> list[str]:
        return ["https://graph.microsoft.com/.default"]
