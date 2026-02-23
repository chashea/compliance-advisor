"""Tests for search_posture prompt flow node."""
from unittest.mock import patch, MagicMock
import pytest

VALID_UUID = "11111111-1111-1111-1111-111111111111"


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://fake.search.windows.net")
    monkeypatch.setenv("KEY_VAULT_URL", "https://fake-kv.vault.azure.net")


class TestInputValidation:
    def test_empty_question(self):
        from search_posture import search_posture
        with patch("search_posture._get_search_key", return_value="k"), \
             patch("search_posture.SearchClient"):
            result = search_posture("", VALID_UUID)
        assert "non-empty" in result["context"]
        assert result["sources"] == []

    def test_whitespace_question(self):
        from search_posture import search_posture
        with patch("search_posture._get_search_key", return_value="k"), \
             patch("search_posture.SearchClient"):
            result = search_posture("   ", VALID_UUID)
        assert "non-empty" in result["context"]

    def test_question_too_long(self):
        from search_posture import search_posture
        with patch("search_posture._get_search_key", return_value="k"), \
             patch("search_posture.SearchClient"):
            result = search_posture("x" * 1001, VALID_UUID)
        assert "exceeds maximum" in result["context"]

    def test_invalid_tenant_id(self):
        from search_posture import search_posture
        with patch("search_posture._get_search_key", return_value="k"), \
             patch("search_posture.SearchClient"):
            result = search_posture("question", "bad-uuid")
        assert "Invalid tenant_id" in result["context"]

    def test_cross_tenant_skips_validation(self):
        from search_posture import search_posture
        mock_client = MagicMock()
        mock_client.search.return_value = iter([])
        with patch("search_posture._get_search_key", return_value="k"), \
             patch("search_posture.SearchClient", return_value=mock_client):
            result = search_posture("question", "bad-uuid", cross_tenant=True)
        assert result["context"] == "No compliance posture data found."


class TestODataInjection:
    def test_escapes_single_quotes(self):
        from search_posture import _safe_odata_string
        assert _safe_odata_string("tenant's") == "tenant''s"

    def test_no_quotes_is_noop(self):
        from search_posture import _safe_odata_string
        assert _safe_odata_string("abc") == "abc"


class TestSearchResults:
    def test_no_results(self):
        from search_posture import search_posture
        mock_client = MagicMock()
        mock_client.search.return_value = iter([])
        with patch("search_posture._get_search_key", return_value="k"), \
             patch("search_posture.SearchClient", return_value=mock_client):
            result = search_posture("question", VALID_UUID)
        assert result["context"] == "No compliance posture data found."
        assert result["sources"] == []

    def test_results_formatted_correctly(self):
        from search_posture import search_posture
        mock_item = {
            "tenant_name": "Acme",
            "assessment_name": "NIST",
            "control_name": "MFA",
            "regulation": "NIST 800-53",
            "compliance_score": 85,
            "passed_controls": 10,
            "total_controls": 12,
            "control_family": "Identity",
            "implementation_status": "implemented",
            "test_status": "passed",
            "remediation_url": "https://example.com",
            "control_title": "MFA Control",
        }
        mock_client = MagicMock()
        mock_client.search.return_value = iter([mock_item])
        with patch("search_posture._get_search_key", return_value="k"), \
             patch("search_posture.SearchClient", return_value=mock_client):
            result = search_posture("question", VALID_UUID)
        assert "Acme" in result["context"]
        assert len(result["sources"]) == 1
        assert result["sources"][0]["url"] == "https://example.com"

    def test_no_remediation_url_excluded_from_sources(self):
        from search_posture import search_posture
        mock_item = {"tenant_name": "Acme", "control_name": "MFA"}
        mock_client = MagicMock()
        mock_client.search.return_value = iter([mock_item])
        with patch("search_posture._get_search_key", return_value="k"), \
             patch("search_posture.SearchClient", return_value=mock_client):
            result = search_posture("question", VALID_UUID)
        assert result["sources"] == []

    def test_cross_tenant_has_no_filter(self):
        from search_posture import search_posture
        mock_client = MagicMock()
        mock_client.search.return_value = iter([])
        with patch("search_posture._get_search_key", return_value="k"), \
             patch("search_posture.SearchClient", return_value=mock_client):
            search_posture("question", "", cross_tenant=True)
        kwargs = mock_client.search.call_args[1]
        assert kwargs.get("filter") is None
