"""
Compliance Advisor — Azure Function App configuration.

All endpoints are Azure Commercial:
- PostgreSQL:    *.postgres.database.azure.com
- Key Vault:     *.vault.azure.net
- Azure OpenAI:  *.openai.azure.com
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

    # Azure OpenAI (Azure Commercial)
    AZURE_OPENAI_ENDPOINT: str = Field(..., description="https://<resource>.openai.azure.com/")
    AZURE_OPENAI_DEPLOYMENT: str = Field(default="gpt-4o")
    AZURE_OPENAI_API_VERSION: str = Field(default="2024-08-01-preview")

    # Tenant allow-list (comma-separated GUIDs)
    ALLOWED_TENANT_IDS: str = Field(default="")

    @property
    def allowed_tenants(self) -> set[str]:
        return {t.strip() for t in self.ALLOWED_TENANT_IDS.split(",") if t.strip()}


@lru_cache(maxsize=1)
def get_settings() -> FunctionSettings:
    return FunctionSettings()
