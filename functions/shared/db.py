"""
PostgreSQL database client for the Compliance Advisor Function App.

Uses psycopg2 with a connection pool. Authenticates via DATABASE_URL
(connection string stored in Key Vault, referenced by Function App config).
"""

import logging
from contextlib import contextmanager
from typing import Any

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
    secure_score: float,
    max_score: float,
    active_user_count: int = 0,
    licensed_user_count: int = 0,
    controls_total: int = 0,
    controls_implemented: int = 0,
    collector_version: str = "",
) -> None:
    execute(
        """
        INSERT INTO posture_snapshots
            (tenant_id, snapshot_date, secure_score, max_score,
             active_user_count, licensed_user_count,
             controls_total, controls_implemented, collector_version)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, snapshot_date) DO UPDATE SET
            secure_score = EXCLUDED.secure_score,
            max_score = EXCLUDED.max_score,
            active_user_count = EXCLUDED.active_user_count,
            licensed_user_count = EXCLUDED.licensed_user_count,
            controls_total = EXCLUDED.controls_total,
            controls_implemented = EXCLUDED.controls_implemented,
            collector_version = EXCLUDED.collector_version
        """,
        (
            tenant_id, snapshot_date, secure_score, max_score,
            active_user_count, licensed_user_count,
            controls_total, controls_implemented, collector_version,
        ),
    )


def upsert_control_score(
    tenant_id: str,
    control_name: str,
    category: str,
    score: float,
    score_pct: float,
    implementation_status: str,
    last_synced: str,
    description: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO control_scores
            (tenant_id, control_name, category, score, score_pct,
             implementation_status, last_synced, description, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, control_name, snapshot_date) DO UPDATE SET
            category = EXCLUDED.category,
            score = EXCLUDED.score,
            score_pct = EXCLUDED.score_pct,
            implementation_status = EXCLUDED.implementation_status,
            last_synced = EXCLUDED.last_synced,
            description = EXCLUDED.description
        """,
        (
            tenant_id, control_name, category, score, score_pct,
            implementation_status, last_synced, description, snapshot_date,
        ),
    )


def upsert_control_profile(
    tenant_id: str,
    control_id: str,
    title: str,
    max_score: float,
    service: str,
    category: str,
    action_type: str,
    tier: str,
    implementation_cost: str,
    user_impact: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO control_profiles
            (tenant_id, control_id, title, max_score, service, category,
             action_type, tier, implementation_cost, user_impact, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, control_id, snapshot_date) DO UPDATE SET
            title = EXCLUDED.title,
            max_score = EXCLUDED.max_score,
            service = EXCLUDED.service,
            category = EXCLUDED.category,
            action_type = EXCLUDED.action_type,
            tier = EXCLUDED.tier,
            implementation_cost = EXCLUDED.implementation_cost,
            user_impact = EXCLUDED.user_impact
        """,
        (
            tenant_id, control_id, title, max_score, service, category,
            action_type, tier, implementation_cost, user_impact, snapshot_date,
        ),
    )


def upsert_security_alert(
    tenant_id: str,
    alert_id: str,
    title: str,
    severity: str,
    status: str,
    category: str,
    service_source: str,
    created: str,
    resolved: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO security_alerts
            (tenant_id, alert_id, title, severity, status, category,
             service_source, created, resolved, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, alert_id, snapshot_date) DO UPDATE SET
            title = EXCLUDED.title,
            severity = EXCLUDED.severity,
            status = EXCLUDED.status,
            category = EXCLUDED.category,
            service_source = EXCLUDED.service_source,
            created = EXCLUDED.created,
            resolved = EXCLUDED.resolved
        """,
        (
            tenant_id, alert_id, title, severity, status, category,
            service_source, created, resolved, snapshot_date,
        ),
    )


def upsert_security_incident(
    tenant_id: str,
    incident_id: str,
    display_name: str,
    severity: str,
    status: str,
    classification: str,
    created: str,
    last_update: str,
    assigned_to: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO security_incidents
            (tenant_id, incident_id, display_name, severity, status,
             classification, created, last_update, assigned_to, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, incident_id, snapshot_date) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            severity = EXCLUDED.severity,
            status = EXCLUDED.status,
            classification = EXCLUDED.classification,
            created = EXCLUDED.created,
            last_update = EXCLUDED.last_update,
            assigned_to = EXCLUDED.assigned_to
        """,
        (
            tenant_id, incident_id, display_name, severity, status,
            classification, created, last_update, assigned_to, snapshot_date,
        ),
    )


def upsert_risky_user(
    tenant_id: str,
    user_id: str,
    user_display_name: str,
    user_principal_name: str,
    risk_level: str,
    risk_state: str,
    risk_detail: str,
    risk_last_updated: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO risky_users
            (tenant_id, user_id, user_display_name, user_principal_name,
             risk_level, risk_state, risk_detail, risk_last_updated, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, user_id, snapshot_date) DO UPDATE SET
            user_display_name = EXCLUDED.user_display_name,
            user_principal_name = EXCLUDED.user_principal_name,
            risk_level = EXCLUDED.risk_level,
            risk_state = EXCLUDED.risk_state,
            risk_detail = EXCLUDED.risk_detail,
            risk_last_updated = EXCLUDED.risk_last_updated
        """,
        (
            tenant_id, user_id, user_display_name, user_principal_name,
            risk_level, risk_state, risk_detail, risk_last_updated, snapshot_date,
        ),
    )


def upsert_service_health(
    tenant_id: str,
    service_name: str,
    status: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO service_health (tenant_id, service_name, status, snapshot_date)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (tenant_id, service_name, snapshot_date) DO UPDATE SET
            status = EXCLUDED.status
        """,
        (tenant_id, service_name, status, snapshot_date),
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
            (snapshot_date, department, avg_score_pct, min_score_pct, max_score_pct, tenant_count)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (snapshot_date, department) DO UPDATE SET
            avg_score_pct = EXCLUDED.avg_score_pct,
            min_score_pct = EXCLUDED.min_score_pct,
            max_score_pct = EXCLUDED.max_score_pct,
            tenant_count = EXCLUDED.tenant_count
        """,
        (snapshot_date, department, avg_pct, min_pct, max_pct, tenant_count),
    )
