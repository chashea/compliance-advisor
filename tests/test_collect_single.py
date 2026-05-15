"""Tests for the collect_single HTTP trigger."""

import json
from unittest.mock import MagicMock, patch

import azure.functions as func

TENANT_ID = "12345678-1234-1234-1234-123456789abc"


def _mock_settings(client_id="test-client-id", client_secret="test-secret", audit_days=1):
    s = MagicMock()
    s.COLLECTOR_CLIENT_ID = client_id
    s.COLLECTOR_CLIENT_SECRET = client_secret
    s.COLLECTOR_AUDIT_LOG_DAYS = audit_days
    return s


def _make_request(tenant_id: str) -> func.HttpRequest:
    req = MagicMock(spec=func.HttpRequest)
    req.route_params = {"tenant_id": tenant_id}
    req.get_json.return_value = {}
    req.get_body.return_value = b"{}"
    return req


# ── Happy path ───────────────────────────────────────────────────


@patch("function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("routes.collect._COLLECTOR_IMPORT_ERROR", None)
@patch(
    "routes.collect._collect_single_tenant",
    return_value={"status": "ok", "tenant_id": TENANT_ID, "record_counts": {}},
)
@patch(
    "routes.collect.query",
    return_value=[{"tenant_id": TENANT_ID, "display_name": "Test", "department": "DOJ"}],
)
@patch("shared.config.get_settings")
def test_collect_single_success(mock_settings, mock_query, mock_collect):
    mock_settings.return_value = _mock_settings()
    from functions.function_app import collect_single

    resp = collect_single(_make_request(TENANT_ID))
    assert resp.status_code == 200
    data = json.loads(resp.get_body())
    assert data["status"] == "ok"
    mock_collect.assert_called_once()


# ── Invalid UUID ─────────────────────────────────────────────────


@patch("function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("routes.collect._COLLECTOR_IMPORT_ERROR", None)
def test_collect_single_invalid_uuid():
    from functions.function_app import collect_single

    resp = collect_single(_make_request("not-a-uuid"))
    assert resp.status_code == 400
    assert "UUID" in json.loads(resp.get_body())["error"]


# ── Tenant not found ─────────────────────────────────────────────


@patch("function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("routes.collect._COLLECTOR_IMPORT_ERROR", None)
@patch("routes.collect.query", return_value=[])
def test_collect_single_tenant_not_found(mock_query):
    from functions.function_app import collect_single

    resp = collect_single(_make_request(TENANT_ID))
    assert resp.status_code == 404
    assert "not found" in json.loads(resp.get_body())["error"]


# ── Collector imports unavailable ────────────────────────────────


@patch("function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("routes.collect._COLLECTOR_IMPORT_ERROR", RuntimeError("no msal"))
def test_collect_single_collector_unavailable():
    from functions.function_app import collect_single

    resp = collect_single(_make_request(TENANT_ID))
    assert resp.status_code == 503
    assert "unavailable" in json.loads(resp.get_body())["error"].lower()


# ── Credentials not configured ───────────────────────────────────


@patch("function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("routes.collect._COLLECTOR_IMPORT_ERROR", None)
@patch(
    "routes.collect.query",
    return_value=[{"tenant_id": TENANT_ID, "display_name": "Test", "department": "DOJ"}],
)
@patch("shared.config.get_settings")
def test_collect_single_no_credentials(mock_settings, mock_query):
    mock_settings.return_value = _mock_settings(client_id="", client_secret="")
    from functions.function_app import collect_single

    resp = collect_single(_make_request(TENANT_ID))
    assert resp.status_code == 503
    assert "not configured" in json.loads(resp.get_body())["error"]


# ── Collection failure returns 502 ───────────────────────────────


@patch("function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("routes.collect._COLLECTOR_IMPORT_ERROR", None)
@patch(
    "routes.collect._collect_single_tenant",
    return_value={"status": "error", "tenant_id": TENANT_ID, "error": "auth failed"},
)
@patch(
    "routes.collect.query",
    return_value=[{"tenant_id": TENANT_ID, "display_name": "Test", "department": "DOJ"}],
)
@patch("shared.config.get_settings")
def test_collect_single_failure_returns_502(mock_settings, mock_query, mock_collect):
    mock_settings.return_value = _mock_settings()
    from functions.function_app import collect_single

    resp = collect_single(_make_request(TENANT_ID))
    assert resp.status_code == 502
    data = json.loads(resp.get_body())
    assert data["status"] == "error"
