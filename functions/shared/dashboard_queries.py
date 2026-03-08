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
    row = query_one(
        """
        SELECT COUNT(DISTINCT tenant_id) AS active_tenants,
               MAX(snapshot_date)::text  AS newest_sync
        FROM posture_snapshots
        """
    )
    return {
        "active_tenants": row["active_tenants"] if row else 0,
        "newest_sync": row["newest_sync"] if row else None,
    }


def get_overview(department: str | None = None) -> dict:
    """POST /api/advisor/overview — top-level dashboard cards."""
    dept_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    # Latest snapshot per tenant
    tenants = query(
        f"""
        SELECT DISTINCT ON (ps.tenant_id)
            ps.tenant_id, t.display_name, t.department,
            ps.secure_score, ps.max_score, ps.score_pct,
            ps.active_user_count, ps.licensed_user_count,
            ps.controls_total, ps.controls_implemented,
            ps.snapshot_date::text
        FROM posture_snapshots ps
        JOIN tenants t ON t.tenant_id = ps.tenant_id
        WHERE 1=1 {dept_filter}
        ORDER BY ps.tenant_id, ps.snapshot_date DESC
        """,
        params,
    )

    # Alert summary
    alert_summary = query_one(
        f"""
        SELECT
            COUNT(*) FILTER (WHERE sa.severity = 'high')::int AS high_alerts,
            COUNT(*) FILTER (WHERE sa.severity = 'medium')::int AS medium_alerts,
            COUNT(*) FILTER (WHERE sa.severity = 'low')::int AS low_alerts,
            COUNT(*) FILTER (WHERE sa.status != 'resolved')::int AS active_alerts,
            COUNT(*)::int AS total_alerts
        FROM security_alerts sa
        JOIN tenants t ON t.tenant_id = sa.tenant_id
        WHERE sa.snapshot_date = (SELECT MAX(snapshot_date) FROM security_alerts)
          {dept_filter}
        """,
        params,
    )

    # Incident summary
    incident_summary = query_one(
        f"""
        SELECT
            COUNT(*)::int AS total_incidents,
            COUNT(*) FILTER (WHERE si.status = 'active')::int AS active_incidents,
            COUNT(*) FILTER (WHERE si.severity = 'high')::int AS high_incidents
        FROM security_incidents si
        JOIN tenants t ON t.tenant_id = si.tenant_id
        WHERE si.snapshot_date = (SELECT MAX(snapshot_date) FROM security_incidents)
          {dept_filter}
        """,
        params,
    )

    # Risky user count
    risky_count = query_one(
        f"""
        SELECT COUNT(*)::int AS total_risky_users,
               COUNT(*) FILTER (WHERE ru.risk_level = 'high')::int AS high_risk_users
        FROM risky_users ru
        JOIN tenants t ON t.tenant_id = ru.tenant_id
        WHERE ru.snapshot_date = (SELECT MAX(snapshot_date) FROM risky_users)
          {dept_filter}
        """,
        params,
    )

    # Service health summary
    health_summary = query_one(
        f"""
        SELECT COUNT(*)::int AS total_services,
               COUNT(*) FILTER (WHERE sh.status = 'serviceOperational')::int AS healthy_services
        FROM service_health sh
        JOIN tenants t ON t.tenant_id = sh.tenant_id
        WHERE sh.snapshot_date = (SELECT MAX(snapshot_date) FROM service_health)
          {dept_filter}
        """,
        params,
    )

    return {
        "tenants": tenants,
        "alert_summary": alert_summary or {},
        "incident_summary": incident_summary or {},
        "risky_user_summary": risky_count or {},
        "service_health_summary": health_summary or {},
    }


def get_score_trend(department: str | None = None, days: int = 30) -> dict:
    """POST /api/advisor/score-trend — Secure Score over time."""
    params: dict = {"days": days}
    dept_filter = ""
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    cutoff = (date.today() - timedelta(days=days)).isoformat()

    # Per-tenant daily scores
    daily_scores = query(
        f"""
        SELECT ps.snapshot_date::text, t.display_name,
               ps.secure_score, ps.max_score, ps.score_pct
        FROM posture_snapshots ps
        JOIN tenants t ON t.tenant_id = ps.tenant_id
        WHERE ps.snapshot_date >= %(cutoff)s {dept_filter}
        ORDER BY ps.snapshot_date
        """,
        {**params, "cutoff": cutoff},
    )

    # Trend from compliance_trend table
    trend_filter = "WHERE ct.department IS NULL" if not department else "WHERE ct.department = %(dept)s"
    trend = query(
        f"""
        SELECT ct.snapshot_date::text, ct.avg_score_pct,
               ct.min_score_pct, ct.max_score_pct
        FROM compliance_trend ct
        {trend_filter}
          AND ct.snapshot_date >= %(cutoff)s
        ORDER BY ct.snapshot_date
        """,
        {**params, "cutoff": cutoff},
    )

    return {
        "daily_scores": daily_scores,
        "trend": trend,
    }


def get_controls(department: str | None = None) -> dict:
    """POST /api/advisor/controls — control scores and profiles."""
    dept_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    # Control scores
    scores = query(
        f"""
        SELECT cs.control_name, cs.category, cs.score, cs.score_pct,
               cs.implementation_status, cs.description,
               t.display_name
        FROM control_scores cs
        JOIN tenants t ON t.tenant_id = cs.tenant_id
        WHERE cs.snapshot_date = (SELECT MAX(snapshot_date) FROM control_scores)
          {dept_filter}
        ORDER BY cs.score_pct ASC
        """,
        params,
    )

    # Category rollup
    categories = query(
        f"""
        SELECT cs.category,
               COUNT(*)::int AS total_controls,
               COUNT(*) FILTER (WHERE cs.score_pct = 100)::int AS fully_implemented,
               COUNT(*) FILTER (WHERE cs.score_pct = 0)::int AS not_implemented,
               ROUND(AVG(cs.score_pct)::numeric, 1) AS avg_score_pct,
               SUM(cs.score)::real AS total_score
        FROM control_scores cs
        JOIN tenants t ON t.tenant_id = cs.tenant_id
        WHERE cs.snapshot_date = (SELECT MAX(snapshot_date) FROM control_scores)
          {dept_filter}
        GROUP BY cs.category
        ORDER BY avg_score_pct ASC
        """,
        params,
    )

    # Top improvement opportunities (not fully implemented, sorted by potential points)
    opportunities = query(
        f"""
        SELECT cp.title, cp.control_id, cp.service, cp.category,
               cp.max_score, cp.tier, cp.implementation_cost, cp.user_impact,
               cp.action_type, t.display_name
        FROM control_profiles cp
        JOIN tenants t ON t.tenant_id = cp.tenant_id
        LEFT JOIN control_scores cs
            ON cs.tenant_id = cp.tenant_id
            AND cs.control_name = cp.control_id
            AND cs.snapshot_date = cp.snapshot_date
        WHERE cp.snapshot_date = (SELECT MAX(snapshot_date) FROM control_profiles)
          AND (cs.score_pct IS NULL OR cs.score_pct < 100)
          {dept_filter}
        ORDER BY cp.max_score DESC
        LIMIT 25
        """,
        params,
    )

    return {
        "control_scores": scores,
        "categories": categories,
        "opportunities": opportunities,
    }


def get_alerts(department: str | None = None) -> dict:
    """POST /api/advisor/alerts — security alerts."""
    dept_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    alerts = query(
        f"""
        SELECT sa.alert_id, sa.title, sa.severity, sa.status,
               sa.category, sa.service_source, sa.created, sa.resolved,
               t.display_name
        FROM security_alerts sa
        JOIN tenants t ON t.tenant_id = sa.tenant_id
        WHERE sa.snapshot_date = (SELECT MAX(snapshot_date) FROM security_alerts)
          {dept_filter}
        ORDER BY
            CASE sa.severity
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END,
            sa.created DESC
        """,
        params,
    )

    # Severity breakdown
    severity_breakdown = query(
        f"""
        SELECT sa.severity,
               COUNT(*)::int AS total,
               COUNT(*) FILTER (WHERE sa.status != 'resolved')::int AS active
        FROM security_alerts sa
        JOIN tenants t ON t.tenant_id = sa.tenant_id
        WHERE sa.snapshot_date = (SELECT MAX(snapshot_date) FROM security_alerts)
          {dept_filter}
        GROUP BY sa.severity
        ORDER BY
            CASE sa.severity
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END
        """,
        params,
    )

    return {
        "alerts": alerts,
        "severity_breakdown": severity_breakdown,
    }


def get_security(department: str | None = None) -> dict:
    """POST /api/advisor/security — incidents and risky users."""
    dept_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    incidents = query(
        f"""
        SELECT si.incident_id, si.display_name, si.severity, si.status,
               si.classification, si.created, si.last_update, si.assigned_to,
               t.display_name AS tenant_name
        FROM security_incidents si
        JOIN tenants t ON t.tenant_id = si.tenant_id
        WHERE si.snapshot_date = (SELECT MAX(snapshot_date) FROM security_incidents)
          {dept_filter}
        ORDER BY
            CASE si.severity
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END,
            si.created DESC
        """,
        params,
    )

    risky_users = query(
        f"""
        SELECT ru.user_display_name, ru.user_principal_name,
               ru.risk_level, ru.risk_state, ru.risk_detail,
               ru.risk_last_updated, t.display_name AS tenant_name
        FROM risky_users ru
        JOIN tenants t ON t.tenant_id = ru.tenant_id
        WHERE ru.snapshot_date = (SELECT MAX(snapshot_date) FROM risky_users)
          {dept_filter}
        ORDER BY
            CASE ru.risk_level
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END
        """,
        params,
    )

    return {
        "incidents": incidents,
        "risky_users": risky_users,
    }


def get_service_health(department: str | None = None) -> dict:
    """POST /api/advisor/service-health — M365 service health."""
    dept_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    services = query(
        f"""
        SELECT sh.service_name, sh.status, t.display_name
        FROM service_health sh
        JOIN tenants t ON t.tenant_id = sh.tenant_id
        WHERE sh.snapshot_date = (SELECT MAX(snapshot_date) FROM service_health)
          {dept_filter}
        ORDER BY
            CASE sh.status
                WHEN 'serviceOperational' THEN 2
                ELSE 1
            END,
            sh.service_name
        """,
        params,
    )

    return {"services": services}
