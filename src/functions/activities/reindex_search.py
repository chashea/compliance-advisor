"""
Activity: rebuild the Azure AI Search index from the latest SQL data.
Runs after all tenant syncs are complete.
Search key is retrieved from Key Vault via managed identity — never from env vars.
"""
import logging
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from azure.core.credentials import AzureKeyCredential
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from azure.search.documents import SearchClient
from shared.sql_client import get_connection, set_admin_context

SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
INDEX_NAME      = os.environ.get("AZURE_SEARCH_INDEX_NAME", "compliance-posture")


def _get_search_key() -> str:
    """Retrieve the AI Search admin key from Key Vault via managed identity."""
    kv_url = os.environ["KEY_VAULT_URL"]
    client = SecretClient(vault_url=kv_url, credential=DefaultAzureCredential())
    return client.get_secret("azure-search-key").value


def _fetch_documents(conn) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            CAST(cs.id AS NVARCHAR) + '-' + cs.tenant_id AS id,
            cs.tenant_id,
            t.display_name  AS tenant_name,
            t.region,
            cs.snapshot_date,
            cs.control_name,
            cp.title        AS control_title,
            cs.control_category,
            cs.score,
            cs.max_score,
            cs.max_score - cs.score AS points_gap,
            cp.action_type,
            cp.tier,
            cp.rank,
            cp.remediation_url,
            cp.control_state,
            cp.assigned_to
        FROM control_scores cs
        JOIN tenants t ON t.tenant_id = cs.tenant_id
        LEFT JOIN control_profiles cp
            ON cp.tenant_id    = cs.tenant_id
            AND cp.control_name = cs.control_name
        WHERE cs.snapshot_date = (
            SELECT MAX(snapshot_date)
            FROM control_scores
            WHERE tenant_id = cs.tenant_id
        )
    """)
    cols = [col[0] for col in cursor.description]
    rows = []
    for row in cursor.fetchall():
        doc = dict(zip(cols, row))
        doc["snapshot_date"] = str(doc["snapshot_date"])
        rows.append(doc)
    return rows


def main(payload) -> dict:
    conn = get_connection()
    try:
        # Admin context required — query spans all tenants for reindex
        set_admin_context(conn)
        docs = _fetch_documents(conn)
    finally:
        conn.close()

    if not docs:
        logging.warning("No documents to index")
        return {"indexed": 0}

    client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(_get_search_key()),
    )

    batch_size = 1000
    total = 0
    for i in range(0, len(docs), batch_size):
        result = client.upload_documents(docs[i : i + batch_size])
        total += sum(1 for r in result if r.succeeded)

    logging.info("Indexed %d documents into '%s'", total, INDEX_NAME)
    return {"indexed": total}
