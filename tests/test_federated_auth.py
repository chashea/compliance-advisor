"""Tests for the collector federated-workload-identity auth path (#6)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def _settings(use_federated: bool = False):
    return SimpleNamespace(
        TENANT_ID="11111111-1111-1111-1111-111111111111",
        CLIENT_ID="cid",
        CLIENT_SECRET="secret-value",
        USE_FEDERATED=use_federated,
        login_authority="https://login.microsoftonline.com",
        graph_scope=["https://graph.microsoft.com/.default"],
    )


def test_secret_path_passes_secret_to_msal():
    from collector import auth

    auth._app_cache.clear()
    fake_app = MagicMock()
    fake_app.acquire_token_for_client.return_value = {"access_token": "tok", "expires_in": 3600}

    with patch.object(auth.msal, "ConfidentialClientApplication", return_value=fake_app) as ctor:
        token = auth.get_graph_token(_settings(use_federated=False))

    assert token == "tok"
    args, kwargs = ctor.call_args
    assert kwargs["client_credential"] == "secret-value"


def test_federated_path_passes_assertion_to_msal():
    from collector import auth

    auth._app_cache.clear()
    fake_app = MagicMock()
    fake_app.acquire_token_for_client.return_value = {"access_token": "tok", "expires_in": 3600}

    with (
        patch.object(auth, "_get_federated_assertion", return_value="federated-jwt"),
        patch.object(auth.msal, "ConfidentialClientApplication", return_value=fake_app) as ctor,
    ):
        token = auth.get_graph_token(_settings(use_federated=True))

    assert token == "tok"
    _, kwargs = ctor.call_args
    assert kwargs["client_credential"] == {"client_assertion": "federated-jwt"}


def test_federated_mode_does_not_cache_msal_app():
    """Federated assertions are short-lived; rebuild MSAL app each call."""
    from collector import auth

    auth._app_cache.clear()
    fake_app = MagicMock()
    fake_app.acquire_token_for_client.return_value = {"access_token": "tok", "expires_in": 3600}

    with (
        patch.object(auth, "_get_federated_assertion", return_value="jwt-1"),
        patch.object(auth.msal, "ConfidentialClientApplication", return_value=fake_app) as ctor,
    ):
        auth.get_graph_token(_settings(use_federated=True))
        auth.get_graph_token(_settings(use_federated=True))

    assert ctor.call_count == 2


def test_secret_mode_caches_msal_app():
    from collector import auth

    auth._app_cache.clear()
    fake_app = MagicMock()
    fake_app.acquire_token_for_client.return_value = {"access_token": "tok", "expires_in": 3600}

    with patch.object(auth.msal, "ConfidentialClientApplication", return_value=fake_app) as ctor:
        auth.get_graph_token(_settings(use_federated=False))
        auth.get_graph_token(_settings(use_federated=False))

    assert ctor.call_count == 1
