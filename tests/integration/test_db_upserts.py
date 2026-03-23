"""Integration tests for shared.db upsert functions."""

import pytest
from psycopg2.extras import RealDictCursor
from shared.db import (
    check_ingestion_duplicate,
    record_ingestion,
    update_tenant_status,
    upsert_audit_record,
    upsert_compliance_assessment,
    upsert_dlp_alert,
    upsert_dlp_policy,
    upsert_ediscovery_case,
    upsert_improvement_action,
    upsert_info_barrier_policy,
    upsert_irm_alert,
    upsert_irm_policy,
    upsert_protection_scope,
    upsert_purview_incident,
    upsert_retention_event,
    upsert_retention_event_type,
    upsert_secure_score,
    upsert_sensitive_info_type,
    upsert_sensitivity_label,
    upsert_tenant,
    upsert_threat_assessment_request,
    upsert_trend,
    upsert_user_content_policies,
)

pytestmark = pytest.mark.integration


def _query(conn, sql, params=None):
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


# -- Tenant ---------------------------------------------------------------


class TestUpsertTenant:
    def test_insert(self, db_conn):
        upsert_tenant("t-001", "Contoso", "IT", "High")
        rows = _query(db_conn, "SELECT * FROM tenants WHERE tenant_id = 't-001'")
        assert len(rows) == 1
        assert rows[0]["display_name"] == "Contoso"
        assert rows[0]["department"] == "IT"
        assert rows[0]["risk_tier"] == "High"

    def test_update_on_conflict(self, db_conn):
        upsert_tenant("t-001", "Contoso", "IT", "High")
        upsert_tenant("t-001", "Contoso Updated", "Finance", "Low")
        rows = _query(db_conn, "SELECT * FROM tenants WHERE tenant_id = 't-001'")
        assert len(rows) == 1
        assert rows[0]["display_name"] == "Contoso Updated"
        assert rows[0]["department"] == "Finance"

    def test_insert_with_status(self, db_conn):
        upsert_tenant("t-002", "Fabrikam", "HR", "Medium", status="active")
        rows = _query(db_conn, "SELECT * FROM tenants WHERE tenant_id = 't-002'")
        assert rows[0]["status"] == "active"

    def test_update_preserves_status_when_not_provided(self, db_conn):
        upsert_tenant("t-003", "Woodgrove", "Legal", "Medium", status="collecting")
        upsert_tenant("t-003", "Woodgrove Updated", "Legal", "Medium")
        rows = _query(db_conn, "SELECT * FROM tenants WHERE tenant_id = 't-003'")
        assert rows[0]["display_name"] == "Woodgrove Updated"
        assert rows[0]["status"] == "collecting"


class TestUpdateTenantStatus:
    def test_updates_status(self, db_conn):
        upsert_tenant("t-010", "Test", "IT", "Medium")
        update_tenant_status("t-010", "collected")
        rows = _query(db_conn, "SELECT status FROM tenants WHERE tenant_id = 't-010'")
        assert rows[0]["status"] == "collected"


# -- eDiscovery ------------------------------------------------------------


class TestUpsertEdiscoveryCase:
    def test_insert(self, db_conn):
        upsert_tenant("t-100", "Test Tenant", "IT", "Medium")
        upsert_ediscovery_case("t-100", "case-1", "Case Alpha", "Active", "2024-01-01", "", "ext-1", 3, "2024-06-01")
        rows = _query(db_conn, "SELECT * FROM ediscovery_cases WHERE tenant_id = 't-100'")
        assert len(rows) == 1
        assert rows[0]["display_name"] == "Case Alpha"
        assert rows[0]["custodian_count"] == 3

    def test_update_on_conflict(self, db_conn):
        upsert_tenant("t-100", "Test Tenant", "IT", "Medium")
        upsert_ediscovery_case("t-100", "case-1", "Case Alpha", "Active", "2024-01-01", "", "ext-1", 3, "2024-06-01")
        upsert_ediscovery_case(
            "t-100", "case-1", "Case Alpha Updated", "Closed", "2024-01-01", "2024-06-15", "ext-1", 5, "2024-06-01"
        )
        rows = _query(db_conn, "SELECT * FROM ediscovery_cases WHERE tenant_id = 't-100'")
        assert len(rows) == 1
        assert rows[0]["display_name"] == "Case Alpha Updated"
        assert rows[0]["status"] == "Closed"
        assert rows[0]["custodian_count"] == 5


# -- Sensitivity Labels ----------------------------------------------------


class TestUpsertSensitivityLabel:
    def test_insert(self, db_conn):
        upsert_tenant("t-200", "Label Tenant", "IT", "Medium")
        upsert_sensitivity_label(
            "t-200", "lbl-1", "Confidential", "Top secret", "#ff0000", True, "", 1, "Do not share", "2024-06-01",
            has_protection=True, applicable_to="Files,Emails",
        )
        rows = _query(db_conn, "SELECT * FROM sensitivity_labels WHERE tenant_id = 't-200'")
        assert len(rows) == 1
        assert rows[0]["name"] == "Confidential"
        assert rows[0]["has_protection"] is True


# -- DLP Alert -------------------------------------------------------------


class TestUpsertDlpAlert:
    def test_insert_with_evidence(self, db_conn):
        upsert_tenant("t-300", "DLP Tenant", "IT", "Medium")
        evidence = [{"type": "file", "name": "secret.docx"}]
        upsert_dlp_alert(
            "t-300", "dlp-1", "DLP Hit", "High", "New", "Exfiltration", "DLP Policy 1",
            "2024-06-01", "", "2024-06-01", evidence=evidence,
        )
        rows = _query(db_conn, "SELECT * FROM dlp_alerts WHERE tenant_id = 't-300'")
        assert len(rows) == 1
        assert rows[0]["severity"] == "High"
        assert rows[0]["evidence"] == evidence

    def test_update_on_conflict(self, db_conn):
        upsert_tenant("t-300", "DLP Tenant", "IT", "Medium")
        upsert_dlp_alert(
            "t-300", "dlp-2", "DLP Hit", "High", "New", "Exfiltration", "Policy",
            "2024-06-01", "", "2024-06-01",
        )
        upsert_dlp_alert(
            "t-300", "dlp-2", "DLP Hit Updated", "Medium", "Resolved", "Exfiltration", "Policy",
            "2024-06-01", "2024-06-02", "2024-06-01",
        )
        rows = _query(db_conn, "SELECT * FROM dlp_alerts WHERE alert_id = 'dlp-2'")
        assert len(rows) == 1
        assert rows[0]["title"] == "DLP Hit Updated"
        assert rows[0]["status"] == "Resolved"


# -- IRM Alert -------------------------------------------------------------


class TestUpsertIrmAlert:
    def test_insert(self, db_conn):
        upsert_tenant("t-400", "IRM Tenant", "IT", "Medium")
        upsert_irm_alert(
            "t-400", "irm-1", "Insider Risk", "Medium", "New", "Data theft", "IRM Policy",
            "2024-06-01", "", "2024-06-01",
        )
        rows = _query(db_conn, "SELECT * FROM irm_alerts WHERE tenant_id = 't-400'")
        assert len(rows) == 1


# -- Secure Score ----------------------------------------------------------


class TestUpsertSecureScore:
    def test_insert(self, db_conn):
        upsert_tenant("t-500", "Score Tenant", "IT", "Medium")
        upsert_secure_score("t-500", 75.5, 100.0, "2024-06-01", "2024-06-01", 60.0, 80.0)
        rows = _query(db_conn, "SELECT * FROM secure_scores WHERE tenant_id = 't-500'")
        assert len(rows) == 1
        assert rows[0]["data_current_score"] == pytest.approx(60.0)
        assert rows[0]["data_max_score"] == pytest.approx(80.0)


# -- Improvement Actions ---------------------------------------------------


class TestUpsertImprovementAction:
    def test_insert(self, db_conn):
        upsert_tenant("t-600", "Action Tenant", "IT", "Medium")
        upsert_improvement_action(
            "t-600", "ctrl-1", "Enable MFA", "Identity", 10.0, 5.0,
            "Low", "Low", "Tier1", "Azure AD", "Credential theft",
            "Enable MFA for all users", "Default", False, 1, "2024-06-01",
        )
        rows = _query(db_conn, "SELECT * FROM improvement_actions WHERE tenant_id = 't-600'")
        assert len(rows) == 1
        assert rows[0]["title"] == "Enable MFA"
        assert rows[0]["max_score"] == pytest.approx(10.0)


# -- Ingestion Idempotency ------------------------------------------------


class TestIngestionIdempotency:
    def test_record_and_check_duplicate(self, db_conn):
        record_ingestion("t-700", "2024-06-01", "abc123", {"cases": 5})
        assert check_ingestion_duplicate("t-700", "2024-06-01", "abc123") is True

    def test_different_hash_not_duplicate(self, db_conn):
        record_ingestion("t-700", "2024-06-01", "hash1", {"cases": 5})
        assert check_ingestion_duplicate("t-700", "2024-06-01", "hash2") is False

    def test_duplicate_insert_no_error(self, db_conn):
        record_ingestion("t-700", "2024-06-01", "dup1", {"cases": 1})
        record_ingestion("t-700", "2024-06-01", "dup1", {"cases": 2})


# -- Trend -----------------------------------------------------------------


class TestUpsertTrend:
    def test_insert(self, db_conn):
        upsert_trend("2024-06-01", "IT", 10, 20, 5, 100, 3)
        rows = _query(
            db_conn,
            "SELECT * FROM compliance_trend WHERE snapshot_date = '2024-06-01' AND department = 'IT'",
        )
        assert len(rows) == 1
        assert rows[0]["ediscovery_cases"] == 10

    def test_null_department(self, db_conn):
        upsert_trend("2024-06-01", None, 10, 20, 5, 100, 3)
        rows = _query(
            db_conn,
            "SELECT * FROM compliance_trend WHERE snapshot_date = '2024-06-01' AND department IS NULL",
        )
        assert len(rows) == 1

    def test_update_on_conflict(self, db_conn):
        upsert_trend("2024-06-02", "IT", 10, 20, 5, 100, 3)
        upsert_trend("2024-06-02", "IT", 15, 25, 8, 150, 4)
        rows = _query(
            db_conn,
            "SELECT * FROM compliance_trend WHERE snapshot_date = '2024-06-02' AND department = 'IT'",
        )
        assert len(rows) == 1
        assert rows[0]["ediscovery_cases"] == 15


# -- User Content Policies -------------------------------------------------


class TestUpsertUserContentPolicies:
    def test_batch_insert(self, db_conn):
        upsert_tenant("t-800", "UCP Tenant", "IT", "Medium")
        records = [
            {"user_id": "u1", "user_upn": "u1@contoso.com", "action": "block", "match_count": 3},
            {"user_id": "u2", "user_upn": "u2@contoso.com", "action": "warn", "match_count": 1},
        ]
        count = upsert_user_content_policies("t-800", records, "2024-06-01")
        assert count == 2
        rows = _query(db_conn, "SELECT * FROM user_content_policies WHERE tenant_id = 't-800'")
        assert len(rows) == 2

    def test_empty_records(self, db_conn):
        count = upsert_user_content_policies("t-800", [], "2024-06-01")
        assert count == 0


# -- Purview Incidents -----------------------------------------------------


class TestUpsertPurviewIncident:
    def test_insert(self, db_conn):
        upsert_tenant("t-900", "Incident Tenant", "IT", "Medium")
        upsert_purview_incident(
            "t-900", "inc-1", "Data Breach", "High", "Active", "TruePositive", "Confirmed",
            "2024-06-01", "2024-06-02", "admin@contoso.com", 5, 3, "2024-06-01",
        )
        rows = _query(db_conn, "SELECT * FROM purview_incidents WHERE tenant_id = 't-900'")
        assert len(rows) == 1
        assert rows[0]["purview_alerts_count"] == 3


# -- Remaining upserts (smoke tests) --------------------------------------


class TestRemainingUpserts:
    def test_retention_event(self, db_conn):
        upsert_tenant("t-misc", "Misc Tenant", "IT", "Medium")
        upsert_retention_event("t-misc", "evt-1", "Hire Event", "Employee Hire", "2024-01-01", "Active", "2024-06-01")
        rows = _query(db_conn, "SELECT * FROM retention_events WHERE tenant_id = 't-misc'")
        assert len(rows) == 1

    def test_retention_event_type(self, db_conn):
        upsert_tenant("t-misc2", "Misc2", "IT", "Medium")
        upsert_retention_event_type(
            "t-misc2", "type-1", "Employee Hire", "Triggered on hire",
            "2024-01-01", "2024-02-01", "2024-06-01",
        )
        rows = _query(db_conn, "SELECT * FROM retention_event_types WHERE tenant_id = 't-misc2'")
        assert len(rows) == 1

    def test_audit_record(self, db_conn):
        upsert_tenant("t-misc3", "Misc3", "IT", "Medium")
        upsert_audit_record(
            "t-misc3", "rec-1", "AuditLog", "FileAccessed", "SharePoint",
            "user@contoso.com", "2024-06-01", "2024-06-01",
        )
        rows = _query(db_conn, "SELECT * FROM audit_records WHERE tenant_id = 't-misc3'")
        assert len(rows) == 1

    def test_protection_scope(self, db_conn):
        upsert_tenant("t-misc4", "Misc4", "IT", "Medium")
        upsert_protection_scope("t-misc4", "DLP", "Enforce", "Exchange,SharePoint", "Upload,Download", "2024-06-01")
        rows = _query(db_conn, "SELECT * FROM protection_scopes WHERE tenant_id = 't-misc4'")
        assert len(rows) == 1

    def test_info_barrier_policy(self, db_conn):
        upsert_tenant("t-misc5", "Misc5", "IT", "Medium")
        upsert_info_barrier_policy("t-misc5", "ib-1", "HR Block", "Active", "HR,Legal", "2024-06-01")
        rows = _query(db_conn, "SELECT * FROM info_barrier_policies WHERE tenant_id = 't-misc5'")
        assert len(rows) == 1

    def test_dlp_policy(self, db_conn):
        upsert_tenant("t-misc6", "Misc6", "IT", "Medium")
        upsert_dlp_policy(
            "t-misc6", "pol-1", "Credit Card Policy", "Enabled", "DLP",
            3, "2024-01-01", "2024-06-01", "Enforce", "2024-06-01",
        )
        rows = _query(db_conn, "SELECT * FROM dlp_policies WHERE tenant_id = 't-misc6'")
        assert len(rows) == 1

    def test_irm_policy(self, db_conn):
        upsert_tenant("t-misc7", "Misc7", "IT", "Medium")
        upsert_irm_policy(
            "t-misc7", "irm-pol-1", "Data Theft", "Enabled", "IRM",
            "2024-01-01", "Sequence,CumulativeExfiltration", "2024-06-01",
        )
        rows = _query(db_conn, "SELECT * FROM irm_policies WHERE tenant_id = 't-misc7'")
        assert len(rows) == 1

    def test_sensitive_info_type(self, db_conn):
        upsert_tenant("t-misc8", "Misc8", "IT", "Medium")
        upsert_sensitive_info_type(
            "t-misc8", "sit-1", "SSN", "Social Security Number",
            False, "PII", "Organization", "Enabled", "2024-06-01",
        )
        rows = _query(db_conn, "SELECT * FROM sensitive_info_types WHERE tenant_id = 't-misc8'")
        assert len(rows) == 1

    def test_compliance_assessment(self, db_conn):
        upsert_tenant("t-misc9", "Misc9", "IT", "Medium")
        upsert_compliance_assessment(
            "t-misc9", "assess-1", "NIST 800-171", "Active", "NIST",
            75.5, "2024-01-01", "Data Protection", "2024-06-01",
        )
        rows = _query(db_conn, "SELECT * FROM compliance_assessments WHERE tenant_id = 't-misc9'")
        assert len(rows) == 1

    def test_threat_assessment_request(self, db_conn):
        upsert_tenant("t-misc10", "Misc10", "IT", "Medium")
        upsert_threat_assessment_request(
            "t-misc10", "tar-1", "malware", "file", "completed",
            "2024-06-01", "clean", "No threats detected", "2024-06-01",
        )
        rows = _query(db_conn, "SELECT * FROM threat_assessment_requests WHERE tenant_id = 't-misc10'")
        assert len(rows) == 1
