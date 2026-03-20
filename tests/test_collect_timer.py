"""Tests for the collect_tenants timer trigger."""

from unittest.mock import MagicMock, patch

import azure.functions as func

TENANT_ID = "12345678-1234-1234-1234-123456789abc"


def _mock_settings(client_id="test-client-id", client_secret="test-secret", audit_days=1):
    s = MagicMock()
    s.COLLECTOR_CLIENT_ID = client_id
    s.COLLECTOR_CLIENT_SECRET = client_secret
    s.COLLECTOR_AUDIT_LOG_DAYS = audit_days
    return s


def _timer_request():
    return MagicMock(spec=func.TimerRequest)


# ── Skip when not configured ─────────────────────────────────────


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("functions.function_app._COLLECTOR_IMPORT_ERROR", None)
@patch("functions.function_app.query")
@patch("shared.config.get_settings")
def test_skips_when_client_id_empty(mock_get_settings, mock_query):
    mock_get_settings.return_value = _mock_settings(client_id="", client_secret="")
    from functions.function_app import collect_tenants

    collect_tenants(_timer_request())
    mock_query.assert_not_called()


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("functions.function_app._COLLECTOR_IMPORT_ERROR", None)
@patch("functions.function_app.query")
@patch("shared.config.get_settings")
def test_skips_when_no_tenants(mock_get_settings, mock_query):
    mock_get_settings.return_value = _mock_settings()
    mock_query.return_value = []
    from functions.function_app import collect_tenants

    collect_tenants(_timer_request())
    mock_query.assert_called_once()


# ── Collector import error ───────────────────────────────────────


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("functions.function_app._COLLECTOR_IMPORT_ERROR", RuntimeError("no msal"))
@patch("functions.function_app.query")
@patch("shared.config.get_settings")
def test_skips_when_collector_imports_failed(mock_get_settings, mock_query):
    mock_get_settings.return_value = _mock_settings()
    from functions.function_app import collect_tenants

    collect_tenants(_timer_request())
    mock_query.assert_not_called()


# ── Successful collection ────────────────────────────────────────


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("functions.function_app._COLLECTOR_IMPORT_ERROR", None)
@patch("functions.function_app.update_tenant_status")
@patch("functions.function_app.upsert_tenant")
@patch("functions.function_app.upsert_ediscovery_case")
@patch("functions.function_app.upsert_sensitivity_label")
@patch("functions.function_app.upsert_secure_score")
@patch("functions.function_app.upsert_user_content_policies")
@patch(
    "functions.function_app.collect_ediscovery",
    return_value=[
        {
            "case_id": "c1",
            "display_name": "Case 1",
            "status": "active",
            "created": "",
            "closed": "",
            "external_id": "",
            "custodian_count": 0,
        }
    ],
)
@patch(
    "functions.function_app.collect_sensitivity_labels",
    return_value=[
        {
            "label_id": "l1",
            "name": "Confidential",
            "description": "",
            "color": "",
            "is_active": True,
            "parent_id": "",
            "priority": 0,
            "tooltip": "",
        }
    ],
)
@patch("functions.function_app.collect_retention_labels", return_value=[])
@patch("functions.function_app.collect_retention_events", return_value=[])
@patch("functions.function_app.collect_audit_log_records", return_value=[])
@patch("functions.function_app.collect_dlp_alerts", return_value=[])
@patch("functions.function_app.collect_irm_alerts", return_value=[])
@patch("functions.function_app.collect_protection_scopes", return_value=[])
@patch(
    "functions.function_app.collect_secure_scores",
    return_value=[
        {
            "current_score": 50,
            "max_score": 100,
            "score_date": "2026-03-19",
            "data_current_score": 10,
            "data_max_score": 20,
        }
    ],
)
@patch("functions.function_app.collect_improvement_actions", return_value=[])
@patch("functions.function_app.collect_subject_rights", return_value=[])
@patch("functions.function_app.collect_comm_compliance", return_value=[])
@patch("functions.function_app.collect_info_barriers", return_value=[])
@patch("functions.function_app.collect_user_content_policies", return_value=[])
@patch("functions.function_app.collect_dlp_policies", return_value=[])
@patch("functions.function_app.collect_irm_policies", return_value=[])
@patch("functions.function_app.collect_sensitive_info_types", return_value=[])
@patch("functions.function_app.collect_assessments", return_value=[])
@patch("functions.function_app.get_graph_token", return_value="fake-token")
@patch(
    "functions.function_app.query",
    return_value=[{"tenant_id": TENANT_ID, "display_name": "Test", "department": "DOJ"}],
)
@patch("shared.config.get_settings")
def test_collects_and_upserts(
    mock_get_settings,
    mock_query,
    mock_get_token,
    mock_assessments,
    mock_sit,
    mock_irm_pol,
    mock_dlp_pol,
    mock_ucp,
    mock_ib,
    mock_cc,
    mock_srr,
    mock_actions,
    mock_scores,
    mock_scopes,
    mock_irm,
    mock_dlp,
    mock_audit,
    mock_ret_events,
    mock_ret_labels,
    mock_sens_labels,
    mock_ediscovery,
    mock_upsert_ucp,
    mock_upsert_score,
    mock_upsert_sens,
    mock_upsert_edisc,
    mock_upsert_tenant,
):
    mock_get_settings.return_value = _mock_settings()
    from functions.function_app import collect_tenants

    collect_tenants(_timer_request())

    mock_get_token.assert_called_once()
    mock_upsert_tenant.assert_called_once()
    mock_upsert_edisc.assert_called_once()
    mock_upsert_sens.assert_called_once()
    mock_upsert_score.assert_called_once()
    mock_upsert_ucp.assert_called_once()


# ── Per-tenant error isolation ───────────────────────────────────


@patch("functions.function_app._DEPENDENCY_IMPORT_ERROR", None)
@patch("functions.function_app._COLLECTOR_IMPORT_ERROR", None)
@patch("functions.function_app.upsert_tenant")
@patch("functions.function_app.collect_ediscovery", return_value=[])
@patch("functions.function_app.collect_sensitivity_labels", return_value=[])
@patch("functions.function_app.collect_retention_labels", return_value=[])
@patch("functions.function_app.collect_retention_events", return_value=[])
@patch("functions.function_app.collect_audit_log_records", return_value=[])
@patch("functions.function_app.collect_dlp_alerts", return_value=[])
@patch("functions.function_app.collect_irm_alerts", return_value=[])
@patch("functions.function_app.collect_protection_scopes", return_value=[])
@patch("functions.function_app.collect_secure_scores", return_value=[])
@patch("functions.function_app.collect_improvement_actions", return_value=[])
@patch("functions.function_app.collect_subject_rights", return_value=[])
@patch("functions.function_app.collect_comm_compliance", return_value=[])
@patch("functions.function_app.collect_info_barriers", return_value=[])
@patch("functions.function_app.collect_user_content_policies", return_value=[])
@patch("functions.function_app.collect_dlp_policies", return_value=[])
@patch("functions.function_app.collect_irm_policies", return_value=[])
@patch("functions.function_app.collect_sensitive_info_types", return_value=[])
@patch("functions.function_app.collect_assessments", return_value=[])
@patch("functions.function_app.get_graph_token")
@patch("functions.function_app.query")
@patch("shared.config.get_settings")
def test_per_tenant_error_isolation(
    mock_get_settings,
    mock_query,
    mock_get_token,
    mock_assessments,
    mock_sit,
    mock_irm_pol,
    mock_dlp_pol,
    mock_ucp,
    mock_ib,
    mock_cc,
    mock_srr,
    mock_actions,
    mock_scores,
    mock_scopes,
    mock_irm,
    mock_dlp,
    mock_audit,
    mock_ret_events,
    mock_ret_labels,
    mock_sens_labels,
    mock_ediscovery,
    mock_upsert_tenant,
):
    mock_get_settings.return_value = _mock_settings()
    mock_query.return_value = [
        {"tenant_id": "tenant-1", "display_name": "T1", "department": "D1"},
        {"tenant_id": "tenant-2", "display_name": "T2", "department": "D2"},
    ]
    # First tenant auth fails, second succeeds
    mock_get_token.side_effect = [RuntimeError("auth failed"), "fake-token"]

    from functions.function_app import collect_tenants

    collect_tenants(_timer_request())

    # Second tenant should still be processed
    assert mock_get_token.call_count == 2
    mock_upsert_tenant.assert_called_once()
