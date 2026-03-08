"""
Dashboard query layer — translates PostgreSQL data into the JSON shapes
expected by the dashboard frontend (app.js).

Each function returns a dict matching exactly what the corresponding
POST /api/advisor/* endpoint should return.
"""

import logging
from datetime import date, timedelta

from shared.db import query, query_one

log = logging.getLogger(__name__)


def get_status() -> dict:
    """POST /api/advisor/status — basic health check."""
    row = query_one("""
        SELECT COUNT(DISTINCT tenant_id)::int AS active_tenants,
               MAX(created_at)::text AS newest_sync
        FROM tenants
        """)
    return {
        "active_tenants": row["active_tenants"] if row else 0,
        "newest_sync": row["newest_sync"] if row else None,
    }


def get_overview(department: str | None = None) -> dict:
    """POST /api/advisor/overview — top-level dashboard cards."""
    dept_filter = ""
    params: dict = {}
    if department:
        dept_filter = "WHERE t.department = %(dept)s"
        params["dept"] = department

    # Tenants
    tenants = query(
        f"""
        SELECT t.tenant_id, t.display_name, t.department
        FROM tenants t
        {dept_filter}
        ORDER BY t.display_name
        """,
        params,
    )

    and_dept = "AND t.department = %(dept)s" if department else ""

    # eDiscovery summary
    ediscovery_summary = query_one(
        f"""
        SELECT COUNT(*)::int AS total_cases,
               COUNT(*) FILTER (WHERE ec.status = 'active')::int AS active_cases
        FROM ediscovery_cases ec
        JOIN tenants t ON t.tenant_id = ec.tenant_id
        WHERE ec.snapshot_date = (SELECT MAX(snapshot_date) FROM ediscovery_cases)
          {and_dept}
        """,
        params,
    )

    # Labels summary
    labels_summary = query_one(
        f"""
        SELECT
            (SELECT COUNT(*)::int FROM sensitivity_labels sl
             JOIN tenants t ON t.tenant_id = sl.tenant_id
             WHERE sl.snapshot_date = (SELECT MAX(snapshot_date) FROM sensitivity_labels)
               {and_dept}) AS sensitivity_labels,
            (SELECT COUNT(*)::int FROM retention_labels rl
             JOIN tenants t ON t.tenant_id = rl.tenant_id
             WHERE rl.snapshot_date = (SELECT MAX(snapshot_date) FROM retention_labels)
               {and_dept}) AS retention_labels
        """,
        params,
    )

    # DLP alert summary
    dlp_summary = query_one(
        f"""
        SELECT
            COUNT(*)::int AS total_dlp_alerts,
            COUNT(*) FILTER (WHERE da.severity = 'high')::int AS high_alerts,
            COUNT(*) FILTER (WHERE da.severity = 'medium')::int AS medium_alerts,
            COUNT(*) FILTER (WHERE da.status != 'resolved')::int AS active_alerts
        FROM dlp_alerts da
        JOIN tenants t ON t.tenant_id = da.tenant_id
        WHERE da.snapshot_date = (SELECT MAX(snapshot_date) FROM dlp_alerts)
          {and_dept}
        """,
        params,
    )

    # Audit record summary
    audit_summary = query_one(
        f"""
        SELECT COUNT(*)::int AS total_records
        FROM audit_records ar
        JOIN tenants t ON t.tenant_id = ar.tenant_id
        WHERE ar.snapshot_date = (SELECT MAX(snapshot_date) FROM audit_records)
          {and_dept}
        """,
        params,
    )

    return {
        "tenants": tenants,
        "ediscovery_summary": ediscovery_summary or {},
        "labels_summary": labels_summary or {},
        "dlp_summary": dlp_summary or {},
        "audit_summary": audit_summary or {},
    }


def get_ediscovery(department: str | None = None) -> dict:
    """POST /api/advisor/ediscovery — eDiscovery cases."""
    dept_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    cases = query(
        f"""
        SELECT ec.case_id, ec.display_name, ec.status, ec.created, ec.closed,
               ec.external_id, ec.custodian_count, t.display_name AS tenant_name
        FROM ediscovery_cases ec
        JOIN tenants t ON t.tenant_id = ec.tenant_id
        WHERE ec.snapshot_date = (SELECT MAX(snapshot_date) FROM ediscovery_cases)
          {dept_filter}
        ORDER BY ec.created DESC
        """,
        params,
    )

    status_breakdown = query(
        f"""
        SELECT ec.status, COUNT(*)::int AS total
        FROM ediscovery_cases ec
        JOIN tenants t ON t.tenant_id = ec.tenant_id
        WHERE ec.snapshot_date = (SELECT MAX(snapshot_date) FROM ediscovery_cases)
          {dept_filter}
        GROUP BY ec.status
        ORDER BY total DESC
        """,
        params,
    )

    return {"cases": cases, "status_breakdown": status_breakdown}


def get_labels(department: str | None = None) -> dict:
    """POST /api/advisor/labels — sensitivity + retention labels."""
    dept_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    sensitivity = query(
        f"""
        SELECT sl.label_id, sl.name, sl.description, sl.color, sl.is_active,
               sl.parent_id, sl.priority, sl.tooltip, t.display_name AS tenant_name
        FROM sensitivity_labels sl
        JOIN tenants t ON t.tenant_id = sl.tenant_id
        WHERE sl.snapshot_date = (SELECT MAX(snapshot_date) FROM sensitivity_labels)
          {dept_filter}
        ORDER BY sl.priority
        """,
        params,
    )

    retention = query(
        f"""
        SELECT rl.label_id, rl.display_name, rl.retention_duration, rl.retention_trigger,
               rl.action_after_retention, rl.is_in_use, rl.status,
               t.display_name AS tenant_name
        FROM retention_labels rl
        JOIN tenants t ON t.tenant_id = rl.tenant_id
        WHERE rl.snapshot_date = (SELECT MAX(snapshot_date) FROM retention_labels)
          {dept_filter}
        ORDER BY rl.display_name
        """,
        params,
    )

    retention_events = query(
        f"""
        SELECT re.event_id, re.display_name, re.event_type, re.created, re.event_status,
               t.display_name AS tenant_name
        FROM retention_events re
        JOIN tenants t ON t.tenant_id = re.tenant_id
        WHERE re.snapshot_date = (SELECT MAX(snapshot_date) FROM retention_events)
          {dept_filter}
        ORDER BY re.created DESC
        """,
        params,
    )

    return {
        "sensitivity_labels": sensitivity,
        "retention_labels": retention,
        "retention_events": retention_events,
    }


def get_audit(department: str | None = None) -> dict:
    """POST /api/advisor/audit — audit log records."""
    dept_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    records = query(
        f"""
        SELECT ar.record_id, ar.record_type, ar.operation, ar.service,
               ar.user_id, ar.created, t.display_name AS tenant_name
        FROM audit_records ar
        JOIN tenants t ON t.tenant_id = ar.tenant_id
        WHERE ar.snapshot_date = (SELECT MAX(snapshot_date) FROM audit_records)
          {dept_filter}
        ORDER BY ar.created DESC
        LIMIT 500
        """,
        params,
    )

    service_breakdown = query(
        f"""
        SELECT ar.service, COUNT(*)::int AS total
        FROM audit_records ar
        JOIN tenants t ON t.tenant_id = ar.tenant_id
        WHERE ar.snapshot_date = (SELECT MAX(snapshot_date) FROM audit_records)
          {dept_filter}
        GROUP BY ar.service
        ORDER BY total DESC
        """,
        params,
    )

    operation_breakdown = query(
        f"""
        SELECT ar.operation, COUNT(*)::int AS total
        FROM audit_records ar
        JOIN tenants t ON t.tenant_id = ar.tenant_id
        WHERE ar.snapshot_date = (SELECT MAX(snapshot_date) FROM audit_records)
          {dept_filter}
        GROUP BY ar.operation
        ORDER BY total DESC
        LIMIT 20
        """,
        params,
    )

    return {
        "records": records,
        "service_breakdown": service_breakdown,
        "operation_breakdown": operation_breakdown,
    }


def get_dlp(department: str | None = None) -> dict:
    """POST /api/advisor/dlp — DLP alerts."""
    dept_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    alerts = query(
        f"""
        SELECT da.alert_id, da.title, da.severity, da.status, da.category,
               da.policy_name, da.created, da.resolved,
               t.display_name AS tenant_name
        FROM dlp_alerts da
        JOIN tenants t ON t.tenant_id = da.tenant_id
        WHERE da.snapshot_date = (SELECT MAX(snapshot_date) FROM dlp_alerts)
          {dept_filter}
        ORDER BY
            CASE da.severity
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END,
            da.created DESC
        """,
        params,
    )

    severity_breakdown = query(
        f"""
        SELECT da.severity, COUNT(*)::int AS total,
               COUNT(*) FILTER (WHERE da.status != 'resolved')::int AS active
        FROM dlp_alerts da
        JOIN tenants t ON t.tenant_id = da.tenant_id
        WHERE da.snapshot_date = (SELECT MAX(snapshot_date) FROM dlp_alerts)
          {dept_filter}
        GROUP BY da.severity
        ORDER BY
            CASE da.severity
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END
        """,
        params,
    )

    policy_breakdown = query(
        f"""
        SELECT da.policy_name, COUNT(*)::int AS total
        FROM dlp_alerts da
        JOIN tenants t ON t.tenant_id = da.tenant_id
        WHERE da.snapshot_date = (SELECT MAX(snapshot_date) FROM dlp_alerts)
          AND da.policy_name != ''
          {dept_filter}
        GROUP BY da.policy_name
        ORDER BY total DESC
        LIMIT 20
        """,
        params,
    )

    return {
        "alerts": alerts,
        "severity_breakdown": severity_breakdown,
        "policy_breakdown": policy_breakdown,
    }


def get_governance(department: str | None = None) -> dict:
    """POST /api/advisor/governance — protection scopes."""
    dept_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    scopes = query(
        f"""
        SELECT ps.scope_type, ps.execution_mode, ps.locations, ps.activity_types,
               t.display_name AS tenant_name
        FROM protection_scopes ps
        JOIN tenants t ON t.tenant_id = ps.tenant_id
        WHERE ps.snapshot_date = (SELECT MAX(snapshot_date) FROM protection_scopes)
          {dept_filter}
        ORDER BY ps.scope_type
        """,
        params,
    )

    return {"scopes": scopes}


def get_trend(department: str | None = None, days: int = 30) -> dict:
    """POST /api/advisor/trend — compliance workload counts over time."""
    params: dict = {}
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    trend_filter = "WHERE ct.department IS NULL" if not department else "WHERE ct.department = %(dept)s"
    if department:
        params["dept"] = department

    trend = query(
        f"""
        SELECT ct.snapshot_date::text, ct.ediscovery_cases, ct.sensitivity_labels,
               ct.retention_labels, ct.dlp_alerts, ct.audit_records, ct.tenant_count
        FROM compliance_trend ct
        {trend_filter}
          AND ct.snapshot_date >= %(cutoff)s
        ORDER BY ct.snapshot_date
        """,
        {**params, "cutoff": cutoff},
    )

    return {"trend": trend}
