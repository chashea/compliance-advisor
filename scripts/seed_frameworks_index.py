"""
One-time script: create (or reset) the compliance-frameworks Azure AI Search
index and upload seed data from data/frameworks/*.json.

Usage:
    export AZURE_SEARCH_ENDPOINT=https://<service>.search.windows.net
    export AZURE_SEARCH_KEY=<admin-key>          # or omit if KEY_VAULT_URL is set
    export KEY_VAULT_URL=https://<vault>.vault.azure.net  # optional; preferred in CI

    python scripts/seed_frameworks_index.py [--reset]

Flags:
    --reset   Delete the existing index before recreating it.
              Use this when the schema changes.
              Without --reset the script does an upsert (safe to re-run).
"""
import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    CorsOptions,
    SearchableField,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    SimpleField,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

INDEX_NAME = "compliance-frameworks"

# Root of the repo, two levels up from this script
REPO_ROOT    = Path(__file__).resolve().parent.parent
FRAMEWORKS_DIR = REPO_ROOT / "data" / "frameworks"

# ── helpers ──────────────────────────────────────────────────────────────────

def _get_search_key() -> str:
    """
    Resolve the AI Search admin key.
    Priority:
      1. AZURE_SEARCH_KEY env var (local dev / CI with secret)
      2. Key Vault secret 'azure-search-key' (production managed identity)
    """
    key = os.environ.get("AZURE_SEARCH_KEY")
    if key:
        return key

    kv_url = os.environ.get("KEY_VAULT_URL")
    if not kv_url:
        sys.exit(
            "Error: set AZURE_SEARCH_KEY or KEY_VAULT_URL before running this script."
        )

    from azure.identity import DefaultAzureCredential
    from azure.keyvault.secrets import SecretClient

    log.info("Fetching search key from Key Vault: %s", kv_url)
    client = SecretClient(vault_url=kv_url, credential=DefaultAzureCredential())
    return client.get_secret("azure-search-key").value


def _make_doc_id(framework: str, control_id: str) -> str:
    """
    Build a stable, URL-safe document key from framework + control_id.
    Azure AI Search keys must match [A-Za-z0-9_-].
    """
    raw = f"{framework}_{control_id}"
    return re.sub(r"[^A-Za-z0-9_\-]", "_", raw)


# ── index schema ─────────────────────────────────────────────────────────────

def _build_index() -> SearchIndex:
    fields = [
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),
        SimpleField(
            name="framework",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        SimpleField(
            name="control_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),
        SearchableField(
            name="control_title",
            type=SearchFieldDataType.String,
            analyzer_name="en.microsoft",
        ),
        SearchableField(
            name="description",
            type=SearchFieldDataType.String,
            analyzer_name="en.microsoft",
        ),
        SearchableField(
            name="guidance",
            type=SearchFieldDataType.String,
            analyzer_name="en.microsoft",
        ),
        SimpleField(
            name="category",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),
        SearchField(
            name="secure_score_categories",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
            facetable=True,
        ),
    ]

    # Semantic configuration so Prompt Flow can use semantic ranking
    semantic_cfg = SemanticConfiguration(
        name="default",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="control_title"),
            content_fields=[
                SemanticField(field_name="description"),
                SemanticField(field_name="guidance"),
            ],
            keywords_fields=[
                SemanticField(field_name="framework"),
                SemanticField(field_name="category"),
            ],
        ),
    )

    return SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        semantic_search=SemanticSearch(configurations=[semantic_cfg]),
        cors_options=CorsOptions(allowed_origins=[], max_age_in_seconds=300),
    )


# ── seed data loading ─────────────────────────────────────────────────────────

def _load_documents() -> list[dict]:
    """Load all JSON files from data/frameworks/ and normalise to index docs."""
    if not FRAMEWORKS_DIR.is_dir():
        sys.exit(f"Error: frameworks directory not found: {FRAMEWORKS_DIR}")

    json_files = sorted(FRAMEWORKS_DIR.glob("*.json"))
    if not json_files:
        sys.exit(f"Error: no JSON files found in {FRAMEWORKS_DIR}")

    docs: list[dict] = []
    for path in json_files:
        log.info("Loading %s", path.name)
        with path.open(encoding="utf-8") as f:
            controls = json.load(f)

        if not isinstance(controls, list):
            log.warning("Skipping %s — expected a JSON array", path.name)
            continue

        for ctrl in controls:
            doc = {
                "id":                    _make_doc_id(ctrl["framework"], ctrl["control_id"]),
                "framework":             ctrl["framework"],
                "control_id":            ctrl["control_id"],
                "control_title":         ctrl.get("control_title", ""),
                "description":           ctrl.get("description", ""),
                "guidance":              ctrl.get("guidance", ""),
                "category":              ctrl.get("category", ""),
                "secure_score_categories": ctrl.get("secure_score_categories", []),
            }
            docs.append(doc)

    log.info("Loaded %d controls across %d framework files", len(docs), len(json_files))
    return docs


# ── main ──────────────────────────────────────────────────────────────────────

def main(reset: bool) -> None:
    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        sys.exit("Error: AZURE_SEARCH_ENDPOINT environment variable is not set.")

    key        = _get_search_key()
    credential = AzureKeyCredential(key)

    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)

    # Optionally delete existing index
    if reset:
        try:
            index_client.delete_index(INDEX_NAME)
            log.info("Deleted existing index '%s'", INDEX_NAME)
        except ResourceNotFoundError:
            log.info("Index '%s' did not exist — nothing to delete", INDEX_NAME)

    # Create or update index schema
    index = _build_index()
    index_client.create_or_update_index(index)
    log.info("Index '%s' created / updated", INDEX_NAME)

    # Load documents
    docs = _load_documents()
    if not docs:
        log.warning("No documents loaded; exiting.")
        return

    # Upload in batches of 1 000 (Search service limit per request)
    search_client = SearchClient(
        endpoint=endpoint,
        index_name=INDEX_NAME,
        credential=credential,
    )

    batch_size = 1000
    total_ok   = 0
    total_fail = 0

    for start in range(0, len(docs), batch_size):
        batch   = docs[start : start + batch_size]
        results = search_client.upload_documents(batch)
        ok   = sum(1 for r in results if r.succeeded)
        fail = sum(1 for r in results if not r.succeeded)
        for r in results:
            if not r.succeeded:
                log.error("Failed to upload doc '%s': %s", r.key, r.error_message)
        total_ok   += ok
        total_fail += fail
        log.info(
            "Batch %d–%d: %d succeeded, %d failed",
            start + 1,
            start + len(batch),
            ok,
            fail,
        )

    log.info(
        "Done. %d documents uploaded successfully, %d failed.",
        total_ok,
        total_fail,
    )
    if total_fail:
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed the compliance-frameworks Azure AI Search index."
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the index before recreating it (use when schema changes).",
    )
    args = parser.parse_args()
    main(reset=args.reset)
