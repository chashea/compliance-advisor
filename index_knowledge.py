#!/usr/bin/env python3
"""Index compliance framework documents into Azure AI Search.

Creates the 'compliance-knowledge' index (if it doesn't exist) and uploads
all JSON files from data/frameworks/ as searchable documents.

Usage:
    python index_knowledge.py              # create index + upload documents
    python index_knowledge.py --delete     # delete and recreate the index

Requires AZURE_SEARCH_ENDPOINT and either AZURE_SEARCH_API_KEY or az login.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from pathlib import Path

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import AzureCliCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchableField,
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
)
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

FRAMEWORKS_DIR = Path(__file__).parent / "data" / "frameworks"
INDEX_NAME = os.environ.get("AZURE_SEARCH_INDEX_NAME", "compliance-knowledge")


def _credential():
    api_key = os.environ.get("AZURE_SEARCH_API_KEY")
    return AzureKeyCredential(api_key) if api_key else AzureCliCredential()


def _index_definition() -> SearchIndex:
    return SearchIndex(
        name=INDEX_NAME,
        fields=[
            SimpleField(name="id", type=SearchFieldDataType.String, key=True),
            SearchableField(name="title", type=SearchFieldDataType.String),
            SearchableField(name="content", type=SearchFieldDataType.String),
            SimpleField(
                name="category",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SimpleField(name="source_url", type=SearchFieldDataType.String),
            SimpleField(
                name="framework",
                type=SearchFieldDataType.String,
                filterable=True,
                facetable=True,
            ),
            SimpleField(name="control_id", type=SearchFieldDataType.String),
        ],
    )


def _stable_id(framework: str, control_id: str) -> str:
    """Deterministic document ID from framework + control_id."""
    raw = f"{framework}::{control_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load_documents() -> list[dict]:
    """Load all framework JSON files and map to search documents."""
    docs = []
    for path in sorted(FRAMEWORKS_DIR.glob("*.json")):
        controls = json.loads(path.read_text())
        log.info("Loaded %d controls from %s", len(controls), path.name)
        for ctrl in controls:
            content = ctrl.get("description", "")
            guidance = ctrl.get("guidance", "")
            if guidance:
                content = f"{content}\n\nGuidance: {guidance}"

            docs.append(
                {
                    "id": _stable_id(ctrl["framework"], ctrl["control_id"]),
                    "title": f'{ctrl["control_id"]} — {ctrl["control_title"]}',
                    "content": content,
                    "category": ctrl.get("category", ""),
                    "source_url": "",
                    "framework": ctrl["framework"],
                    "control_id": ctrl["control_id"],
                }
            )
    return docs


def ensure_index(index_client: SearchIndexClient, *, recreate: bool = False) -> None:
    """Create the index if it doesn't exist, or recreate if requested."""
    if recreate:
        try:
            index_client.delete_index(INDEX_NAME)
            log.info("Deleted existing index '%s'", INDEX_NAME)
        except ResourceNotFoundError:
            pass

    try:
        index_client.get_index(INDEX_NAME)
        log.info("Index '%s' already exists", INDEX_NAME)
    except ResourceNotFoundError:
        index_client.create_index(_index_definition())
        log.info("Created index '%s'", INDEX_NAME)


def upload_documents(search_client: SearchClient, docs: list[dict]) -> None:
    """Upload documents in batches of 100."""
    batch_size = 100
    for i in range(0, len(docs), batch_size):
        batch = docs[i : i + batch_size]
        result = search_client.upload_documents(batch)
        succeeded = sum(1 for r in result if r.succeeded)
        log.info("Uploaded batch %d–%d: %d/%d succeeded", i + 1, i + len(batch), succeeded, len(batch))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delete", action="store_true", help="Delete and recreate the index before uploading")
    args = parser.parse_args()

    endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
    if not endpoint:
        log.error("AZURE_SEARCH_ENDPOINT is required. Set it in .env or environment.")
        sys.exit(1)

    credential = _credential()
    index_client = SearchIndexClient(endpoint=endpoint, credential=credential)
    search_client = SearchClient(endpoint=endpoint, index_name=INDEX_NAME, credential=credential)

    docs = _load_documents()
    if not docs:
        log.error("No framework documents found in %s", FRAMEWORKS_DIR)
        sys.exit(1)

    log.info("Total documents to index: %d", len(docs))

    ensure_index(index_client, recreate=args.delete)
    upload_documents(search_client, docs)

    log.info("Done. Index '%s' now has %d documents.", INDEX_NAME, search_client.get_document_count())


if __name__ == "__main__":
    main()
