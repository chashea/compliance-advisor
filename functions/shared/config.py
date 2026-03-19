"""
Compliance Advisor — Azure Function App configuration.

All endpoints are Azure Commercial:
- PostgreSQL:    *.postgres.database.azure.com
- Key Vault:     *.vault.azure.net
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class FunctionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL (Azure Database for PostgreSQL Flexible Server)
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string, e.g. postgresql://user:pass@host:5432/db")

    # Key Vault (Azure Commercial)
    KEY_VAULT_URL: str = Field(..., description="https://<vault>.vault.azure.net/")

    # Tenant allow-list (comma-separated GUIDs)
    ALLOWED_TENANT_IDS: str = Field(default="")

    # Azure OpenAI (Assistants API)
    AZURE_OPENAI_ENDPOINT: str = Field(default="", description="https://<resource>.openai.azure.com/")
    AZURE_OPENAI_ASSISTANT_ID: str = Field(default="", description="Pre-created assistant ID (auto-creates if empty)")
    AZURE_OPENAI_MODEL: str = Field(default="gpt-4o", description="Azure OpenAI deployment name")

    # Collector (timer-triggered auto-collection)
    COLLECTOR_CLIENT_ID: str = Field(default="", description="App registration client ID for Graph API collection")
    COLLECTOR_CLIENT_SECRET: str = Field(default="", description="Client secret for Graph API collection")
    COLLECTOR_AUDIT_LOG_DAYS: int = Field(default=1, description="Days of audit log history to query")

    @property
    def allowed_tenants(self) -> set[str]:
        return {t.strip() for t in self.ALLOWED_TENANT_IDS.split(",") if t.strip()}


@lru_cache(maxsize=1)
def get_settings() -> FunctionSettings:
    return FunctionSettings()
