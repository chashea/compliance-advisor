"""Tests for collector/payload.py — CompliancePayload serialization."""

from datetime import datetime, timezone

from collector.payload import CompliancePayload

TENANT_ID = "12345678-1234-1234-1234-123456789abc"


def _make_payload(**overrides) -> CompliancePayload:
    defaults = {
        "tenant_id": TENANT_ID,
        "agency_id": "AG-001",
        "department": "DOJ",
        "display_name": "Test Tenant",
        "timestamp": "2026-03-08T00:00:00Z",
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
    }
    return CompliancePayload(**{**defaults, **overrides})


# ── Construction ──────────────────────────────────────────────────


def test_default_collector_version():
    p = _make_payload()
    assert isinstance(p.collector_version, str)
    assert len(p.collector_version) > 0


def test_custom_collector_version():
    p = _make_payload(collector_version="4.2.0")
    assert p.collector_version == "4.2.0"


def test_fields_set_correctly():
    p = _make_payload(department="HR", display_name="HR Tenant")
    assert p.tenant_id == TENANT_ID
    assert p.department == "HR"
    assert p.display_name == "HR Tenant"


# ── to_dict ───────────────────────────────────────────────────────


def test_to_dict_returns_dict():
    p = _make_payload()
    d = p.to_dict()
    assert isinstance(d, dict)


def test_to_dict_contains_all_fields():
    p = _make_payload()
    d = p.to_dict()
    expected_keys = {
        "tenant_id",
        "agency_id",
        "department",
        "display_name",
        "timestamp",
        "ediscovery_cases",
        "sensitivity_labels",
        "retention_labels",
        "retention_events",
        "audit_records",
        "dlp_alerts",
        "irm_alerts",
        "subject_rights_requests",
        "comm_compliance_policies",
        "info_barrier_policies",
        "protection_scopes",
        "secure_scores",
        "improvement_actions",
        "user_content_policies",
        "collector_version",
    }
    assert set(d.keys()) == expected_keys


def test_to_dict_preserves_values():
    cases = [{"case_id": "c1", "status": "active"}]
    p = _make_payload(ediscovery_cases=cases)
    d = p.to_dict()
    assert d["ediscovery_cases"] == cases
    assert d["tenant_id"] == TENANT_ID


def test_to_dict_returns_new_dict():
    p = _make_payload()
    d1 = p.to_dict()
    d2 = p.to_dict()
    assert d1 == d2
    assert d1 is not d2


# ── now_iso ───────────────────────────────────────────────────────


def test_now_iso_returns_utc_string():
    ts = CompliancePayload.now_iso()
    parsed = datetime.fromisoformat(ts)
    assert parsed.tzinfo is not None


def test_now_iso_is_current():
    before = datetime.now(timezone.utc)
    ts = CompliancePayload.now_iso()
    after = datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(ts)
    assert before <= parsed <= after


# ── Round-trip (payload → dict → matches schema fields) ──────────


def test_round_trip_matches_schema_required_fields():
    """Verify to_dict() keys match the PAYLOAD_SCHEMA required fields."""
    from shared.validation import PAYLOAD_SCHEMA

    p = _make_payload()
    d = p.to_dict()
    assert set(PAYLOAD_SCHEMA["required"]) == set(d.keys())
