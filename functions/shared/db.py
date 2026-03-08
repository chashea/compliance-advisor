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


def upsert_tenant(tenant_id: str, display_name: str, department: str, risk_tier: str = "Medium") -> None:
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


def upsert_ediscovery_case(
    tenant_id: str,
    case_id: str,
    display_name: str,
    status: str,
    created: str,
    closed: str,
    external_id: str,
    custodian_count: int,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO ediscovery_cases
            (tenant_id, case_id, display_name, status, created, closed,
             external_id, custodian_count, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, case_id, snapshot_date) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            status = EXCLUDED.status,
            created = EXCLUDED.created,
            closed = EXCLUDED.closed,
            external_id = EXCLUDED.external_id,
            custodian_count = EXCLUDED.custodian_count
        """,
        (tenant_id, case_id, display_name, status, created, closed, external_id, custodian_count, snapshot_date),
    )


def upsert_sensitivity_label(
    tenant_id: str,
    label_id: str,
    name: str,
    description: str,
    color: str,
    is_active: bool,
    parent_id: str,
    priority: int,
    tooltip: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO sensitivity_labels
            (tenant_id, label_id, name, description, color, is_active,
             parent_id, priority, tooltip, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, label_id, snapshot_date) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            color = EXCLUDED.color,
            is_active = EXCLUDED.is_active,
            parent_id = EXCLUDED.parent_id,
            priority = EXCLUDED.priority,
            tooltip = EXCLUDED.tooltip
        """,
        (tenant_id, label_id, name, description, color, is_active, parent_id, priority, tooltip, snapshot_date),
    )


def upsert_retention_label(
    tenant_id: str,
    label_id: str,
    display_name: str,
    retention_duration: str,
    retention_trigger: str,
    action_after_retention: str,
    is_in_use: bool,
    status: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO retention_labels
            (tenant_id, label_id, display_name, retention_duration, retention_trigger,
             action_after_retention, is_in_use, status, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, label_id, snapshot_date) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            retention_duration = EXCLUDED.retention_duration,
            retention_trigger = EXCLUDED.retention_trigger,
            action_after_retention = EXCLUDED.action_after_retention,
            is_in_use = EXCLUDED.is_in_use,
            status = EXCLUDED.status
        """,
        (
            tenant_id,
            label_id,
            display_name,
            retention_duration,
            retention_trigger,
            action_after_retention,
            is_in_use,
            status,
            snapshot_date,
        ),
    )


def upsert_retention_event(
    tenant_id: str,
    event_id: str,
    display_name: str,
    event_type: str,
    created: str,
    event_status: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO retention_events
            (tenant_id, event_id, display_name, event_type, created, event_status, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, event_id, snapshot_date) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            event_type = EXCLUDED.event_type,
            created = EXCLUDED.created,
            event_status = EXCLUDED.event_status
        """,
        (tenant_id, event_id, display_name, event_type, created, event_status, snapshot_date),
    )


def upsert_audit_record(
    tenant_id: str,
    record_id: str,
    record_type: str,
    operation: str,
    service: str,
    user_id: str,
    created: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO audit_records
            (tenant_id, record_id, record_type, operation, service, user_id, created, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, record_id, snapshot_date) DO UPDATE SET
            record_type = EXCLUDED.record_type,
            operation = EXCLUDED.operation,
            service = EXCLUDED.service,
            user_id = EXCLUDED.user_id,
            created = EXCLUDED.created
        """,
        (tenant_id, record_id, record_type, operation, service, user_id, created, snapshot_date),
    )


def upsert_dlp_alert(
    tenant_id: str,
    alert_id: str,
    title: str,
    severity: str,
    status: str,
    category: str,
    policy_name: str,
    created: str,
    resolved: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO dlp_alerts
            (tenant_id, alert_id, title, severity, status, category,
             policy_name, created, resolved, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, alert_id, snapshot_date) DO UPDATE SET
            title = EXCLUDED.title,
            severity = EXCLUDED.severity,
            status = EXCLUDED.status,
            category = EXCLUDED.category,
            policy_name = EXCLUDED.policy_name,
            created = EXCLUDED.created,
            resolved = EXCLUDED.resolved
        """,
        (tenant_id, alert_id, title, severity, status, category, policy_name, created, resolved, snapshot_date),
    )


def upsert_protection_scope(
    tenant_id: str,
    scope_type: str,
    execution_mode: str,
    locations: str,
    activity_types: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO protection_scopes
            (tenant_id, scope_type, execution_mode, locations, activity_types, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, scope_type, snapshot_date) DO UPDATE SET
            execution_mode = EXCLUDED.execution_mode,
            locations = EXCLUDED.locations,
            activity_types = EXCLUDED.activity_types
        """,
        (tenant_id, scope_type, execution_mode, locations, activity_types, snapshot_date),
    )


def upsert_trend(
    snapshot_date: str,
    department: str | None,
    ediscovery_cases: int,
    sensitivity_labels: int,
    retention_labels: int,
    dlp_alerts: int,
    audit_records: int,
    tenant_count: int,
) -> None:
    execute(
        """
        INSERT INTO compliance_trend
            (snapshot_date, department, ediscovery_cases, sensitivity_labels,
             retention_labels, dlp_alerts, audit_records, tenant_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (snapshot_date, department) DO UPDATE SET
            ediscovery_cases = EXCLUDED.ediscovery_cases,
            sensitivity_labels = EXCLUDED.sensitivity_labels,
            retention_labels = EXCLUDED.retention_labels,
            dlp_alerts = EXCLUDED.dlp_alerts,
            audit_records = EXCLUDED.audit_records,
            tenant_count = EXCLUDED.tenant_count
        """,
        (
            snapshot_date,
            department,
            ediscovery_cases,
            sensitivity_labels,
            retention_labels,
            dlp_alerts,
            audit_records,
            tenant_count,
        ),
    )
