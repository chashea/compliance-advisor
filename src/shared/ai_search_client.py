"""
Azure AI Search helpers for compliance knowledge retrieval.
"""
import os

from azure.core.credentials import AzureKeyCredential
from azure.identity import AzureCliCredential
from azure.search.documents import SearchClient

_search_client = None


def get_search_client() -> SearchClient:
    global _search_client
    if _search_client is not None:
        return _search_client

    endpoint = os.environ["AZURE_SEARCH_ENDPOINT"]
    index_name = os.environ["AZURE_SEARCH_INDEX_NAME"]
    api_key = os.environ.get("AZURE_SEARCH_API_KEY")

    credential = AzureKeyCredential(api_key) if api_key else AzureCliCredential()
    _search_client = SearchClient(
        endpoint=endpoint,
        index_name=index_name,
        credential=credential,
    )
    return _search_client


def search_knowledge_documents(
    query: str,
    top: int = 5,
    category: str | None = None,
) -> list[dict]:
    search_client = get_search_client()
    filter_expr = None
    if category:
        sanitized_category = category.replace("'", "''")
        filter_expr = f"category eq '{sanitized_category}'"

    results = search_client.search(
        search_text=query,
        top=max(1, min(int(top), 20)),
        filter=filter_expr,
    )
    return [
        {
            "id": doc.get("id"),
            "title": doc.get("title"),
            "content": doc.get("content"),
            "category": doc.get("category"),
            "source_url": doc.get("source_url"),
            "score": doc.get("@search.score"),
        }
        for doc in results
    ]
