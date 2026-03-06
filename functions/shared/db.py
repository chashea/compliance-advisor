"""
PostgreSQL database client for the Compliance Advisor Function App.

Uses psycopg2 with a connection pool. Authenticates via DATABASE_URL
(connection string stored in Key Vault, referenced by Function App config).
"""

import logging
from contextlib import contextmanager
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from shared.config import get_settings

log = logging.getLogger(__name__)

_pool: ThreadedConnectionPool | None = None


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ThreadedConnectionPool(minconn=1, maxconn=10, dsn=settings.DATABASE_URL)
    return _pool


@contextmanager
def get_conn():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def query(sql: str, params: tuple | dict | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]


def query_one(sql: str, params: tuple | dict | None = None) -> dict[str, Any] | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple | dict | None = None) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)


def execute_many(sql: str, params_list: list[tuple]) -> None:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.executemany(sql, params_list)


# ── Write Operations ───────────────────────────────────────────────


def upsert_tenant(
    tenant_id: str, display_name: str, department: str, risk_tier: str = "Medium"
) -> None:
    execute(
        """
        INSERT INTO tenants (tenant_id, display_name, department, risk_tier)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (tenant_id) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            department = EXCLUDED.department,
            risk_tier = EXCLUDED.risk_tier
        """,
        (tenant_id, display_name, department, risk_tier),
    )


def upsert_snapshot(
    tenant_id: str,
    snapshot_date: str,
    compliance_score: float,
    max_score: float,
    collector_version: str = "",
) -> None:
    execute(
        """
        INSERT INTO posture_snapshots (tenant_id, snapshot_date, compliance_score, max_score, collector_version)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, snapshot_date) DO UPDATE SET
            compliance_score = EXCLUDED.compliance_score,
            max_score = EXCLUDED.max_score,
            collector_version = EXCLUDED.collector_version
        """,
        (tenant_id, snapshot_date, compliance_score, max_score, collector_version),
    )


def upsert_assessment(
    tenant_id: str,
    assessment_id: str,
    assessment_name: str,
    regulation: str,
    compliance_score: float,
    passed_controls: int,
    failed_controls: int,
    total_controls: int,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO assessments
            (tenant_id, assessment_id, assessment_name, regulation,
             compliance_score, passed_controls, failed_controls, total_controls, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, assessment_id, snapshot_date) DO UPDATE SET
            assessment_name = EXCLUDED.assessment_name,
            regulation = EXCLUDED.regulation,
            compliance_score = EXCLUDED.compliance_score,
            passed_controls = EXCLUDED.passed_controls,
            failed_controls = EXCLUDED.failed_controls,
            total_controls = EXCLUDED.total_controls
        """,
        (
            tenant_id, assessment_id, assessment_name, regulation,
            compliance_score, passed_controls, failed_controls, total_controls, snapshot_date,
        ),
    )


def upsert_action(
    tenant_id: str,
    action_id: str,
    control_name: str,
    control_family: str,
    regulation: str,
    implementation_status: str,
    test_status: str,
    action_category: str,
    is_mandatory: bool,
    point_value: int,
    owner: str,
    service: str,
    description: str,
    remediation_steps: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO improvement_actions
            (tenant_id, action_id, control_name, control_family, regulation,
             implementation_status, test_status, action_category, is_mandatory,
             point_value, owner, service, description, remediation_steps, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, action_id, snapshot_date) DO UPDATE SET
            control_name = EXCLUDED.control_name,
            control_family = EXCLUDED.control_family,
            regulation = EXCLUDED.regulation,
            implementation_status = EXCLUDED.implementation_status,
            test_status = EXCLUDED.test_status,
            action_category = EXCLUDED.action_category,
            is_mandatory = EXCLUDED.is_mandatory,
            point_value = EXCLUDED.point_value,
            owner = EXCLUDED.owner,
            service = EXCLUDED.service,
            description = EXCLUDED.description,
            remediation_steps = EXCLUDED.remediation_steps
        """,
        (
            tenant_id, action_id, control_name, control_family, regulation,
            implementation_status, test_status, action_category, is_mandatory,
            point_value, owner, service, description, remediation_steps, snapshot_date,
        ),
    )


def upsert_trend(
    snapshot_date: str,
    department: str | None,
    avg_pct: float,
    min_pct: float,
    max_pct: float,
    tenant_count: int,
) -> None:
    execute(
        """
        INSERT INTO compliance_trend
            (snapshot_date, department, avg_compliance_pct, min_compliance_pct, max_compliance_pct, tenant_count)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (snapshot_date, department) DO UPDATE SET
            avg_compliance_pct = EXCLUDED.avg_compliance_pct,
            min_compliance_pct = EXCLUDED.min_compliance_pct,
            max_compliance_pct = EXCLUDED.max_compliance_pct,
            tenant_count = EXCLUDED.tenant_count
        """,
        (snapshot_date, department, avg_pct, min_pct, max_pct, tenant_count),
    )
