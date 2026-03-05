"""
Azure OpenAI client — singleton AzureOpenAI for chat completions.

Uses managed identity (DefaultAzureCredential) for authentication.
Reads AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_VERSION from environment.
"""

import os

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

_client: AzureOpenAI | None = None


def get_openai_client() -> AzureOpenAI:
    """Return a cached AzureOpenAI client using Entra ID (managed identity) auth."""
    global _client
    if _client is None:
        endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
        api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
        token_provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )
        _client = AzureOpenAI(
            azure_endpoint=endpoint,
            azure_ad_token_provider=token_provider,
            api_version=api_version,
        )
    return _client
