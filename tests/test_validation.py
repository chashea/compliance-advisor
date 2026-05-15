"""Tests for functions/shared/validation.py — payload schema validation."""

from unittest.mock import MagicMock, patch

import pytest
from shared.validation import PAYLOAD_SCHEMA, validate_ingestion_request

VALID_TENANT_ID = "12345678-1234-1234-1234-123456789abc"

VALID_PAYLOAD = {
    "tenant_id": VALID_TENANT_ID,
    "agency_id": "AG-001",
    "department": "DOJ",
    "display_name": "Test Tenant",
    "timestamp": "2026-03-08T00:00:00Z",
    "sensitivity_labels": [],
    "retention_events": [],
    "retention_event_types": [],
    "retention_labels": [],
    "audit_records": [],
    "dlp_alerts": [],
    "irm_alerts": [],
    "info_barrier_policies": [],
    "protection_scopes": [],
    "secure_scores": [],
    "improvement_actions": [],
    "user_content_policies": [],
    "dlp_policies": [],
    "irm_policies": [],
    "sensitive_info_types": [],
    "compliance_assessments": [],
    "threat_assessment_requests": [],
    "purview_incidents": [],
    "collector_version": "4.0.0",
}


def _mock_request(body: dict | None = None, *, raise_on_json: bool = False) -> MagicMock:
    req = MagicMock()
    if raise_on_json:
        req.get_json.side_effect = ValueError("no JSON")
    else:
        req.get_json.return_value = body
    return req


def _mock_settings(allowed: str = ""):
    settings = MagicMock()
    settings.ALLOWED_TENANT_IDS = allowed
    settings.allowed_tenants = {t.strip() for t in allowed.split(",") if t.strip()}
    return settings


# ── Schema structure ──────────────────────────────────────────────


def test_schema_requires_all_fields():
    assert set(PAYLOAD_SCHEMA["required"]) == {
        "tenant_id",
        "agency_id",
        "department",
        "display_name",
        "timestamp",
        "sensitivity_labels",
        "retention_events",
        "retention_event_types",
        "retention_labels",
        "audit_records",
        "dlp_alerts",
        "irm_alerts",
        "info_barrier_policies",
        "protection_scopes",
        "secure_scores",
        "improvement_actions",
        "user_content_policies",
        "dlp_policies",
        "irm_policies",
        "sensitive_info_types",
        "compliance_assessments",
        "purview_incidents",
        "collector_version",
    }


def test_schema_disallows_additional_properties():
    assert PAYLOAD_SCHEMA["additionalProperties"] is False


# ── Valid payloads ────────────────────────────────────────────────


@patch("shared.validation.get_settings")
def test_valid_payload_no_allowlist(mock_get):
    mock_get.return_value = _mock_settings("")
    req = _mock_request(VALID_PAYLOAD)
    result = validate_ingestion_request(req)
    assert result == VALID_PAYLOAD


@patch("shared.validation.get_settings")
def test_valid_payload_with_allowlist(mock_get):
    mock_get.return_value = _mock_settings(VALID_TENANT_ID)
    req = _mock_request(VALID_PAYLOAD)
    result = validate_ingestion_request(req)
    assert result["tenant_id"] == VALID_TENANT_ID


@patch("shared.validation.get_settings")
def test_valid_payload_with_populated_arrays(mock_get):
    mock_get.return_value = _mock_settings("")
    payload = {
        **VALID_PAYLOAD,
        "sensitivity_labels": [{"label_id": "sl-1"}],
        "dlp_alerts": [{"alert_id": "a1", "severity": "high"}, {"alert_id": "a2", "severity": "medium"}],
    }
    req = _mock_request(payload)
    result = validate_ingestion_request(req)
    assert len(result["sensitivity_labels"]) == 1
    assert len(result["dlp_alerts"]) == 2


# ── Invalid JSON ──────────────────────────────────────────────────


@patch("shared.validation.get_settings")
def test_invalid_json_raises(mock_get):
    mock_get.return_value = _mock_settings("")
    req = _mock_request(raise_on_json=True)
    with pytest.raises(ValueError, match="Invalid JSON body"):
        validate_ingestion_request(req)


# ── Schema violations ─────────────────────────────────────────────


@patch("shared.validation.get_settings")
def test_missing_required_field(mock_get):
    mock_get.return_value = _mock_settings("")
    payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "tenant_id"}
    req = _mock_request(payload)
    with pytest.raises(ValueError, match="Schema validation failed"):
        validate_ingestion_request(req)


@patch("shared.validation.get_settings")
def test_invalid_tenant_id_format(mock_get):
    mock_get.return_value = _mock_settings("")
    payload = {**VALID_PAYLOAD, "tenant_id": "not-a-uuid"}
    req = _mock_request(payload)
    with pytest.raises(ValueError, match="Schema validation failed"):
        validate_ingestion_request(req)


@patch("shared.validation.get_settings")
def test_wrong_type_for_array_field(mock_get):
    mock_get.return_value = _mock_settings("")
    payload = {**VALID_PAYLOAD, "sensitivity_labels": "not-an-array"}
    req = _mock_request(payload)
    with pytest.raises(ValueError, match="Schema validation failed"):
        validate_ingestion_request(req)


@patch("shared.validation.get_settings")
def test_additional_properties_rejected(mock_get):
    mock_get.return_value = _mock_settings("")
    payload = {**VALID_PAYLOAD, "extra_field": "nope"}
    req = _mock_request(payload)
    with pytest.raises(ValueError, match="Schema validation failed"):
        validate_ingestion_request(req)


@patch("shared.validation.get_settings")
def test_empty_agency_id_rejected(mock_get):
    mock_get.return_value = _mock_settings("")
    payload = {**VALID_PAYLOAD, "agency_id": ""}
    req = _mock_request(payload)
    with pytest.raises(ValueError, match="Schema validation failed"):
        validate_ingestion_request(req)


# ── Array item schema validation ──────────────────────────────────


@patch("shared.validation.get_settings")
def test_dlp_alert_missing_alert_id_rejected(mock_get):
    mock_get.return_value = _mock_settings("")
    payload = {**VALID_PAYLOAD, "dlp_alerts": [{"severity": "high"}]}
    req = _mock_request(payload)
    with pytest.raises(ValueError, match="Schema validation failed"):
        validate_ingestion_request(req)


@patch("shared.validation.get_settings")
def test_dlp_alert_missing_severity_rejected(mock_get):
    mock_get.return_value = _mock_settings("")
    payload = {**VALID_PAYLOAD, "dlp_alerts": [{"alert_id": "a1"}]}
    req = _mock_request(payload)
    with pytest.raises(ValueError, match="Schema validation failed"):
        validate_ingestion_request(req)


@patch("shared.validation.get_settings")
def test_dlp_alert_with_evidence_accepted(mock_get):
    mock_get.return_value = _mock_settings("")
    payload = {
        **VALID_PAYLOAD,
        "dlp_alerts": [
            {
                "alert_id": "a1",
                "severity": "high",
                "classification": "truePositive",
                "determination": "maliciousUserActivity",
                "recommended_actions": "Review and revoke",
                "incident_id": "inc-1",
                "mitre_techniques": "T1567",
                "evidence": [
                    {"type": "mailboxEvidence", "remediation_status": "remediated", "verdict": "malicious"},
                ],
            }
        ],
    }
    req = _mock_request(payload)
    result = validate_ingestion_request(req)
    assert len(result["dlp_alerts"]) == 1
    assert result["dlp_alerts"][0]["classification"] == "truePositive"
    assert len(result["dlp_alerts"][0]["evidence"]) == 1


@patch("shared.validation.get_settings")
def test_secure_score_missing_required_fields_rejected(mock_get):
    mock_get.return_value = _mock_settings("")
    payload = {**VALID_PAYLOAD, "secure_scores": [{"score_date": "2026-03-09"}]}
    req = _mock_request(payload)
    with pytest.raises(ValueError, match="Schema validation failed"):
        validate_ingestion_request(req)


# ── Tenant allow-list ─────────────────────────────────────────────


@patch("shared.validation.get_settings")
def test_tenant_not_in_allowlist_rejected(mock_get):
    mock_get.return_value = _mock_settings("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    req = _mock_request(VALID_PAYLOAD)
    with pytest.raises(ValueError, match="not in allow-list"):
        validate_ingestion_request(req)


@patch("shared.validation.get_settings")
def test_tenant_in_allowlist_passes(mock_get):
    mock_get.return_value = _mock_settings(f"{VALID_TENANT_ID}, aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    req = _mock_request(VALID_PAYLOAD)
    result = validate_ingestion_request(req)
    assert result["tenant_id"] == VALID_TENANT_ID
