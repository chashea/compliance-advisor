"""Tests for shared.persist.persist_payload — the single upsert orchestrator."""

from unittest.mock import patch


def _all_upsert_targets():
    return [
        "shared.persist.upsert_tenant",
        "shared.persist.upsert_sensitivity_label",
        "shared.persist.upsert_retention_event",
        "shared.persist.upsert_retention_event_type",
        "shared.persist.upsert_retention_label",
        "shared.persist.upsert_audit_record",
        "shared.persist.upsert_dlp_alert",
        "shared.persist.upsert_irm_alert",
        "shared.persist.upsert_protection_scope",
        "shared.persist.upsert_info_barrier_policy",
        "shared.persist.upsert_secure_score",
        "shared.persist.upsert_improvement_action",
        "shared.persist.upsert_dlp_policy",
        "shared.persist.upsert_irm_policy",
        "shared.persist.upsert_sensitive_info_type",
        "shared.persist.upsert_compliance_assessment",
        "shared.persist.upsert_threat_assessment_request",
        "shared.persist.upsert_purview_incident",
        "shared.persist.upsert_user_content_policies",
    ]


def test_empty_payload_skips_tenant_when_no_metadata():
    """Tenant row is not touched when display_name/department are omitted."""
    from unittest.mock import MagicMock

    from shared.persist import persist_payload

    mocks = {name.split(".")[-1]: MagicMock() for name in _all_upsert_targets()}
    with patch.multiple("shared.persist", **mocks):
        counts = persist_payload(tenant_id="t1", snapshot_date="2026-05-15")

    mocks["upsert_tenant"].assert_not_called()
    assert counts["sensitivity_labels"] == 0
    assert counts["dlp_alerts"] == 0
    assert counts["user_content_policies"] == 0


def test_full_payload_calls_each_workload():
    """Every workload list is iterated; counts match input length."""
    from unittest.mock import MagicMock

    from shared import persist

    mocks = {name.split(".")[-1]: MagicMock() for name in _all_upsert_targets()}
    with patch.multiple("shared.persist", **mocks):
        counts = persist.persist_payload(
            tenant_id="t1",
            snapshot_date="2026-05-15",
            display_name="Test Tenant",
            department="DOJ",
            sensitivity_labels=[{"label_id": "l1"}, {"label_id": "l2"}],
            retention_events=[{"event_id": "e1"}],
            retention_event_types=[],
            retention_labels=[{"label_id": "rl1"}, {"label_id": "rl2"}, {"label_id": "rl3"}],
            audit_records=[{"record_id": "a1"}],
            dlp_alerts=[{"alert_id": "d1"}, {"alert_id": "d2"}],
            irm_alerts=[],
            protection_scopes=[{"scope_type": "ps1"}],
            info_barrier_policies=[],
            secure_scores=[{"current_score": 50}],
            improvement_actions=[{"control_id": "c1"}],
            user_content_policies=[{"user_id": "u1"}, {"user_id": "u2"}],
            dlp_policies=[],
            irm_policies=[],
            sensitive_info_types=[{"type_id": "s1"}],
            compliance_assessments=[],
            threat_assessment_requests=[{"request_id": "t1"}],
            purview_incidents=[{"incident_id": "i1"}],
        )

    # Tenant upserted once
    mocks["upsert_tenant"].assert_called_once()

    # Per-workload upsert called N times
    assert mocks["upsert_sensitivity_label"].call_count == 2
    assert mocks["upsert_retention_event"].call_count == 1
    assert mocks["upsert_retention_label"].call_count == 3
    assert mocks["upsert_dlp_alert"].call_count == 2
    assert mocks["upsert_irm_alert"].call_count == 0
    assert mocks["upsert_protection_scope"].call_count == 1
    assert mocks["upsert_user_content_policies"].call_count == 1  # bulk

    # Counts dict
    assert counts["sensitivity_labels"] == 2
    assert counts["retention_labels"] == 3
    assert counts["dlp_alerts"] == 2
    assert counts["irm_alerts"] == 0
    assert counts["user_content_policies"] == 2


def test_tenant_upsert_passes_risk_tier_when_set():
    from unittest.mock import MagicMock

    from shared import persist

    mocks = {name.split(".")[-1]: MagicMock() for name in _all_upsert_targets()}
    with patch.multiple("shared.persist", **mocks):
        persist.persist_payload(
            tenant_id="t1",
            snapshot_date="2026-05-15",
            display_name="T",
            department="D",
            risk_tier="High",
        )

    kwargs = mocks["upsert_tenant"].call_args.kwargs
    assert kwargs == {"tenant_id": "t1", "display_name": "T", "department": "D", "risk_tier": "High"}


def test_alerts_share_helper_with_correct_upsert_fn():
    """DLP and IRM alerts both flow through _persist_alerts; ensure each routes to its own upsert."""
    from unittest.mock import MagicMock

    from shared import persist

    mocks = {name.split(".")[-1]: MagicMock() for name in _all_upsert_targets()}
    with patch.multiple("shared.persist", **mocks):
        persist.persist_payload(
            tenant_id="t1",
            snapshot_date="2026-05-15",
            dlp_alerts=[{"alert_id": "d1", "severity": "high"}],
            irm_alerts=[{"alert_id": "i1", "severity": "low"}],
        )

    mocks["upsert_dlp_alert"].assert_called_once()
    mocks["upsert_irm_alert"].assert_called_once()
    assert mocks["upsert_dlp_alert"].call_args.kwargs["alert_id"] == "d1"
    assert mocks["upsert_irm_alert"].call_args.kwargs["alert_id"] == "i1"
