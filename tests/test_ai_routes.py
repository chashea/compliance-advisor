import json
from unittest.mock import MagicMock, patch

from function_app import advisor_ask, advisor_briefing, ingest_compliance
from shared.ai_agent import AdvisorAIError

VALID_PAYLOAD = {
    "tenant_id": "12345678-1234-1234-1234-123456789abc",
    "agency_id": "AG-001",
    "department": "DOJ",
    "display_name": "Test Tenant",
    "timestamp": "2026-03-09T00:00:00Z",
    "ediscovery_cases": [],
    "sensitivity_labels": [],
    "retention_labels": [],
    "retention_events": [],
    "audit_records": [],
    "dlp_alerts": [],
    "irm_alerts": [],
    "subject_rights_requests": [],
    "comm_compliance_policies": [],
    "info_barrier_policies": [],
    "protection_scopes": [],
    "secure_scores": [],
    "improvement_actions": [],
    "user_content_policies": [],
    "collector_version": "0.23.0",
}


def _mock_request(body: dict):
    req = MagicMock()
    req.get_json.return_value = body
    return req


@patch("function_app.ask_advisor")
def test_advisor_briefing_returns_structured_ai_error(mock_ask):
    mock_ask.side_effect = AdvisorAIError(
        "ai_service_error",
        "AI service is unavailable right now. Please try again shortly.",
        status_code=502,
    )
    resp = advisor_briefing(_mock_request({}))
    payload = json.loads(resp.get_body().decode("utf-8"))

    assert resp.status_code == 502
    assert payload["code"] == "ai_service_error"
    assert "AI service is unavailable" in payload["error"]


@patch("function_app.check_ingestion_duplicate", return_value=True)
@patch("function_app.validate_ingestion_request", return_value=VALID_PAYLOAD)
def test_ingest_duplicate_returns_ok_with_flag(mock_validate, mock_check):
    req = MagicMock()
    req.get_body.return_value = b'{"tenant_id": "12345678-1234-1234-1234-123456789abc"}'
    resp = ingest_compliance(req)
    payload = json.loads(resp.get_body().decode("utf-8"))

    assert resp.status_code == 200
    assert payload["status"] == "ok"
    assert payload["duplicate"] is True


@patch("function_app.ask_advisor")
def test_advisor_ask_returns_structured_ai_error(mock_ask):
    mock_ask.side_effect = AdvisorAIError(
        "ai_no_data",
        "No compliance data is available yet. Run data collection and try again.",
        status_code=503,
    )
    resp = advisor_ask(_mock_request({"question": "What changed?"}))
    payload = json.loads(resp.get_body().decode("utf-8"))

    assert resp.status_code == 503
    assert payload["code"] == "ai_no_data"
    assert "No compliance data is available yet" in payload["error"]
