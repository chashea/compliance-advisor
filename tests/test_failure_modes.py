"""Tests for the failure-mode contract enforced by routes/_decorator.py."""

from unittest.mock import MagicMock, patch

import azure.functions as func
import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from shared.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _bp_handler(handler, **kwargs):
    """Register a route on a fresh blueprint and return the wrapped function."""
    from routes._decorator import register_advisor_route

    bp = func.Blueprint()
    register_advisor_route(bp, "test", handler, **kwargs)
    return bp._function_builders[0]._function._func


def _req(body: bytes = b"") -> func.HttpRequest:
    return func.HttpRequest(
        method="POST",
        url="/api/advisor/test",
        body=body,
        headers={"Content-Type": "application/json"},
    )


def _no_auth_required():
    return patch("shared.auth.get_settings", return_value=MagicMock(AUTH_REQUIRED=False))


# ── BadJSONBodyError → 400 ────────────────────────────────────────


def test_get_body_returns_empty_dict_for_empty_body():
    from routes._decorator import get_body

    assert get_body(_req(b"")) == {}
    assert get_body(_req(b"  \n  ")) == {}


def test_get_body_raises_on_malformed_json():
    from routes._decorator import BadJSONBodyError, get_body

    with pytest.raises(BadJSONBodyError):
        get_body(_req(b"{not-json}"))


def test_get_body_or_400_returns_response_on_malformed():
    from routes._decorator import get_body_or_400

    body, err = get_body_or_400(_req(b"{not-json}"))
    assert body == {}
    assert err is not None
    assert err.status_code == 400


def test_decorator_returns_400_for_malformed_body():
    handler = MagicMock(return_value={"ok": True})
    fn = _bp_handler(handler)

    with _no_auth_required():
        resp = fn(_req(b"{garbage"))

    assert resp.status_code == 400
    handler.assert_not_called()


# ── ValueError → 400 (was 500) ────────────────────────────────────


def test_decorator_translates_handler_value_error_to_400():
    """Validation failures inside handlers should be 400, not 500."""
    handler = MagicMock(side_effect=ValueError("days must be positive"))
    fn = _bp_handler(handler)

    with _no_auth_required():
        resp = fn(_req(b"{}"))

    assert resp.status_code == 400
    import json
    assert "days must be positive" in json.loads(resp.get_body())["error"]


def test_decorator_treats_other_exceptions_as_500():
    """Unexpected errors stay as 500."""
    handler = MagicMock(side_effect=RuntimeError("db down"))
    fn = _bp_handler(handler)

    with _no_auth_required():
        resp = fn(_req(b"{}"))

    assert resp.status_code == 500


# ── Empty body still works (positive case) ────────────────────────


def test_decorator_passes_empty_body_through():
    handler = MagicMock(return_value={"ok": True})
    fn = _bp_handler(handler)

    with _no_auth_required():
        resp = fn(_req(b""))

    assert resp.status_code == 200
    handler.assert_called_once_with(department=None, tenant_id=None)
