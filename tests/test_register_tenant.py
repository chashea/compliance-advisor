"""Tests for the register_tenant endpoint."""

import json
from unittest.mock import MagicMock, patch

import azure.functions as func

TENANT_ID = "12345678-1234-1234-1234-123456789abc"


def _make_request(body: dict) -> func.HttpRequest:
    raw = json.dumps(body).encode()
    req = MagicMock(spec=func.HttpRequest)
    req.get_json.return_value = body
    req.get_body.return_value = raw
    return req


def _make_bad_json_request() -> func.HttpRequest:
    req = MagicMock(spec=func.HttpRequest)
    req.get_json.side_effect = ValueError("bad json")
    return req


# ── Valid registration ────────────────────────────────────────────


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("functions.function_app._trigger_collection_async")
@patch("functions.function_app.upsert_tenant")
def test_valid_registration(mock_upsert, mock_trigger):
    from functions.function_app import register_tenant

    resp = register_tenant(
        _make_request(
            {
                "tenant_id": TENANT_ID,
                "display_name": "Contoso",
                "department": "DOJ",
            }
        )
    )
    assert resp.status_code == 200
    data = json.loads(resp.get_body())
    assert data["status"] == "ok"
    assert data["tenant_id"] == TENANT_ID
    assert data["collection"] == "triggered"
    mock_upsert.assert_called_once_with(
        tenant_id=TENANT_ID,
        display_name="Contoso",
        department="DOJ",
        risk_tier="Medium",
    )
    mock_trigger.assert_called_once_with(TENANT_ID, "Contoso", "DOJ")


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("functions.function_app._trigger_collection_async")
@patch("functions.function_app.upsert_tenant")
def test_valid_registration_with_risk_tier(mock_upsert, mock_trigger):
    from functions.function_app import register_tenant

    resp = register_tenant(
        _make_request(
            {
                "tenant_id": TENANT_ID,
                "display_name": "Contoso",
                "department": "DOJ",
                "risk_tier": "High",
            }
        )
    )
    assert resp.status_code == 200
    mock_upsert.assert_called_once_with(
        tenant_id=TENANT_ID,
        display_name="Contoso",
        department="DOJ",
        risk_tier="High",
    )


# ── Missing required fields ──────────────────────────────────────


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
def test_missing_tenant_id():
    from functions.function_app import register_tenant

    resp = register_tenant(_make_request({"display_name": "Contoso", "department": "DOJ"}))
    assert resp.status_code == 400
    assert "tenant_id" in json.loads(resp.get_body())["error"]


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
def test_missing_display_name():
    from functions.function_app import register_tenant

    resp = register_tenant(_make_request({"tenant_id": TENANT_ID, "department": "DOJ"}))
    assert resp.status_code == 400
    assert "display_name" in json.loads(resp.get_body())["error"]


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
def test_missing_department():
    from functions.function_app import register_tenant

    resp = register_tenant(_make_request({"tenant_id": TENANT_ID, "display_name": "Contoso"}))
    assert resp.status_code == 400
    assert "department" in json.loads(resp.get_body())["error"]


# ── Invalid UUID ──────────────────────────────────────────────────


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
def test_invalid_uuid():
    from functions.function_app import register_tenant

    resp = register_tenant(
        _make_request(
            {
                "tenant_id": "not-a-uuid",
                "display_name": "Contoso",
                "department": "DOJ",
            }
        )
    )
    assert resp.status_code == 400
    assert "UUID" in json.loads(resp.get_body())["error"]


# ── Default risk_tier ─────────────────────────────────────────────


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("functions.function_app._trigger_collection_async")
@patch("functions.function_app.upsert_tenant")
def test_default_risk_tier(mock_upsert, mock_trigger):
    from functions.function_app import register_tenant

    register_tenant(
        _make_request(
            {
                "tenant_id": TENANT_ID,
                "display_name": "Contoso",
                "department": "DOJ",
            }
        )
    )
    mock_upsert.assert_called_once()
    assert mock_upsert.call_args.kwargs["risk_tier"] == "Medium"


# ── Consent callback tests ────────────────────────────────────────


def _make_callback_request(params: dict) -> func.HttpRequest:
    req = MagicMock(spec=func.HttpRequest)
    req.params = params
    return req


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("functions.function_app._trigger_collection_async")
@patch("functions.function_app.upsert_tenant")
def test_consent_callback_success(mock_upsert, mock_trigger):
    from functions.function_app import tenant_consent_callback

    resp = tenant_consent_callback(_make_callback_request({"tenant": TENANT_ID, "admin_consent": "True"}))
    assert resp.status_code == 200
    assert TENANT_ID in resp.get_body().decode()
    mock_upsert.assert_called_once_with(
        tenant_id=TENANT_ID,
        display_name=f"Tenant {TENANT_ID[:8]}",
        department="Pending",
        status="pending",
    )
    mock_trigger.assert_called_once_with(TENANT_ID, f"Tenant {TENANT_ID[:8]}", "Pending")


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
def test_consent_callback_error_from_azure():
    from functions.function_app import tenant_consent_callback

    resp = tenant_consent_callback(
        _make_callback_request({"error": "access_denied", "error_description": "Admin declined"})
    )
    assert resp.status_code == 400
    assert "Admin declined" in resp.get_body().decode()


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
def test_consent_callback_no_consent():
    from functions.function_app import tenant_consent_callback

    resp = tenant_consent_callback(_make_callback_request({"tenant": TENANT_ID, "admin_consent": "False"}))
    assert resp.status_code == 400


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
def test_consent_callback_missing_tenant():
    from functions.function_app import tenant_consent_callback

    resp = tenant_consent_callback(_make_callback_request({"admin_consent": "True"}))
    assert resp.status_code == 400


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
def test_consent_callback_invalid_tenant_id():
    from functions.function_app import tenant_consent_callback

    resp = tenant_consent_callback(_make_callback_request({"tenant": "not-a-uuid", "admin_consent": "True"}))
    assert resp.status_code == 400
