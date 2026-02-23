"""Tests for the reindex_search activity."""
from unittest.mock import patch, MagicMock
from datetime import date
import importlib
import pytest


def _make_upload_result(succeeded=True):
    r = MagicMock()
    r.succeeded = succeeded
    return r


@pytest.fixture
def activity(monkeypatch):
    """Import the activity module with required env vars set."""
    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("AZURE_SEARCH_INDEX_NAME", "compliance-posture")
    monkeypatch.setenv("KEY_VAULT_URL", "https://fake-kv.vault.azure.net")
    import activities.reindex_search as mod
    importlib.reload(mod)
    return mod


class TestReindexSearch:
    def test_returns_zero_when_no_documents(self, mock_connection, activity):
        mock_connection.cursor.return_value.fetchall.return_value = []
        mock_connection.cursor.return_value.description = []

        with patch.object(activity, "get_connection", return_value=mock_connection), \
             patch.object(activity, "set_admin_context"):
            result = activity.main(None)

        assert result == {"indexed": 0}

    def test_indexes_in_batches(self, mock_connection, mock_cursor, activity):
        mock_cursor.description = [("id",), ("tenant_id",), ("snapshot_date",)]
        mock_cursor.fetchall.return_value = [
            (f"doc-{i}", "tid", date(2026, 2, 22)) for i in range(2500)
        ]

        mock_search = MagicMock()
        mock_search.upload_documents.return_value = [_make_upload_result(True)] * 1000

        with patch.object(activity, "get_connection", return_value=mock_connection), \
             patch.object(activity, "set_admin_context"), \
             patch.object(activity, "_get_search_key", return_value="key"), \
             patch.object(activity, "SearchClient", return_value=mock_search):
            result = activity.main(None)

        assert mock_search.upload_documents.call_count == 3  # 1000+1000+500

    def test_counts_only_succeeded(self, mock_connection, mock_cursor, activity):
        mock_cursor.description = [("id",), ("tenant_id",), ("snapshot_date",)]
        mock_cursor.fetchall.return_value = [
            ("doc-1", "tid", date(2026, 2, 22)),
            ("doc-2", "tid", date(2026, 2, 22)),
            ("doc-3", "tid", date(2026, 2, 22)),
        ]

        mock_search = MagicMock()
        mock_search.upload_documents.return_value = [
            _make_upload_result(True),
            _make_upload_result(False),
            _make_upload_result(True),
        ]

        with patch.object(activity, "get_connection", return_value=mock_connection), \
             patch.object(activity, "set_admin_context"), \
             patch.object(activity, "_get_search_key", return_value="key"), \
             patch.object(activity, "SearchClient", return_value=mock_search):
            result = activity.main(None)

        assert result["indexed"] == 2

    def test_fetch_documents_converts_date_to_str(self, mock_connection, mock_cursor, activity):
        mock_cursor.description = [("id",), ("snapshot_date",)]
        mock_cursor.fetchall.return_value = [("doc-1", date(2026, 2, 22))]

        docs = activity._fetch_documents(mock_connection)

        assert docs[0]["snapshot_date"] == "2026-02-22"
        assert isinstance(docs[0]["snapshot_date"], str)
