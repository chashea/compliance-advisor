"""
Prompt Flow node: search the compliance-frameworks index for regulatory context.
Search key is retrieved from Key Vault via managed identity — never from env vars.
"""
import os
from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.search.documents import SearchClient

SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
INDEX_NAME      = "compliance-frameworks"


def _get_search_key() -> str:
    kv_url = os.environ["KEY_VAULT_URL"]
    client = SecretClient(vault_url=kv_url, credential=DefaultAzureCredential())
    return client.get_secret("azure-search-key").value


def search_frameworks(question: str) -> dict:
    client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(_get_search_key()),
    )

    results = client.search(
        search_text=question,
        select=["framework", "control_id", "control_title", "description", "guidance"],
        top=5,
    )

    items = list(results)
    if not items:
        return {"context": ""}

    lines = [
        f"- [{r.get('framework')} {r.get('control_id')}] {r.get('control_title')}: "
        f"{r.get('description','')}"
        for r in items
    ]
    return {"context": "\n".join(lines)}
