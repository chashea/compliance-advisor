"""Tests for shared.auth — Key Vault singleton, Graph token, Graph client."""
from unittest.mock import patch, MagicMock
import pytest


def test_get_kv_client_creates_singleton(mock_env):
    from shared.auth import _get_kv_client

    with patch("shared.auth.SecretClient") as MockSC, \
         patch("shared.auth.DefaultAzureCredential"):
        client1 = _get_kv_client()
        client2 = _get_kv_client()

    assert client1 is client2
    MockSC.assert_called_once()


def test_get_kv_client_missing_env_raises():
    import shared.auth as auth_module
    auth_module._kv_client = None

    with pytest.raises(KeyError):
        auth_module._get_kv_client()


def test_get_graph_token_calls_correct_url(mock_env, sample_tenant):
    with patch("shared.auth._get_kv_client") as mock_kv, \
         patch("shared.auth.requests.post") as mock_post:
        mock_kv.return_value.get_secret.return_value.value = "test-secret"
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"access_token": "tok-123"}
        mock_post.return_value = mock_resp

        from shared.auth import get_graph_token
        token = get_graph_token(sample_tenant)

    assert token == "tok-123"
    call_url = mock_post.call_args[0][0]
    assert sample_tenant["tenant_id"] in call_url
    assert "oauth2/v2.0/token" in call_url


def test_get_graph_token_raises_on_http_error(mock_env, sample_tenant):
    import requests as req

    with patch("shared.auth._get_kv_client") as mock_kv, \
         patch("shared.auth.requests.post") as mock_post:
        mock_kv.return_value.get_secret.return_value.value = "s"
        mock_post.return_value.raise_for_status.side_effect = req.HTTPError("401")

        from shared.auth import get_graph_token
        with pytest.raises(req.HTTPError):
            get_graph_token(sample_tenant)


def test_get_graph_client_returns_client(mock_env, sample_tenant):
    with patch("shared.auth._get_kv_client") as mock_kv, \
         patch("shared.auth.ClientSecretCredential") as MockCSC, \
         patch("shared.auth.GraphServiceClient") as MockGSC:
        mock_kv.return_value.get_secret.return_value.value = "secret"

        from shared.auth import get_graph_client
        client = get_graph_client(sample_tenant)

    MockCSC.assert_called_once_with(
        tenant_id=sample_tenant["tenant_id"],
        client_id=sample_tenant["app_id"],
        client_secret="secret",
    )
    MockGSC.assert_called_once()
    assert client is MockGSC.return_value
