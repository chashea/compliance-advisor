"""Tests for search_frameworks prompt flow node."""
from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("KEY_VAULT_URL", "https://fake-kv.vault.azure.net")


class TestSearchFrameworks:
    def test_no_results_returns_empty_context(self):
        from search_frameworks import search_frameworks
        mock_client = MagicMock()
        mock_client.search.return_value = iter([])
        with patch("search_frameworks._get_search_key", return_value="k"), \
             patch("search_frameworks.SearchClient", return_value=mock_client):
            result = search_frameworks("question")
        assert result == {"context": ""}

    def test_results_formatted_as_bullets(self):
        from search_frameworks import search_frameworks
        item = {
            "framework": "NIST",
            "control_id": "AC-1",
            "control_title": "Policy",
            "description": "Access control policy",
        }
        mock_client = MagicMock()
        mock_client.search.return_value = iter([item])
        with patch("search_frameworks._get_search_key", return_value="k"), \
             patch("search_frameworks.SearchClient", return_value=mock_client):
            result = search_frameworks("question")
        assert result["context"].startswith("- [NIST AC-1]")
        assert "Policy" in result["context"]

    def test_search_called_with_correct_params(self):
        from search_frameworks import search_frameworks
        mock_client = MagicMock()
        mock_client.search.return_value = iter([])
        with patch("search_frameworks._get_search_key", return_value="k"), \
             patch("search_frameworks.SearchClient", return_value=mock_client):
            search_frameworks("question")
        kwargs = mock_client.search.call_args[1]
        assert kwargs["top"] == 5
        assert "framework" in kwargs["select"]
