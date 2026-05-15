"""Tests for shared.logging — structured-logging configuration + context binding."""

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _reset_structlog():
    """Force re-configuration so each test sees a fresh pipeline."""
    import shared.logging as slog
    from structlog.contextvars import clear_contextvars

    slog._configured = False
    clear_contextvars()
    yield
    clear_contextvars()
    slog._configured = False


def test_get_logger_auto_configures():
    from shared.logging import get_logger

    log = get_logger("foo")
    # Should be usable immediately
    log.info("hello")


def test_bind_request_context_extracts_client_ip_from_xff():
    from shared.logging import bind_request_context
    from structlog.contextvars import get_contextvars

    req = MagicMock()
    req.headers = {"X-Forwarded-For": "203.0.113.5, 10.0.0.1", "x-ms-request-id": "req-123"}
    bind_request_context(req, route="advisor/dlp")

    ctx = get_contextvars()
    assert ctx["route"] == "advisor/dlp"
    assert ctx["client_ip"] == "203.0.113.5"
    assert ctx["request_id"] == "req-123"


def test_bind_request_context_extras_propagate():
    from shared.logging import bind_request_context
    from structlog.contextvars import get_contextvars

    req = MagicMock()
    req.headers = {}
    bind_request_context(req, route="x", tenant_id="t1", department="DOJ")

    ctx = get_contextvars()
    assert ctx["tenant_id"] == "t1"
    assert ctx["department"] == "DOJ"


def test_bind_request_context_skips_none_values():
    from shared.logging import bind_request_context
    from structlog.contextvars import get_contextvars

    req = MagicMock()
    req.headers = {}
    bind_request_context(req, route="x", tenant_id=None)

    ctx = get_contextvars()
    assert "tenant_id" not in ctx


def test_clear_request_context_removes_bindings():
    from shared.logging import bind_request_context, clear_request_context
    from structlog.contextvars import get_contextvars

    req = MagicMock()
    req.headers = {"X-Forwarded-For": "1.2.3.4"}
    bind_request_context(req, route="x")
    assert get_contextvars()

    clear_request_context()
    assert get_contextvars() == {}


def test_decorator_binds_route_and_clears_on_completion(monkeypatch):
    """The advisor route decorator should bind context on entry and clear on exit."""
    monkeypatch.setenv("AUTH_REQUIRED", "false")
    from shared.config import get_settings

    get_settings.cache_clear()

    import azure.functions as func
    from routes._decorator import register_advisor_route
    from structlog.contextvars import get_contextvars

    captured: dict = {}

    def handler(**kwargs):
        captured["bindings"] = dict(get_contextvars())
        return {"ok": True}

    bp = func.Blueprint()
    register_advisor_route(bp, "test", handler)
    fn = bp._function_builders[0]._function._func

    req = func.HttpRequest(
        method="POST", url="/api/advisor/test", body=b"{}",
        headers={"X-Forwarded-For": "9.8.7.6"},
    )
    resp = fn(req)
    assert resp.status_code == 200

    # During the call, route + client_ip were bound
    assert captured["bindings"]["route"] == "advisor/test"
    assert captured["bindings"]["client_ip"] == "9.8.7.6"

    # After return, context is cleared
    assert get_contextvars() == {}
