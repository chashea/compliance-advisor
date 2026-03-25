"""
Hunter configuration using Pydantic Settings.

Uses DefaultAzureCredential for both Graph API (runHuntingQuery)
and Azure OpenAI (chat completions).
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HunterSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str = Field(..., description="e.g., https://<resource>.openai.azure.com/")
    AZURE_OPENAI_DEPLOYMENT: str = Field(default="gpt-4o", description="Model deployment name")
    AZURE_OPENAI_API_VERSION: str = Field(default="2024-06-01", description="Azure OpenAI API version")

    # Graph API
    GRAPH_BASE_URL: str = Field(
        default="https://graph.microsoft.com/v1.0",
        description="Graph base URL (override for GCC: https://graph.microsoft.us/v1.0)",
    )

    # Client credentials (reuse collector's app registration for Graph API)
    CLIENT_ID: str = Field(default="", description="App registration client ID")
    CLIENT_SECRET: str = Field(default="", description="App registration client secret")
    TENANT_ID: str = Field(default="", description="Target tenant GUID")

    # Behavior
    MAX_RETRIES: int = Field(default=2, description="KQL retry attempts on invalid query")
    MAX_RESULTS: int = Field(default=50, description="Default result limit appended to KQL")
    LOOKBACK_DAYS: int = Field(default=30, description="Default time window (max 30)")

    @property
    def graph_scope(self) -> str:
        if "microsoft.us" in self.GRAPH_BASE_URL:
            return "https://graph.microsoft.us/.default"
        return "https://graph.microsoft.com/.default"

    @property
    def use_client_credentials(self) -> bool:
        return bool(self.CLIENT_ID and self.CLIENT_SECRET and self.TENANT_ID)
