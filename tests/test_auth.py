"""Tests for shared.auth.require_auth — fail-closed vs dev-mode behavior."""

import base64
import json
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from shared.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _req(headers: dict | None = None) -> MagicMock:
    req = MagicMock()
    req.headers = headers or {}
    return req


def _make_principal_header(claims: dict) -> str:
    return base64.b64encode(json.dumps(claims).encode()).decode()


def _settings_with(auth_required: bool):
    """Return a fake FunctionSettings that bypasses env loading."""
    return MagicMock(AUTH_REQUIRED=auth_required)


def test_missing_header_rejects_when_auth_required():
    from shared import auth

    with patch.object(auth, "get_settings", return_value=_settings_with(True)):
        result = auth.require_auth(_req())
    assert result is None


def test_missing_header_passes_when_auth_optional():
    from shared import auth

    with patch.object(auth, "get_settings", return_value=_settings_with(False)):
        result = auth.require_auth(_req())
    assert result == {}


def test_valid_header_decodes_principal():
    from shared import auth

    claims = {"userPrincipalName": "alice@example.gov", "tid": "11111111-1111-1111-1111-111111111111"}
    headers = {"X-MS-CLIENT-PRINCIPAL": _make_principal_header(claims)}

    # AUTH_REQUIRED value is irrelevant when a valid header is present
    with patch.object(auth, "get_settings", return_value=_settings_with(True)):
        result = auth.require_auth(_req(headers))
    assert result == claims


def test_malformed_header_rejected_regardless_of_setting():
    from shared import auth

    headers = {"X-MS-CLIENT-PRINCIPAL": "not-base64!!"}

    with patch.object(auth, "get_settings", return_value=_settings_with(False)):
        result = auth.require_auth(_req(headers))
    assert result is None
