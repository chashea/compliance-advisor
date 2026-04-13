"""Integration tests for shared.dashboard_queries -- real PostgreSQL."""

import pytest
from shared.dashboard_queries import (
    get_dlp,
    get_governance,
    get_improvement_actions,
    get_irm,
    get_labels,
    get_overview,
    get_purview_incidents,
    get_status,
    get_trend,
)
from shared.db import (
    upsert_dlp_alert,
    upsert_improvement_action,
    upsert_irm_alert,
    upsert_protection_scope,
    upsert_purview_incident,
    upsert_secure_score,
    upsert_sensitivity_label,
    upsert_tenant,
    upsert_trend,
)

pytestmark = pytest.mark.integration


def _seed_tenant(tenant_id="t-001", display_name="Contoso", department="IT"):
    upsert_tenant(tenant_id, display_name, department, "Medium", status="collected")


class TestGetStatus:
    def test_empty_db(self, db_conn):
        result = get_status()
        assert "active_tenants" in result
        assert result["active_tenants"] == 0

    def test_with_tenant(self, db_conn):
        _seed_tenant()
        result = get_status()
        assert result["active_tenants"] >= 1


class TestGetOverview:
    def test_empty_db(self, db_conn):
        result = get_overview()
        assert "labels_summary" in result

    def test_with_data(self, db_conn):
        _seed_tenant()
        upsert_sensitivity_label(
            "t-001", "lbl-1", "Confidential", "", "", True, "", 1, "", "2024-06-01",
            has_protection=True,
        )
        result = get_overview()
        assert result["labels_summary"]["sensitivity_labels"] >= 1

    def test_department_filter(self, db_conn):
        _seed_tenant("t-001", "Contoso", "IT")
        _seed_tenant("t-002", "Fabrikam", "Finance")
        upsert_sensitivity_label(
            "t-001", "lbl-1", "IT Label", "", "", True, "", 1, "", "2024-06-01", has_protection=True,
        )
        upsert_sensitivity_label(
            "t-002", "lbl-2", "Finance Label", "", "", True, "", 1, "", "2024-06-01", has_protection=True,
        )
        result = get_overview(department="IT")
        assert result["labels_summary"]["sensitivity_labels"] == 1


class TestGetLabels:
    def test_returns_labels(self, db_conn):
        _seed_tenant()
        upsert_sensitivity_label(
            "t-001", "lbl-1", "Confidential", "Desc", "#ff0000", True, "", 1, "tip", "2024-06-01",
            has_protection=True,
        )
        result = get_labels()
        assert len(result["sensitivity_labels"]) == 1
        assert result["sensitivity_labels"][0]["name"] == "Confidential"


class TestGetDlp:
    def test_returns_alerts(self, db_conn):
        _seed_tenant()
        upsert_dlp_alert(
            "t-001", "dlp-1", "DLP Alert", "High", "New", "Exfiltration", "Policy 1",
            "2024-06-01", "", "2024-06-01",
        )
        result = get_dlp()
        assert len(result["alerts"]) >= 1

    def test_severity_breakdown(self, db_conn):
        _seed_tenant()
        upsert_dlp_alert(
            "t-001", "dlp-1", "Alert 1", "High", "New", "Cat", "Pol", "2024-06-01", "", "2024-06-01",
        )
        upsert_dlp_alert(
            "t-001", "dlp-2", "Alert 2", "Low", "New", "Cat", "Pol", "2024-06-01", "", "2024-06-01",
        )
        result = get_dlp()
        assert len(result["alerts"]) == 2
        assert len(result["severity_breakdown"]) == 2


class TestGetIrm:
    def test_returns_alerts(self, db_conn):
        _seed_tenant()
        upsert_irm_alert(
            "t-001", "irm-1", "IRM Alert", "Medium", "New", "Data theft", "IRM Policy",
            "2024-06-01", "", "2024-06-01",
        )
        result = get_irm()
        assert len(result["alerts"]) >= 1


class TestGetTrend:
    def test_returns_trend_data(self, db_conn):
        from datetime import date, timedelta

        today = date.today()
        d1 = (today - timedelta(days=2)).isoformat()
        d2 = (today - timedelta(days=1)).isoformat()
        upsert_trend(d1, None, 20, 5, 100, 3)
        upsert_trend(d2, None, 22, 6, 110, 3)
        result = get_trend(days=30)
        assert len(result["trend"]) >= 2


class TestGetGovernance:
    def test_returns_scopes(self, db_conn):
        _seed_tenant()
        upsert_protection_scope("t-001", "DLP", "Enforce", "Exchange", "Upload", "2024-06-01")
        result = get_governance()
        assert len(result["scopes"]) >= 1


class TestGetImprovementActions:
    def test_returns_score_and_actions(self, db_conn):
        _seed_tenant()
        upsert_secure_score("t-001", 75.0, 100.0, "2024-06-01", "2024-06-01", 60.0, 80.0)
        upsert_improvement_action(
            "t-001", "ctrl-1", "Enable MFA", "Data", 10.0, 5.0,
            "Low", "Low", "Tier1", "Azure AD", "Credential theft",
            "Enable MFA for all users", "Default", False, 1, "2024-06-01",
        )
        result = get_improvement_actions()
        assert "secure_score" in result
        assert result["secure_score"]["data_current_score"] == pytest.approx(60.0)
        assert len(result["actions"]) >= 1


class TestGetPurviewIncidents:
    def test_returns_incidents(self, db_conn):
        _seed_tenant()
        upsert_purview_incident(
            "t-001", "inc-1", "Breach", "High", "Active", "TruePositive", "Confirmed",
            "2024-06-01", "2024-06-02", "admin", 5, 3, "2024-06-01",
        )
        result = get_purview_incidents()
        assert len(result["incidents"]) >= 1
        assert len(result["severity_breakdown"]) >= 1
