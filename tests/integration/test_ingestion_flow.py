"""End-to-end ingestion flow integration tests."""

import pytest
from psycopg2.extras import RealDictCursor
from shared.dashboard_queries import get_overview, get_status
from shared.db import (
    check_ingestion_duplicate,
    record_ingestion,
    upsert_dlp_alert,
    upsert_ediscovery_case,
    upsert_tenant,
)

pytestmark = pytest.mark.integration


class TestIngestionFlow:
    def test_full_ingest_then_query(self, db_conn):
        """Register tenant, ingest data, verify queryable via dashboard."""
        upsert_tenant("t-flow", "Flow Tenant", "IT", "Medium", status="collected")
        upsert_ediscovery_case(
            "t-flow", "case-1", "Flow Case", "active", "2024-01-01", "", "", 2, "2024-06-01",
        )
        upsert_dlp_alert(
            "t-flow", "dlp-1", "Flow Alert", "High", "New", "Cat", "Policy",
            "2024-06-01", "", "2024-06-01",
        )
        record_ingestion("t-flow", "2024-06-01", "flowhash", {"cases": 1, "dlp_alerts": 1})

        status = get_status()
        assert status["active_tenants"] >= 1

        overview = get_overview()
        assert overview["ediscovery_summary"]["total_cases"] >= 1
        assert overview["dlp_summary"]["total_dlp_alerts"] >= 1

    def test_duplicate_ingestion_detected(self, db_conn):
        record_ingestion("t-dup", "2024-06-01", "hash123", {"cases": 1})
        assert check_ingestion_duplicate("t-dup", "2024-06-01", "hash123") is True
        assert check_ingestion_duplicate("t-dup", "2024-06-01", "hash456") is False

    def test_idempotent_upserts(self, db_conn):
        """Upserting same data twice should not create duplicates."""
        upsert_tenant("t-idem", "Idempotent", "IT", "Medium")
        upsert_ediscovery_case("t-idem", "case-1", "Case", "Active", "2024-01-01", "", "", 1, "2024-06-01")
        upsert_ediscovery_case("t-idem", "case-1", "Case Updated", "Active", "2024-01-01", "", "", 2, "2024-06-01")

        with db_conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as cnt FROM ediscovery_cases WHERE tenant_id = 't-idem'")
            assert cur.fetchone()["cnt"] == 1
