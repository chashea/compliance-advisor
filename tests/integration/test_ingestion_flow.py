"""End-to-end ingestion flow integration tests."""

import pytest
from psycopg2.extras import RealDictCursor
from shared.dashboard_queries import get_overview, get_status
from shared.db import (
    check_ingestion_duplicate,
    record_ingestion,
    upsert_dlp_alert,
    upsert_sensitivity_label,
    upsert_tenant,
)

pytestmark = pytest.mark.integration


class TestIngestionFlow:
    def test_full_ingest_then_query(self, db_conn):
        """Register tenant, ingest data, verify queryable via dashboard."""
        upsert_tenant("t-flow", "Flow Tenant", "IT", "Medium", status="collected")
        upsert_sensitivity_label(
            tenant_id="t-flow",
            label_id="sl-1",
            name="Confidential",
            description="",
            color="",
            is_active=True,
            parent_id="",
            priority=1,
            tooltip="",
            snapshot_date="2024-06-01",
            has_protection=True,
            applicable_to="",
            application_mode="",
            is_endpoint_protection_enabled=False,
        )
        upsert_dlp_alert(
            "t-flow",
            "dlp-1",
            "Flow Alert",
            "High",
            "New",
            "Cat",
            "Policy",
            "2024-06-01",
            "",
            "2024-06-01",
        )
        record_ingestion("t-flow", "2024-06-01", "flowhash", {"sensitivity_labels": 1, "dlp_alerts": 1})

        status = get_status()
        assert status["active_tenants"] >= 1

        overview = get_overview()
        assert overview["labels_summary"]["sensitivity_labels"] >= 1
        assert overview["dlp_summary"]["total_dlp_alerts"] >= 1

    def test_duplicate_ingestion_detected(self, db_conn):
        record_ingestion("t-dup", "2024-06-01", "hash123", {"cases": 1})
        assert check_ingestion_duplicate("t-dup", "2024-06-01", "hash123") is True
        assert check_ingestion_duplicate("t-dup", "2024-06-01", "hash456") is False

    def test_idempotent_upserts(self, db_conn):
        """Upserting same data twice should not create duplicates."""
        upsert_tenant("t-idem", "Idempotent", "IT", "Medium")
        kwargs = dict(
            tenant_id="t-idem",
            label_id="sl-1",
            name="Confidential",
            description="",
            color="",
            is_active=True,
            parent_id="",
            priority=1,
            tooltip="",
            snapshot_date="2024-06-01",
            has_protection=True,
            applicable_to="",
            application_mode="",
            is_endpoint_protection_enabled=False,
        )
        upsert_sensitivity_label(**kwargs)
        upsert_sensitivity_label(**{**kwargs, "name": "Confidential Updated"})

        with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM sensitivity_labels WHERE tenant_id = 't-idem'")
            assert cur.fetchone()["cnt"] == 1
