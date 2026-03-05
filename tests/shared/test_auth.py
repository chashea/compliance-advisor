"""Tests for shared.auth — env-based Graph token acquisition."""
from unittest.mock import patch, MagicMock
import pytest
import requests as req


def test_get_graph_token_calls_correct_url(monkeypatch, sample_tenant):
    monkeypatch.setenv("AZURE_TENANT_ID", sample_tenant["tenant_id"])
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")

    with patch("shared.auth.requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"access_token": "tok-123"}
        mock_post.return_value = mock_resp

        from shared.auth import get_graph_token
        token = get_graph_token(sample_tenant)

    assert token == "tok-123"
    call_url = mock_post.call_args[0][0]
    assert sample_tenant["tenant_id"] in call_url
    assert "oauth2/v2.0/token" in call_url


def test_get_graph_token_raises_on_http_error(monkeypatch, sample_tenant):
    monkeypatch.setenv("AZURE_TENANT_ID", sample_tenant["tenant_id"])
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")

    with patch("shared.auth.requests.post") as mock_post:
        mock_post.return_value.raise_for_status.side_effect = req.HTTPError("401")

        from shared.auth import get_graph_token
        with pytest.raises(req.HTTPError):
            get_graph_token(sample_tenant)


def test_get_graph_token_missing_env_raises(sample_tenant):
    """Missing AZURE_TENANT_ID should raise KeyError."""
    from shared.auth import get_graph_token
    with pytest.raises(KeyError):
        get_graph_token(sample_tenant)
