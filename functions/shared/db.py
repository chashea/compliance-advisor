"""
PostgreSQL database client for the Compliance Advisor Function App.

Uses psycopg2 with a connection pool. Authenticates via DATABASE_URL
(connection string stored in Key Vault, referenced by Function App config).
"""

import logging
from contextlib import contextmanager
from typing import Any

from psycopg2.extras import Json, RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from shared.config import get_settings

log = logging.getLogger(__name__)

_pool: ThreadedConnectionPool | None = None


def _get_pool() -> ThreadedConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        dsn = settings.DATABASE_URL
        if dsn.startswith("@Microsoft.KeyVault("):
            log.warning("DATABASE_URL still contains unresolved Key Vault reference — resolving via KEY_VAULT_URL")
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            client = SecretClient(vault_url=settings.KEY_VAULT_URL, credential=DefaultAzureCredential())
            dsn = client.get_secret("database-url").value
        _pool = ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=dsn,
            connect_timeout=10,
            options="-c statement_timeout=30000",
        )
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


# ── Ingestion Idempotency ──────────────────────────────────────────


def check_ingestion_duplicate(tenant_id: str, snapshot_date: str, payload_hash: str) -> bool:
    row = query_one(
        "SELECT 1 FROM ingestion_log WHERE tenant_id = %s AND snapshot_date = %s AND payload_hash = %s",
        (tenant_id, snapshot_date, payload_hash),
    )
    return row is not None


def record_ingestion(tenant_id: str, snapshot_date: str, payload_hash: str, counts: dict) -> None:
    execute(
        """
        INSERT INTO ingestion_log (tenant_id, snapshot_date, payload_hash, record_counts)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (tenant_id, snapshot_date, payload_hash) DO NOTHING
        """,
        (tenant_id, snapshot_date, payload_hash, Json(counts)),
    )


# ── Write Operations ───────────────────────────────────────────────


def upsert_tenant(
    tenant_id: str,
    display_name: str,
    department: str,
    risk_tier: str = "Medium",
    status: str | None = None,
) -> None:
    if status:
        execute(
            """
            INSERT INTO tenants (tenant_id, display_name, department, risk_tier, status)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (tenant_id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                department = EXCLUDED.department,
                risk_tier = EXCLUDED.risk_tier,
                status = EXCLUDED.status
            """,
            (tenant_id, display_name, department, risk_tier, status),
        )
    else:
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


def update_tenant_status(tenant_id: str, status: str) -> None:
    execute(
        """
        UPDATE tenants SET status = %s, collected_at = now()
        WHERE tenant_id = %s
        """,
        (status, tenant_id),
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
    ip_address: str = "",
    client_app: str = "",
    result_status: str = "",
) -> None:
    execute(
        """
        INSERT INTO audit_records
            (tenant_id, record_id, record_type, operation, service, user_id, created,
             ip_address, client_app, result_status, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, record_id, snapshot_date) DO UPDATE SET
            record_type = EXCLUDED.record_type,
            operation = EXCLUDED.operation,
            service = EXCLUDED.service,
            user_id = EXCLUDED.user_id,
            created = EXCLUDED.created,
            ip_address = EXCLUDED.ip_address,
            client_app = EXCLUDED.client_app,
            result_status = EXCLUDED.result_status
        """,
        (
            tenant_id,
            record_id,
            record_type,
            operation,
            service,
            user_id,
            created,
            ip_address,
            client_app,
            result_status,
            snapshot_date,
        ),
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
    description: str = "",
    assigned_to: str = "",
) -> None:
    execute(
        """
        INSERT INTO dlp_alerts
            (tenant_id, alert_id, title, severity, status, category,
             policy_name, created, resolved, description, assigned_to, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, alert_id, snapshot_date) DO UPDATE SET
            title = EXCLUDED.title,
            severity = EXCLUDED.severity,
            status = EXCLUDED.status,
            category = EXCLUDED.category,
            policy_name = EXCLUDED.policy_name,
            created = EXCLUDED.created,
            resolved = EXCLUDED.resolved,
            description = EXCLUDED.description,
            assigned_to = EXCLUDED.assigned_to
        """,
        (
            tenant_id,
            alert_id,
            title,
            severity,
            status,
            category,
            policy_name,
            created,
            resolved,
            description,
            assigned_to,
            snapshot_date,
        ),
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


def upsert_irm_alert(
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
    description: str = "",
    assigned_to: str = "",
) -> None:
    execute(
        """
        INSERT INTO irm_alerts
            (tenant_id, alert_id, title, severity, status, category,
             policy_name, created, resolved, description, assigned_to, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, alert_id, snapshot_date) DO UPDATE SET
            title = EXCLUDED.title,
            severity = EXCLUDED.severity,
            status = EXCLUDED.status,
            category = EXCLUDED.category,
            policy_name = EXCLUDED.policy_name,
            created = EXCLUDED.created,
            resolved = EXCLUDED.resolved,
            description = EXCLUDED.description,
            assigned_to = EXCLUDED.assigned_to
        """,
        (
            tenant_id,
            alert_id,
            title,
            severity,
            status,
            category,
            policy_name,
            created,
            resolved,
            description,
            assigned_to,
            snapshot_date,
        ),
    )


def upsert_subject_rights_request(
    tenant_id: str,
    request_id: str,
    display_name: str,
    request_type: str,
    status: str,
    created: str,
    closed: str,
    data_subject_type: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO subject_rights_requests
            (tenant_id, request_id, display_name, request_type, status,
             created, closed, data_subject_type, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, request_id, snapshot_date) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            request_type = EXCLUDED.request_type,
            status = EXCLUDED.status,
            created = EXCLUDED.created,
            closed = EXCLUDED.closed,
            data_subject_type = EXCLUDED.data_subject_type
        """,
        (tenant_id, request_id, display_name, request_type, status, created, closed, data_subject_type, snapshot_date),
    )


def upsert_comm_compliance_policy(
    tenant_id: str,
    policy_id: str,
    display_name: str,
    status: str,
    policy_type: str,
    review_pending_count: int,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO comm_compliance_policies
            (tenant_id, policy_id, display_name, status, policy_type,
             review_pending_count, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, policy_id, snapshot_date) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            status = EXCLUDED.status,
            policy_type = EXCLUDED.policy_type,
            review_pending_count = EXCLUDED.review_pending_count
        """,
        (tenant_id, policy_id, display_name, status, policy_type, review_pending_count, snapshot_date),
    )


def upsert_info_barrier_policy(
    tenant_id: str,
    policy_id: str,
    display_name: str,
    state: str,
    segments_applied: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO info_barrier_policies
            (tenant_id, policy_id, display_name, state, segments_applied, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, policy_id, snapshot_date) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            state = EXCLUDED.state,
            segments_applied = EXCLUDED.segments_applied
        """,
        (tenant_id, policy_id, display_name, state, segments_applied, snapshot_date),
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


def upsert_secure_score(
    tenant_id: str,
    current_score: float,
    max_score: float,
    score_date: str,
    snapshot_date: str,
    data_current_score: float = 0,
    data_max_score: float = 0,
) -> None:
    execute(
        """
        INSERT INTO secure_scores
            (tenant_id, current_score, max_score, score_date, snapshot_date,
             data_current_score, data_max_score)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, score_date, snapshot_date) DO UPDATE SET
            current_score = EXCLUDED.current_score,
            max_score = EXCLUDED.max_score,
            data_current_score = EXCLUDED.data_current_score,
            data_max_score = EXCLUDED.data_max_score
        """,
        (tenant_id, current_score, max_score, score_date, snapshot_date, data_current_score, data_max_score),
    )


def upsert_user_content_policies(tenant_id: str, records: list[dict], snapshot_date: str) -> int:
    if not records:
        return 0
    sql = """
        INSERT INTO user_content_policies
            (tenant_id, snapshot_date, user_id, user_upn, action, policy_id, policy_name,
             rule_id, rule_name, match_count)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, snapshot_date, user_id) DO UPDATE SET
            action = EXCLUDED.action,
            policy_id = EXCLUDED.policy_id,
            policy_name = EXCLUDED.policy_name,
            rule_id = EXCLUDED.rule_id,
            rule_name = EXCLUDED.rule_name,
            match_count = EXCLUDED.match_count
    """
    params = [
        (
            tenant_id,
            snapshot_date,
            r["user_id"],
            r["user_upn"],
            r.get("action", ""),
            r.get("policy_id", ""),
            r.get("policy_name", ""),
            r.get("rule_id", ""),
            r.get("rule_name", ""),
            r.get("match_count", 0),
        )
        for r in records
    ]
    execute_many(sql, params)
    return len(params)


def upsert_dlp_policy(
    tenant_id: str,
    policy_id: str,
    display_name: str,
    status: str,
    policy_type: str,
    rules_count: int,
    created: str,
    modified: str,
    mode: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO dlp_policies
            (tenant_id, policy_id, display_name, status, policy_type,
             rules_count, created, modified, mode, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, policy_id, snapshot_date) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            status = EXCLUDED.status,
            policy_type = EXCLUDED.policy_type,
            rules_count = EXCLUDED.rules_count,
            created = EXCLUDED.created,
            modified = EXCLUDED.modified,
            mode = EXCLUDED.mode
        """,
        (tenant_id, policy_id, display_name, status, policy_type, rules_count, created, modified, mode, snapshot_date),
    )


def upsert_irm_policy(
    tenant_id: str,
    policy_id: str,
    display_name: str,
    status: str,
    policy_type: str,
    created: str,
    triggers: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO irm_policies
            (tenant_id, policy_id, display_name, status, policy_type, created, triggers, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, policy_id, snapshot_date) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            status = EXCLUDED.status,
            policy_type = EXCLUDED.policy_type,
            created = EXCLUDED.created,
            triggers = EXCLUDED.triggers
        """,
        (tenant_id, policy_id, display_name, status, policy_type, created, triggers, snapshot_date),
    )


def upsert_sensitive_info_type(
    tenant_id: str,
    type_id: str,
    name: str,
    description: str,
    is_custom: bool,
    category: str,
    scope: str,
    state: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO sensitive_info_types
            (tenant_id, type_id, name, description, is_custom, category, scope, state, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, type_id, snapshot_date) DO UPDATE SET
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            is_custom = EXCLUDED.is_custom,
            category = EXCLUDED.category,
            scope = EXCLUDED.scope,
            state = EXCLUDED.state
        """,
        (tenant_id, type_id, name, description, is_custom, category, scope, state, snapshot_date),
    )


def upsert_compliance_assessment(
    tenant_id: str,
    assessment_id: str,
    display_name: str,
    status: str,
    framework: str,
    completion_percentage: float,
    created: str,
    category: str,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO compliance_assessments
            (tenant_id, assessment_id, display_name, status, framework,
             completion_percentage, created, category, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, assessment_id, snapshot_date) DO UPDATE SET
            display_name = EXCLUDED.display_name,
            status = EXCLUDED.status,
            framework = EXCLUDED.framework,
            completion_percentage = EXCLUDED.completion_percentage,
            created = EXCLUDED.created,
            category = EXCLUDED.category
        """,
        (
            tenant_id,
            assessment_id,
            display_name,
            status,
            framework,
            completion_percentage,
            created,
            category,
            snapshot_date,
        ),
    )


def upsert_improvement_action(
    tenant_id: str,
    control_id: str,
    title: str,
    control_category: str,
    max_score: float,
    current_score: float,
    implementation_cost: str,
    user_impact: str,
    tier: str,
    service: str,
    threats: str,
    remediation: str,
    state: str,
    deprecated: bool,
    rank: int,
    snapshot_date: str,
) -> None:
    execute(
        """
        INSERT INTO improvement_actions
            (tenant_id, control_id, title, control_category, max_score, current_score,
             implementation_cost, user_impact, tier, service, threats, remediation,
             state, deprecated, rank, snapshot_date)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (tenant_id, control_id, snapshot_date) DO UPDATE SET
            title = EXCLUDED.title,
            control_category = EXCLUDED.control_category,
            max_score = EXCLUDED.max_score,
            current_score = EXCLUDED.current_score,
            implementation_cost = EXCLUDED.implementation_cost,
            user_impact = EXCLUDED.user_impact,
            tier = EXCLUDED.tier,
            service = EXCLUDED.service,
            threats = EXCLUDED.threats,
            remediation = EXCLUDED.remediation,
            state = EXCLUDED.state,
            deprecated = EXCLUDED.deprecated,
            rank = EXCLUDED.rank
        """,
        (
            tenant_id,
            control_id,
            title,
            control_category,
            max_score,
            current_score,
            implementation_cost,
            user_impact,
            tier,
            service,
            threats,
            remediation,
            state,
            deprecated,
            rank,
            snapshot_date,
        ),
    )
