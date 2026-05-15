"""Tests for routes._decorator.register_advisor_route."""

from unittest.mock import MagicMock, patch

import azure.functions as func
import pytest


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from shared.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _build_request(body=None) -> func.HttpRequest:
    return func.HttpRequest(
        method="POST",
        url="/api/advisor/test",
        body=(b"{}" if body is None else body),
        headers={"Content-Type": "application/json"},
    )


def _bp_with_handler(handler, **kwargs):
    """Register a route on a fresh blueprint and return the wrapped function."""
    from routes._decorator import register_advisor_route

    bp = func.Blueprint()
    register_advisor_route(bp, "test", handler, **kwargs)
    fb = bp._function_builders[0]
    # The user function is what FunctionBuilder wraps
    return fb._function._func


def test_decorator_returns_handler_result_as_json():
    handler = MagicMock(return_value={"ok": True, "value": 42})
    fn = _bp_with_handler(handler)

    with patch("shared.auth.get_settings", return_value=MagicMock(AUTH_REQUIRED=False)):
        resp = fn(_build_request())

    assert resp.status_code == 200
    import json
    assert json.loads(resp.get_body()) == {"ok": True, "value": 42}


def test_decorator_returns_401_when_auth_missing_and_required():
    handler = MagicMock(return_value={"ok": True})
    fn = _bp_with_handler(handler)

    with patch("shared.auth.get_settings", return_value=MagicMock(AUTH_REQUIRED=True)):
        resp = fn(_build_request())

    assert resp.status_code == 401
    handler.assert_not_called()


def test_decorator_forwards_body_args():
    handler = MagicMock(return_value={})
    fn = _bp_with_handler(handler, body_args=("department", "tenant_id"))

    body = b'{"department": "DOJ", "tenant_id": "t1", "ignored": "x"}'
    with patch("shared.auth.get_settings", return_value=MagicMock(AUTH_REQUIRED=False)):
        fn(_build_request(body))

    handler.assert_called_once_with(department="DOJ", tenant_id="t1")


def test_decorator_returns_500_on_handler_exception():
    handler = MagicMock(side_effect=RuntimeError("boom"))
    fn = _bp_with_handler(handler)

    with patch("shared.auth.get_settings", return_value=MagicMock(AUTH_REQUIRED=False)):
        resp = fn(_build_request())

    assert resp.status_code == 500
    import json
    assert "boom" in json.loads(resp.get_body())["error"]


def test_decorator_handles_no_body_args():
    handler = MagicMock(return_value={"ok": True})
    fn = _bp_with_handler(handler, body_args=())

    with patch("shared.auth.get_settings", return_value=MagicMock(AUTH_REQUIRED=False)):
        fn(_build_request())

    handler.assert_called_once_with()
