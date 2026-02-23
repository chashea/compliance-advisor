"""
Create (or re-create) the compliance-posture and compliance-frameworks
indexes in Azure AI Search.

Usage:
    python scripts/setup_search_index.py \
        --endpoint https://srch-compliance-advisor-prod.search.windows.net \
        --key <admin-key>
"""
import argparse
import json
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex, SearchField, SearchFieldDataType,
    SimpleField, SearchableField, ComplexField,
    SemanticConfiguration, SemanticSearch, SemanticPrioritizedFields,
    SemanticField,
)


def create_posture_index(client: SearchIndexClient) -> None:
    fields = [
        SimpleField(name="id",               type=SearchFieldDataType.String, key=True),
        SimpleField(name="tenant_id",        type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchableField(name="tenant_name",  type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="region",           type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="snapshot_date",    type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="control_name",     type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="control_title",type=SearchFieldDataType.String),
        SimpleField(name="control_category", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="score",            type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SimpleField(name="max_score",        type=SearchFieldDataType.Double, filterable=True),
        SimpleField(name="points_gap",       type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SimpleField(name="action_type",      type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="tier",             type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="rank",             type=SearchFieldDataType.Int32,  filterable=True, sortable=True),
        SimpleField(name="remediation_url",  type=SearchFieldDataType.String),
        SimpleField(name="control_state",    type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchableField(name="assigned_to",  type=SearchFieldDataType.String, filterable=True),
    ]

    semantic = SemanticSearch(configurations=[
        SemanticConfiguration(
            name="default",
            prioritized_fields=SemanticPrioritizedFields(
                title_field=SemanticField(field_name="control_title"),
                content_fields=[SemanticField(field_name="control_name")],
                keywords_fields=[
                    SemanticField(field_name="control_category"),
                    SemanticField(field_name="action_type"),
                ],
            ),
        )
    ])

    index = SearchIndex(name="compliance-posture", fields=fields, semantic_search=semantic)
    client.create_or_update_index(index)
    print("Created index: compliance-posture")


def create_frameworks_index(client: SearchIndexClient) -> None:
    fields = [
        SimpleField(name="id",              type=SearchFieldDataType.String, key=True),
        SimpleField(name="framework",       type=SearchFieldDataType.String, filterable=True, facetable=True),
        SimpleField(name="control_id",      type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="control_title",  type=SearchFieldDataType.String),
        SearchableField(name="description",    type=SearchFieldDataType.String),
        SearchableField(name="guidance",       type=SearchFieldDataType.String),
        SimpleField(name="category",        type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(
            name="secure_score_categories",
            type=SearchFieldDataType.Collection(SearchFieldDataType.String),
            filterable=True,
            facetable=True,
        ),
    ]

    semantic = SemanticSearch(configurations=[
        SemanticConfiguration(
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
    ])

    index = SearchIndex(name="compliance-frameworks", fields=fields, semantic_search=semantic)
    client.create_or_update_index(index)
    print("Created index: compliance-frameworks")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--key",      required=True)
    args = parser.parse_args()

    idx_client = SearchIndexClient(
        endpoint=args.endpoint,
        credential=AzureKeyCredential(args.key),
    )
    create_posture_index(idx_client)
    create_frameworks_index(idx_client)
    print("Done.")
