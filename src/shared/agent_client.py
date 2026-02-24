"""
Foundry Agent Service client — singleton AIProjectClient for creating and
running agents via the azure-ai-projects SDK.
"""
import os

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

_client: AIProjectClient | None = None


def get_project_client() -> AIProjectClient:
    """Return a cached AIProjectClient using the PROJECT_ENDPOINT env var."""
    global _client
    if _client is None:
        endpoint = os.environ["PROJECT_ENDPOINT"]
        _client = AIProjectClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
        )
    return _client
