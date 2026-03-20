"""
Compliance Advisor — Azure Function App configuration.

All endpoints are Azure Commercial:
- PostgreSQL:    *.postgres.database.azure.com
- Key Vault:     *.vault.azure.net
"""

import logging
import re
from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger(__name__)

_KV_REF_PATTERN = re.compile(
    r"^@Microsoft\.KeyVault\(SecretUri=(?P<uri>https://[^)]+)\)$"
)


def _resolve_keyvault_reference(ref: str) -> str:
    """Resolve an unresolved @Microsoft.KeyVault(...) app-setting to its secret value."""
    m = _KV_REF_PATTERN.match(ref)
    if not m:
        return ref
    secret_uri = m.group("uri")
    log.warning("Resolving unresolved Key Vault reference programmatically: %s", secret_uri)
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    # Extract vault URL and secret name from SecretUri
    # Format: https://<vault>.vault.azure.net/secrets/<name>/[version]
    parts = secret_uri.rstrip("/").split("/")
    # parts: ['https:', '', '<vault>.vault.azure.net', 'secrets', '<name>', ...]
    vault_url = "/".join(parts[:3])
    secret_name = parts[4]
    client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
    return client.get_secret(secret_name).value


class FunctionSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # PostgreSQL (Azure Database for PostgreSQL Flexible Server)
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string, e.g. postgresql://user:pass@host:5432/db")

    # Key Vault (Azure Commercial)
    KEY_VAULT_URL: str = Field(..., description="https://<vault>.vault.azure.net/")

    @model_validator(mode="after")
    def resolve_keyvault_references(self) -> "FunctionSettings":
        if _KV_REF_PATTERN.match(self.DATABASE_URL):
            self.DATABASE_URL = _resolve_keyvault_reference(self.DATABASE_URL)
        if _KV_REF_PATTERN.match(self.COLLECTOR_CLIENT_ID):
            self.COLLECTOR_CLIENT_ID = _resolve_keyvault_reference(self.COLLECTOR_CLIENT_ID)
        if _KV_REF_PATTERN.match(self.COLLECTOR_CLIENT_SECRET):
            self.COLLECTOR_CLIENT_SECRET = _resolve_keyvault_reference(self.COLLECTOR_CLIENT_SECRET)
        return self

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
