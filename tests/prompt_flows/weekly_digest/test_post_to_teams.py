"""Tests for post_to_teams prompt flow node."""
import json
from unittest.mock import patch, MagicMock
import pytest


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("KEY_VAULT_URL", "https://fake-kv.vault.azure.net")


class TestPostToTeams:
    def test_success_returns_true(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("post_to_teams._get_webhook_url", return_value="https://webhook.example.com"), \
             patch("post_to_teams.requests.post", return_value=mock_resp):
            from post_to_teams import post_to_teams
            result = post_to_teams("Weekly summary")

        assert result == {"success": True, "status_code": 200}

    def test_non_200_returns_false(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 429

        with patch("post_to_teams._get_webhook_url", return_value="https://webhook.example.com"), \
             patch("post_to_teams.requests.post", return_value=mock_resp):
            from post_to_teams import post_to_teams
            result = post_to_teams("Summary")

        assert result == {"success": False, "status_code": 429}

    def test_adaptive_card_structure(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        with patch("post_to_teams._get_webhook_url", return_value="https://webhook.example.com"), \
             patch("post_to_teams.requests.post", return_value=mock_resp) as mock_post:
            from post_to_teams import post_to_teams
            post_to_teams("Test summary text")

        data_arg = mock_post.call_args[1]["data"]
        payload = json.loads(data_arg)
        assert payload["type"] == "message"
        attachment = payload["attachments"][0]
        assert attachment["contentType"] == "application/vnd.microsoft.card.adaptive"
        body = attachment["content"]["body"]
        assert body[0]["text"] == "Weekly Compliance Digest"
        assert body[1]["text"] == "Test summary text"

    def test_get_webhook_url_from_keyvault(self):
        mock_secret = MagicMock()
        mock_secret.value = "https://webhook.test"

        with patch("post_to_teams.SecretClient") as MockSC, \
             patch("post_to_teams.DefaultAzureCredential"):
            MockSC.return_value.get_secret.return_value = mock_secret
            from post_to_teams import _get_webhook_url
            url = _get_webhook_url()

        assert url == "https://webhook.test"
        MockSC.return_value.get_secret.assert_called_once_with("teams-webhook-url")
