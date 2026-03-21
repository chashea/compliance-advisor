"""Tests for functions/shared/dashboard_queries.py — SQL query builders."""

from datetime import date, timedelta
from unittest.mock import patch

from shared.dashboard_queries import (
    get_audit,
    get_dlp,
    get_ediscovery,
    get_governance,
    get_irm,
    get_labels,
    get_overview,
    get_purview_insights,
    get_purview_incidents,
    get_status,
    get_trend,
)

# ── get_status ────────────────────────────────────────────────────


@patch("shared.dashboard_queries.query_one")
def test_get_status_with_data(mock_qo):
    mock_qo.return_value = {"active_tenants": 3, "newest_sync": "2026-03-08"}
    result = get_status()
    assert result == {"active_tenants": 3, "newest_sync": "2026-03-08"}
    mock_qo.assert_called_once()


@patch("shared.dashboard_queries.query_one")
def test_get_status_no_data(mock_qo):
    mock_qo.return_value = None
    result = get_status()
    assert result == {"active_tenants": 0, "newest_sync": None}


# ── get_overview ──────────────────────────────────────────────────


@patch("shared.dashboard_queries.query_one")
@patch("shared.dashboard_queries.query")
def test_get_overview_no_filter(mock_q, mock_qo):
    mock_q.return_value = [{"tenant_id": "t1", "display_name": "T1", "department": "DOJ"}]
    mock_qo.return_value = {"some": "data"}
    result = get_overview()
    assert len(result["tenants"]) == 1
    # query called once (tenants), query_one called 5x (ediscovery, labels, dlp, audit, threats)
    assert mock_q.call_count == 1
    assert mock_qo.call_count == 5


@patch("shared.dashboard_queries.query_one")
@patch("shared.dashboard_queries.query")
def test_get_overview_with_department_filter(mock_q, mock_qo):
    mock_q.return_value = []
    mock_qo.return_value = {}
    get_overview(department="DOJ")
    # Verify department param is passed in SQL params
    tenants_call = mock_q.call_args_list[0]
    sql, params = tenants_call[0]
    assert "%(dept)s" in sql
    assert params["dept"] == "DOJ"


@patch("shared.dashboard_queries.query_one")
@patch("shared.dashboard_queries.query")
def test_get_overview_returns_empty_dicts_on_none(mock_q, mock_qo):
    mock_q.return_value = []
    mock_qo.return_value = None
    result = get_overview()
    assert result["ediscovery_summary"] == {}
    assert result["labels_summary"] == {}
    assert result["dlp_summary"] == {}
    assert result["audit_summary"] == {}


# ── get_ediscovery ────────────────────────────────────────────────


@patch("shared.dashboard_queries.query")
def test_get_ediscovery_returns_cases_and_breakdown(mock_q):
    mock_q.side_effect = [
        [{"case_id": "c1", "status": "active"}],
        [{"status": "active", "total": 1}],
    ]
    result = get_ediscovery()
    assert result["cases"] == [{"case_id": "c1", "status": "active"}]
    assert result["status_breakdown"] == [{"status": "active", "total": 1}]


@patch("shared.dashboard_queries.query")
def test_get_ediscovery_with_department(mock_q):
    mock_q.side_effect = [[], []]
    get_ediscovery(department="HR")
    for c in mock_q.call_args_list:
        sql = c[0][0]
        assert "%(dept)s" in sql


# ── get_labels ────────────────────────────────────────────────────


@patch("shared.dashboard_queries.query")
def test_get_labels_returns_two_sections(mock_q):
    mock_q.side_effect = [
        [{"label_id": "s1"}],
        [{"event_id": "e1"}],
    ]
    result = get_labels()
    assert "sensitivity_labels" in result
    assert "retention_events" in result


# ── get_audit ─────────────────────────────────────────────────────


@patch("shared.dashboard_queries.query")
def test_get_audit_returns_three_sections(mock_q):
    mock_q.side_effect = [
        [{"record_id": "r1"}],
        [{"service": "DLP", "total": 5}],
        [{"operation": "Create", "total": 3}],
    ]
    result = get_audit()
    assert "records" in result
    assert "service_breakdown" in result
    assert "operation_breakdown" in result


# ── get_dlp ───────────────────────────────────────────────────────


@patch("shared.dashboard_queries.query")
def test_get_dlp_returns_all_sections(mock_q):
    evidence_item = {
        "type": "mailboxEvidence",
        "remediation_status": "remediated",
        "verdict": "malicious",
        "roles": ["source"],
        "detailed_roles": [],
    }
    mock_q.side_effect = [
        [{"alert_id": "a1", "severity": "high", "evidence": [evidence_item]}],
        [{"severity": "high", "total": 1, "active": 1}],
        [{"policy_name": "DLP-1", "total": 1}],
        [{"classification": "truePositive", "count": 1}],
    ]
    result = get_dlp()
    assert "alerts" in result
    assert "severity_breakdown" in result
    assert "policy_breakdown" in result
    assert "evidence_summary" in result
    assert "classification_breakdown" in result
    assert result["evidence_summary"]["total_evidence_items"] == 1
    assert result["evidence_summary"]["verdict_breakdown"][0]["verdict"] == "malicious"


@patch("shared.dashboard_queries.query")
def test_get_irm_returns_all_sections(mock_q):
    mock_q.side_effect = [
        [{"alert_id": "i1", "severity": "high", "evidence": []}],
        [{"severity": "high", "total": 1, "active": 1}],
        [{"classification": "unknown", "count": 1}],
    ]
    result = get_irm()
    assert "alerts" in result
    assert "severity_breakdown" in result
    assert "evidence_summary" in result
    assert "classification_breakdown" in result
    assert result["evidence_summary"]["total_evidence_items"] == 0


@patch("shared.dashboard_queries.query")
def test_get_purview_incidents_returns_all_sections(mock_q):
    mock_q.side_effect = [
        [{"incident_id": "inc-1", "severity": "high"}],
        [{"severity": "high", "total": 1, "active": 1}],
        [{"status": "active", "total": 1}],
    ]
    result = get_purview_incidents()
    assert "incidents" in result
    assert "severity_breakdown" in result
    assert "status_breakdown" in result


# ── get_governance ────────────────────────────────────────────────


@patch("shared.dashboard_queries.query")
def test_get_governance_returns_scopes(mock_q):
    mock_q.return_value = [{"scope_type": "dlp", "execution_mode": "active"}]
    result = get_governance()
    assert result["scopes"] == [{"scope_type": "dlp", "execution_mode": "active"}]


# ── get_trend ─────────────────────────────────────────────────────


@patch("shared.dashboard_queries.query")
def test_get_trend_default_30_days(mock_q):
    mock_q.return_value = [{"snapshot_date": "2026-03-01", "tenant_count": 2}]
    result = get_trend()
    sql, params = mock_q.call_args[0]
    expected_cutoff = (date.today() - timedelta(days=30)).isoformat()
    assert params["cutoff"] == expected_cutoff
    assert "department IS NULL" in sql
    assert "to_jsonb(ct)" in sql
    assert result["trend"] == [{"snapshot_date": "2026-03-01", "tenant_count": 2}]


@patch("shared.dashboard_queries.query")
def test_get_trend_custom_days(mock_q):
    mock_q.return_value = []
    get_trend(days=7)
    sql, params = mock_q.call_args[0]
    expected_cutoff = (date.today() - timedelta(days=7)).isoformat()
    assert params["cutoff"] == expected_cutoff


@patch("shared.dashboard_queries.query")
def test_get_trend_with_department(mock_q):
    mock_q.return_value = []
    get_trend(department="DOJ", days=14)
    sql, params = mock_q.call_args[0]
    assert "%(dept)s" in sql
    assert params["dept"] == "DOJ"
    assert "department IS NULL" not in sql


@patch("shared.dashboard_queries.query")
@patch("shared.dashboard_queries.query_one")
def test_get_purview_insights_shape_and_metrics(mock_qo, mock_q):
    mock_q.side_effect = [
        [
            {
                "tenant_id": "t1",
                "display_name": "Contoso",
                "department": "Legal",
                "collected_at": "2026-03-14T08:00:00+00:00",
                "last_snapshot_date": "2026-03-14",
                "last_payload_at": "2026-03-14T08:01:00+00:00",
                "record_counts": {
                    "ediscovery_cases": 1,
                    "sensitivity_labels": 1,
                    "audit_records": 2,
                    "dlp_alerts": 2,
                    "irm_alerts": 1,
                    "info_barrier_policies": 1,
                    "protection_scopes": 1,
                    "dlp_policies": 1,
                    "irm_policies": 1,
                    "sensitive_info_types": 1,
                    "compliance_assessments": 1,
                    "threat_assessment_requests": 1,
                    "purview_incidents": 1,
                },
            }
        ],
        [
            {"owner": "analyst@contoso.com", "total_alerts": 3, "open_alerts": 2, "high_severity": 1, "avg_age_days": 1.5}
        ],
        [
            {"applicable_to": "email, file", "total": 10, "protected": 7},
            {"applicable_to": "site", "total": 3, "protected": 1},
        ],
        [
            {
                "snapshot_date": "2026-03-13",
                "dlp_alerts": 5,
                "active_incidents": 2,
                "data_score_pct": 60.0,
                "policy_changes": 1,
            },
            {
                "snapshot_date": "2026-03-14",
                "dlp_alerts": 2,
                "active_incidents": 1,
                "data_score_pct": 64.0,
                "policy_changes": 0,
            },
        ],
        [
            {
                "assessment_id": "a1",
                "display_name": "NIST 800-53",
                "framework": "NIST 800-53",
                "completion_percentage": 72.0,
                "status": "Active",
                "tenant_name": "Contoso",
            }
        ],
        [
            {
                "control_id": "ctrl-1",
                "title": "Enable DLP",
                "control_category": "Data",
                "max_score": 10.0,
                "current_score": 2.0,
                "threats": "Data exfiltration",
                "remediation": "Enable policy",
                "state": "InProgress",
                "rank": 1,
                "tenant_name": "Contoso",
            }
        ],
        [
            {
                "incident_id": "inc-1",
                "display_name": "Sensitive data leak",
                "severity": "high",
                "status": "active",
                "owner": "analyst@contoso.com",
                "last_update": "2026-03-14",
                "tenant_name": "Contoso",
            }
        ],
    ]
    mock_qo.side_effect = [
        {
            "total_alerts": 6,
            "resolved_alerts": 3,
            "active_alerts": 3,
            "true_positive_alerts": 4,
            "unresolved_high_alerts": 2,
            "unresolved_medium_alerts": 1,
            "mttr_hours": 12.5,
        },
        {"total_labels": 10, "protected_labels": 7},
    ]

    result = get_purview_insights(days=30)

    assert "effectiveness" in result
    assert "classification_coverage" in result
    assert "policy_drift" in result
    assert "data_at_risk" in result
    assert "control_mapping" in result
    assert "owner_actions" in result
    assert "collection_health" in result
    assert result["effectiveness"]["closure_rate_pct"] == 50.0
    assert result["classification_coverage"]["coverage_pct"] == 70.0
    assert result["collection_health"]["complete_tenants"] == 1
    assert result["owner_actions"]["priority_actions"]
