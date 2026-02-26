"""
Microsoft Foundry Agent Service client — singleton AIProjectClient for creating and
running agents via the azure-ai-projects SDK.

Important: Foundry does not connect to M365 or GCC. The agent only reads from
Azure AI Search and from our HTTP API (SQL). All M365 GCC data is ingested via
Microsoft Graph (global endpoints) in the sync activities (collect_tenant_data,
collect_compliance_data). Keep GRAPH_NATIONAL_CLOUD unset for M365 GCC.
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
