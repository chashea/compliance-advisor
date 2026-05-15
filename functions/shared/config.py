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

_KV_REF_PATTERN = re.compile(r"^@Microsoft\.KeyVault\(SecretUri=(?P<uri>https://[^)]+)\)$")


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

    # PostgreSQL — two auth modes:
    #   • Entra ID (production):  PG_USE_AAD=true + PG_HOST + PG_DATABASE + PG_USER
    #   • Password (local dev):   DATABASE_URL connection string
    DATABASE_URL: str = Field(
        default="",
        description="psycopg2 DSN. Used only when PG_USE_AAD is false (local dev/CI).",
    )
    PG_USE_AAD: bool = Field(
        default=False,
        description="When true, ignore DATABASE_URL password and authenticate via DefaultAzureCredential.",
    )
    PG_HOST: str = Field(default="", description="PostgreSQL FQDN; required when PG_USE_AAD is true.")
    PG_DATABASE: str = Field(default="compliance_advisor", description="Database name.")
    PG_USER: str = Field(
        default="",
        description="Entra principal name registered in PG (typically the Function App's MI name).",
    )
    PG_SSLMODE: str = Field(default="require", description="psycopg2 sslmode parameter.")

    # Key Vault (Azure Commercial)
    KEY_VAULT_URL: str = Field(..., description="https://<vault>.vault.azure.net/")

    @model_validator(mode="after")
    def resolve_keyvault_references(self) -> "FunctionSettings":
        for field in ("DATABASE_URL", "COLLECTOR_CLIENT_ID", "COLLECTOR_CLIENT_SECRET"):
            val = getattr(self, field)
            if val and _KV_REF_PATTERN.match(val):
                try:
                    resolved = _resolve_keyvault_reference(val)
                    object.__setattr__(self, field, resolved)
                except Exception as exc:
                    log.error("Failed to resolve Key Vault reference for %s: %s", field, exc)
        return self

    @model_validator(mode="after")
    def validate_pg_config(self) -> "FunctionSettings":
        if self.PG_USE_AAD:
            missing = [f for f in ("PG_HOST", "PG_DATABASE", "PG_USER") if not getattr(self, f)]
            if missing:
                raise ValueError(f"PG_USE_AAD is true but the following settings are unset: {', '.join(missing)}")
        elif not self.DATABASE_URL:
            raise ValueError("Either PG_USE_AAD=true (with PG_HOST/PG_DATABASE/PG_USER) or DATABASE_URL must be set")
        return self

    # Tenant allow-list (comma-separated GUIDs)
    ALLOWED_TENANT_IDS: str = Field(default="")

    # Ingest endpoint authentication (per-tenant Entra-issued JWT)
    INGEST_REQUIRE_JWT: bool = Field(
        default=True,
        description="When true, /api/ingest validates an Entra bearer token instead of relying on the function key.",
    )
    INGEST_AUDIENCE: str = Field(
        default="",
        description="Required JWT audience for ingest (e.g. api://compliance-advisor-ingest or the app's client ID).",
    )
    INGEST_EXPECTED_APPID: str = Field(
        default="",
        description="When set, the JWT's appid/azp claim must match this value (typically the collector app ID).",
    )

    # Authentication enforcement (fail-closed in prod, opt-out for local dev)
    AUTH_REQUIRED: bool = Field(
        default=True,
        description="When true, dashboard routes reject requests without a valid EasyAuth principal header",
    )

    # Rate limiting (AI endpoints)
    RATE_LIMIT_BACKEND: str = Field(
        default="memory",
        description="'memory' (per-instance) or 'table' (Azure Storage Tables, distributed).",
    )
    RATE_LIMIT_MAX: int = Field(default=10, description="Max requests per window per client.")
    RATE_LIMIT_WINDOW_SECONDS: int = Field(default=60, description="Sliding window length in seconds.")
    RATE_LIMIT_STORAGE_ACCOUNT: str = Field(
        default="",
        description="Storage account name used by the table backend; defaults to AzureWebJobsStorage account.",
    )

    # Azure OpenAI (Assistants API)
    AZURE_OPENAI_ENDPOINT: str = Field(default="", description="https://<resource>.openai.azure.com/")
    AZURE_OPENAI_ASSISTANT_ID: str = Field(default="", description="Pre-created assistant ID (auto-creates if empty)")
    AZURE_OPENAI_MODEL: str = Field(default="gpt-4o", description="Azure OpenAI deployment name")

    # Collector (timer-triggered auto-collection)
    COLLECTOR_CLIENT_ID: str = Field(default="", description="App registration client ID for Graph API collection")
    COLLECTOR_CLIENT_SECRET: str = Field(default="", description="Client secret for Graph API collection")
    COLLECTOR_AUDIT_LOG_DAYS: int = Field(default=7, description="Days of audit log history to query")

    @property
    def allowed_tenants(self) -> set[str]:
        return {t.strip() for t in self.ALLOWED_TENANT_IDS.split(",") if t.strip()}


@lru_cache(maxsize=1)
def get_settings() -> FunctionSettings:
    return FunctionSettings()
