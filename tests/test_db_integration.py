"""DB-layer integration tests.

Requires TEST_DATABASE_URL pointing at a live PostgreSQL instance.
Skipped automatically when the env var is absent (unit-test-only runs).

Run locally:
    TEST_DATABASE_URL="postgresql://user:pass@localhost/dbname" \\
        python3.12 -m pytest tests/test_db_integration.py -v
"""

import os
from pathlib import Path
from unittest.mock import patch

import psycopg2
import pytest
from psycopg2.pool import ThreadedConnectionPool

import shared.db as db
from shared.db import (
    check_ingestion_duplicate,
    record_ingestion,
    upsert_audit_record,
    upsert_comm_compliance_policy,
    upsert_compliance_assessment,
    upsert_dlp_alert,
    upsert_dlp_policy,
    upsert_ediscovery_case,
    upsert_improvement_action,
    upsert_info_barrier_policy,
    upsert_irm_alert,
    upsert_irm_policy,
    upsert_protection_scope,
    upsert_retention_event,
    upsert_retention_label,
    upsert_secure_score,
    upsert_sensitive_info_type,
    upsert_sensitivity_label,
    upsert_subject_rights_request,
    upsert_tenant,
    upsert_trend,
    upsert_user_content_policies,
)

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"

TENANT_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
SNAPSHOT = "2026-03-20"


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def pg_url():
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set — skipping DB integration tests")
    return url


@pytest.fixture(scope="session")
def apply_schema(pg_url):
    """Apply schema.sql once per session."""
    conn = psycopg2.connect(pg_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(SCHEMA_PATH.read_text())
    conn.close()


@pytest.fixture(autouse=True)
def clean_db(pg_url, apply_schema):
    """Truncate all tables before each test (CASCADE handles FK children)."""
    conn = psycopg2.connect(pg_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("TRUNCATE tenants, compliance_trend, ingestion_log RESTART IDENTITY CASCADE")
    conn.close()


@pytest.fixture(autouse=True)
def patch_pool(pg_url, apply_schema):
    """Redirect the global connection pool to the test DB."""
    pool = ThreadedConnectionPool(1, 5, dsn=pg_url)
    with patch.object(db, "_pool", pool):
        yield
    pool.closeall()


# ── Helpers ─────────────────────────────────────────────────────────


def _count(pg_url: str, table: str) -> int:
    conn = psycopg2.connect(pg_url)
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
            return cur.fetchone()[0]
    finally:
        conn.close()


def _one(pg_url: str, table: str, where: str = "", params: tuple = ()) -> dict | None:
    conn = psycopg2.connect(pg_url)
    try:
        with conn.cursor() as cur:
            sql = f"SELECT * FROM {table}"  # noqa: S608
            if where:
                sql += f" WHERE {where}"
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            row = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    finally:
        conn.close()


def _seed_tenant():
    upsert_tenant(TENANT_ID, "Test Agency", "DOJ")


# ── tenant ──────────────────────────────────────────────────────────


def test_upsert_tenant_insert(pg_url):
    upsert_tenant(TENANT_ID, "Test Agency", "DOJ")
    row = _one(pg_url, "tenants", "tenant_id = %s", (TENANT_ID,))
    assert row is not None
    assert row["display_name"] == "Test Agency"
    assert row["department"] == "DOJ"
    assert row["risk_tier"] == "Medium"


def test_upsert_tenant_update(pg_url):
    upsert_tenant(TENANT_ID, "Test Agency", "DOJ")
    upsert_tenant(TENANT_ID, "Updated Agency", "FBI", risk_tier="High")
    row = _one(pg_url, "tenants", "tenant_id = %s", (TENANT_ID,))
    assert row["display_name"] == "Updated Agency"
    assert row["risk_tier"] == "High"
    assert _count(pg_url, "tenants") == 1


# ── ediscovery_cases ────────────────────────────────────────────────


def test_upsert_ediscovery_case_insert(pg_url):
    _seed_tenant()
    upsert_ediscovery_case(TENANT_ID, "case-1", "Case One", "active", "2026-01-01", "", "", 3, SNAPSHOT)
    assert _count(pg_url, "ediscovery_cases") == 1


def test_upsert_ediscovery_case_conflict_updates(pg_url):
    _seed_tenant()
    upsert_ediscovery_case(TENANT_ID, "case-1", "Case One", "active", "2026-01-01", "", "", 3, SNAPSHOT)
    upsert_ediscovery_case(TENANT_ID, "case-1", "Case One Updated", "closed", "2026-01-01", "2026-03-01", "", 5, SNAPSHOT)
    row = _one(pg_url, "ediscovery_cases", "case_id = %s", ("case-1",))
    assert row["status"] == "closed"
    assert row["custodian_count"] == 5
    assert _count(pg_url, "ediscovery_cases") == 1


# ── sensitivity_labels ──────────────────────────────────────────────


def test_upsert_sensitivity_label_insert(pg_url):
    _seed_tenant()
    upsert_sensitivity_label(TENANT_ID, "lbl-1", "Confidential", "Desc", "#FF0000", True, "", 1, "Tip", SNAPSHOT)
    assert _count(pg_url, "sensitivity_labels") == 1


def test_upsert_sensitivity_label_conflict_updates(pg_url):
    _seed_tenant()
    upsert_sensitivity_label(TENANT_ID, "lbl-1", "Confidential", "Desc", "#FF0000", True, "", 1, "Tip", SNAPSHOT)
    upsert_sensitivity_label(TENANT_ID, "lbl-1", "Confidential v2", "New desc", "#00FF00", False, "", 2, "Tip2", SNAPSHOT)
    row = _one(pg_url, "sensitivity_labels", "label_id = %s", ("lbl-1",))
    assert row["name"] == "Confidential v2"
    assert row["priority"] == 2
    assert _count(pg_url, "sensitivity_labels") == 1


# ── retention_labels ────────────────────────────────────────────────


def test_upsert_retention_label_insert(pg_url):
    _seed_tenant()
    upsert_retention_label(TENANT_ID, "rl-1", "7-Year Retention", "2555", "DateCreated", "Delete", True, "published", SNAPSHOT)
    assert _count(pg_url, "retention_labels") == 1


def test_upsert_retention_label_conflict_updates(pg_url):
    _seed_tenant()
    upsert_retention_label(TENANT_ID, "rl-1", "7-Year Retention", "2555", "DateCreated", "Delete", True, "published", SNAPSHOT)
    upsert_retention_label(TENANT_ID, "rl-1", "10-Year Retention", "3650", "DateCreated", "Delete", True, "published", SNAPSHOT)
    row = _one(pg_url, "retention_labels", "label_id = %s", ("rl-1",))
    assert row["display_name"] == "10-Year Retention"
    assert _count(pg_url, "retention_labels") == 1


# ── retention_events ────────────────────────────────────────────────


def test_upsert_retention_event_insert(pg_url):
    _seed_tenant()
    upsert_retention_event(TENANT_ID, "evt-1", "Contract End", "ContractExpired", "2026-01-15", "active", SNAPSHOT)
    assert _count(pg_url, "retention_events") == 1


# ── audit_records ───────────────────────────────────────────────────


def test_upsert_audit_record_insert(pg_url):
    _seed_tenant()
    upsert_audit_record(TENANT_ID, "rec-1", "SharePoint", "FileAccessed", "SharePoint", "user-uuid-1", "2026-03-01T10:00:00Z", SNAPSHOT)
    assert _count(pg_url, "audit_records") == 1


def test_upsert_audit_record_optional_fields(pg_url):
    _seed_tenant()
    upsert_audit_record(
        TENANT_ID, "rec-2", "Exchange", "Send", "Exchange", "user-uuid-2", "2026-03-02T09:00:00Z", SNAPSHOT,
        ip_address="10.0.0.1", client_app="Outlook", result_status="Success",
    )
    row = _one(pg_url, "audit_records", "record_id = %s", ("rec-2",))
    assert row["ip_address"] == "10.0.0.1"
    assert row["client_app"] == "Outlook"


def test_upsert_audit_record_conflict_updates(pg_url):
    _seed_tenant()
    upsert_audit_record(TENANT_ID, "rec-1", "SharePoint", "FileAccessed", "SharePoint", "user-uuid-1", "2026-03-01T10:00:00Z", SNAPSHOT)
    upsert_audit_record(TENANT_ID, "rec-1", "SharePoint", "FileDeleted", "SharePoint", "user-uuid-1", "2026-03-01T10:00:00Z", SNAPSHOT)
    row = _one(pg_url, "audit_records", "record_id = %s", ("rec-1",))
    assert row["operation"] == "FileDeleted"
    assert _count(pg_url, "audit_records") == 1


# ── dlp_alerts ──────────────────────────────────────────────────────


def test_upsert_dlp_alert_insert(pg_url):
    _seed_tenant()
    upsert_dlp_alert(TENANT_ID, "dlp-1", "SSN Exfil", "High", "active", "DataExfiltration", "SSN Policy", "2026-03-10", "", SNAPSHOT)
    assert _count(pg_url, "dlp_alerts") == 1


def test_upsert_dlp_alert_conflict_updates(pg_url):
    _seed_tenant()
    upsert_dlp_alert(TENANT_ID, "dlp-1", "SSN Exfil", "High", "active", "DataExfiltration", "SSN Policy", "2026-03-10", "", SNAPSHOT)
    upsert_dlp_alert(TENANT_ID, "dlp-1", "SSN Exfil", "High", "resolved", "DataExfiltration", "SSN Policy", "2026-03-10", "2026-03-11", SNAPSHOT)
    row = _one(pg_url, "dlp_alerts", "alert_id = %s", ("dlp-1",))
    assert row["status"] == "resolved"
    assert row["resolved"] == "2026-03-11"
    assert _count(pg_url, "dlp_alerts") == 1


# ── irm_alerts ──────────────────────────────────────────────────────


def test_upsert_irm_alert_insert(pg_url):
    _seed_tenant()
    upsert_irm_alert(TENANT_ID, "irm-1", "Risky User", "Medium", "active", "InsiderRisk", "IRM Policy A", "2026-03-05", "", SNAPSHOT)
    assert _count(pg_url, "irm_alerts") == 1


def test_upsert_irm_alert_conflict_updates(pg_url):
    _seed_tenant()
    upsert_irm_alert(TENANT_ID, "irm-1", "Risky User", "Medium", "active", "InsiderRisk", "IRM Policy A", "2026-03-05", "", SNAPSHOT)
    upsert_irm_alert(TENANT_ID, "irm-1", "Risky User", "High", "resolved", "InsiderRisk", "IRM Policy A", "2026-03-05", "2026-03-06", SNAPSHOT)
    row = _one(pg_url, "irm_alerts", "alert_id = %s", ("irm-1",))
    assert row["severity"] == "High"
    assert _count(pg_url, "irm_alerts") == 1


# ── protection_scopes ───────────────────────────────────────────────


def test_upsert_protection_scope_insert(pg_url):
    _seed_tenant()
    upsert_protection_scope(TENANT_ID, "Endpoint", "Automatic", "AllDevices", "FileRead,FileWrite", SNAPSHOT)
    assert _count(pg_url, "protection_scopes") == 1


def test_upsert_protection_scope_conflict_updates(pg_url):
    _seed_tenant()
    upsert_protection_scope(TENANT_ID, "Endpoint", "Automatic", "AllDevices", "FileRead", SNAPSHOT)
    upsert_protection_scope(TENANT_ID, "Endpoint", "Manual", "ManagedDevices", "FileRead,FileWrite", SNAPSHOT)
    row = _one(pg_url, "protection_scopes", "scope_type = %s", ("Endpoint",))
    assert row["execution_mode"] == "Manual"
    assert _count(pg_url, "protection_scopes") == 1


# ── subject_rights_requests ─────────────────────────────────────────


def test_upsert_subject_rights_request_insert(pg_url):
    _seed_tenant()
    upsert_subject_rights_request(TENANT_ID, "srr-1", "Delete Request", "delete", "active", "2026-02-01", "", "customer", SNAPSHOT)
    assert _count(pg_url, "subject_rights_requests") == 1


# ── comm_compliance_policies ────────────────────────────────────────


def test_upsert_comm_compliance_policy_insert(pg_url):
    _seed_tenant()
    upsert_comm_compliance_policy(TENANT_ID, "pol-1", "Harassment Policy", "enabled", "CommunicationCompliance", 5, SNAPSHOT)
    assert _count(pg_url, "comm_compliance_policies") == 1


def test_upsert_comm_compliance_policy_conflict_updates(pg_url):
    _seed_tenant()
    upsert_comm_compliance_policy(TENANT_ID, "pol-1", "Harassment Policy", "enabled", "CommunicationCompliance", 5, SNAPSHOT)
    upsert_comm_compliance_policy(TENANT_ID, "pol-1", "Harassment Policy", "enabled", "CommunicationCompliance", 12, SNAPSHOT)
    row = _one(pg_url, "comm_compliance_policies", "policy_id = %s", ("pol-1",))
    assert row["review_pending_count"] == 12
    assert _count(pg_url, "comm_compliance_policies") == 1


# ── info_barrier_policies ───────────────────────────────────────────


def test_upsert_info_barrier_policy_insert(pg_url):
    _seed_tenant()
    upsert_info_barrier_policy(TENANT_ID, "ibp-1", "FIN-LEGAL Barrier", "active", "Finance,Legal", SNAPSHOT)
    assert _count(pg_url, "info_barrier_policies") == 1


# ── secure_scores ───────────────────────────────────────────────────


def test_upsert_secure_score_insert(pg_url):
    _seed_tenant()
    upsert_secure_score(TENANT_ID, 72.5, 200.0, "2026-03-19", SNAPSHOT, data_current_score=30.0, data_max_score=80.0)
    row = _one(pg_url, "secure_scores", "tenant_id = %s", (TENANT_ID,))
    assert row["current_score"] == pytest.approx(72.5)
    assert row["data_current_score"] == pytest.approx(30.0)


def test_upsert_secure_score_conflict_updates(pg_url):
    _seed_tenant()
    upsert_secure_score(TENANT_ID, 72.5, 200.0, "2026-03-19", SNAPSHOT)
    upsert_secure_score(TENANT_ID, 85.0, 200.0, "2026-03-19", SNAPSHOT, data_current_score=40.0, data_max_score=80.0)
    row = _one(pg_url, "secure_scores", "tenant_id = %s", (TENANT_ID,))
    assert row["current_score"] == pytest.approx(85.0)
    assert _count(pg_url, "secure_scores") == 1


# ── improvement_actions ─────────────────────────────────────────────


def test_upsert_improvement_action_insert(pg_url):
    _seed_tenant()
    upsert_improvement_action(
        TENANT_ID, "ctrl-mfa", "Enable MFA", "Identity", 10.0, 10.0,
        "Low", "Low", "Advanced", "Azure AD", "Credential theft", "Enable MFA for all users",
        "Implemented", False, 1, SNAPSHOT,
    )
    assert _count(pg_url, "improvement_actions") == 1


def test_upsert_improvement_action_conflict_updates(pg_url):
    _seed_tenant()
    upsert_improvement_action(
        TENANT_ID, "ctrl-mfa", "Enable MFA", "Identity", 10.0, 0.0,
        "Low", "Low", "Advanced", "Azure AD", "Credential theft", "Enable MFA",
        "Default", False, 1, SNAPSHOT,
    )
    upsert_improvement_action(
        TENANT_ID, "ctrl-mfa", "Enable MFA", "Identity", 10.0, 10.0,
        "Low", "Low", "Advanced", "Azure AD", "Credential theft", "Enable MFA",
        "Implemented", False, 1, SNAPSHOT,
    )
    row = _one(pg_url, "improvement_actions", "control_id = %s", ("ctrl-mfa",))
    assert row["state"] == "Implemented"
    assert row["current_score"] == pytest.approx(10.0)
    assert _count(pg_url, "improvement_actions") == 1


# ── user_content_policies ───────────────────────────────────────────


def test_upsert_user_content_policies_batch_insert(pg_url):
    _seed_tenant()
    records = [
        {"user_id": "uid-1", "user_upn": "alice@agency.gov", "action": "Block", "policy_id": "p1", "policy_name": "DLP-1", "rule_id": "r1", "rule_name": "Rule-1", "match_count": 3},
        {"user_id": "uid-2", "user_upn": "bob@agency.gov", "action": "Warn", "policy_id": "p1", "policy_name": "DLP-1", "rule_id": "r1", "rule_name": "Rule-1", "match_count": 1},
    ]
    inserted = upsert_user_content_policies(TENANT_ID, records, SNAPSHOT)
    assert inserted == 2
    assert _count(pg_url, "user_content_policies") == 2


def test_upsert_user_content_policies_empty_noop(pg_url):
    _seed_tenant()
    inserted = upsert_user_content_policies(TENANT_ID, [], SNAPSHOT)
    assert inserted == 0
    assert _count(pg_url, "user_content_policies") == 0


def test_upsert_user_content_policies_conflict_updates(pg_url):
    _seed_tenant()
    records = [{"user_id": "uid-1", "user_upn": "alice@agency.gov", "action": "Warn", "match_count": 1}]
    upsert_user_content_policies(TENANT_ID, records, SNAPSHOT)
    records_updated = [{"user_id": "uid-1", "user_upn": "alice@agency.gov", "action": "Block", "match_count": 5}]
    upsert_user_content_policies(TENANT_ID, records_updated, SNAPSHOT)
    row = _one(pg_url, "user_content_policies", "user_id = %s", ("uid-1",))
    assert row["action"] == "Block"
    assert row["match_count"] == 5
    assert _count(pg_url, "user_content_policies") == 1


# ── dlp_policies ────────────────────────────────────────────────────


def test_upsert_dlp_policy_insert(pg_url):
    _seed_tenant()
    upsert_dlp_policy(TENANT_ID, "dp-1", "SSN Policy", "enabled", "DLP", 3, "2025-01-01", "2026-01-01", "Enforce", SNAPSHOT)
    assert _count(pg_url, "dlp_policies") == 1


# ── irm_policies ────────────────────────────────────────────────────


def test_upsert_irm_policy_insert(pg_url):
    _seed_tenant()
    upsert_irm_policy(TENANT_ID, "ip-1", "Data Theft", "active", "IRM", "2025-06-01", "FileDownload,USBCopy", SNAPSHOT)
    assert _count(pg_url, "irm_policies") == 1


# ── sensitive_info_types ────────────────────────────────────────────


def test_upsert_sensitive_info_type_insert(pg_url):
    _seed_tenant()
    upsert_sensitive_info_type(TENANT_ID, "sit-1", "US SSN", "Social Security Number", False, "Financial", "Organization", "enabled", SNAPSHOT)
    assert _count(pg_url, "sensitive_info_types") == 1


# ── compliance_assessments ──────────────────────────────────────────


def test_upsert_compliance_assessment_insert(pg_url):
    _seed_tenant()
    upsert_compliance_assessment(TENANT_ID, "ca-1", "NIST 800-53", "inProgress", "NIST", 65.0, "2026-01-01", "Regulatory", SNAPSHOT)
    row = _one(pg_url, "compliance_assessments", "assessment_id = %s", ("ca-1",))
    assert row["completion_percentage"] == pytest.approx(65.0)


def test_upsert_compliance_assessment_conflict_updates(pg_url):
    _seed_tenant()
    upsert_compliance_assessment(TENANT_ID, "ca-1", "NIST 800-53", "inProgress", "NIST", 65.0, "2026-01-01", "Regulatory", SNAPSHOT)
    upsert_compliance_assessment(TENANT_ID, "ca-1", "NIST 800-53", "completed", "NIST", 100.0, "2026-01-01", "Regulatory", SNAPSHOT)
    row = _one(pg_url, "compliance_assessments", "assessment_id = %s", ("ca-1",))
    assert row["status"] == "completed"
    assert row["completion_percentage"] == pytest.approx(100.0)
    assert _count(pg_url, "compliance_assessments") == 1


# ── compliance_trend ────────────────────────────────────────────────


def test_upsert_trend_insert(pg_url):
    upsert_trend(SNAPSHOT, "DOJ", 10, 5, 20, 3, 100, 2)
    assert _count(pg_url, "compliance_trend") == 1


def test_upsert_trend_conflict_updates(pg_url):
    upsert_trend(SNAPSHOT, "DOJ", 10, 5, 20, 3, 100, 2)
    upsert_trend(SNAPSHOT, "DOJ", 15, 6, 22, 4, 110, 3)
    row = _one(pg_url, "compliance_trend", "snapshot_date = %s AND department = %s", (SNAPSHOT, "DOJ"))
    assert row["ediscovery_cases"] == 15
    assert _count(pg_url, "compliance_trend") == 1


# ── ingestion idempotency ───────────────────────────────────────────


def test_check_ingestion_duplicate_false_when_no_record(pg_url):
    assert check_ingestion_duplicate(TENANT_ID, SNAPSHOT, "abc123") is False


def test_record_ingestion_then_duplicate_detected(pg_url):
    counts = {"ediscovery_cases": 2, "dlp_alerts": 5}
    record_ingestion(TENANT_ID, SNAPSHOT, "abc123", counts)
    assert check_ingestion_duplicate(TENANT_ID, SNAPSHOT, "abc123") is True


def test_record_ingestion_different_hash_not_duplicate(pg_url):
    record_ingestion(TENANT_ID, SNAPSHOT, "abc123", {})
    assert check_ingestion_duplicate(TENANT_ID, SNAPSHOT, "xyz999") is False


def test_record_ingestion_idempotent_do_nothing(pg_url):
    record_ingestion(TENANT_ID, SNAPSHOT, "abc123", {"dlp_alerts": 3})
    record_ingestion(TENANT_ID, SNAPSHOT, "abc123", {"dlp_alerts": 3})
    assert _count(pg_url, "ingestion_log") == 1


# ── cross-tenant isolation ──────────────────────────────────────────


def test_tenants_are_isolated(pg_url):
    tenant_b = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    upsert_tenant(TENANT_ID, "Agency A", "DOJ")
    upsert_tenant(tenant_b, "Agency B", "FBI")
    upsert_ediscovery_case(TENANT_ID, "case-1", "Case One", "active", "2026-01-01", "", "", 3, SNAPSHOT)
    upsert_ediscovery_case(tenant_b, "case-2", "Case Two", "active", "2026-01-02", "", "", 1, SNAPSHOT)
    assert _count(pg_url, "ediscovery_cases") == 2
    row_a = _one(pg_url, "ediscovery_cases", "tenant_id = %s", (TENANT_ID,))
    assert row_a["case_id"] == "case-1"
    row_b = _one(pg_url, "ediscovery_cases", "tenant_id = %s", (tenant_b,))
    assert row_b["case_id"] == "case-2"
