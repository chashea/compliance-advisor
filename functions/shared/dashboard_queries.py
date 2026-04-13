"""
Dashboard query layer — translates PostgreSQL data into the JSON shapes
expected by the dashboard frontend (app.js).

Each function returns a dict matching exactly what the corresponding
POST /api/advisor/* endpoint should return.
"""

import json
import logging
from datetime import date, datetime, timedelta, timezone

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


def get_overview(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/overview — top-level dashboard cards."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "WHERE t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    where_clause = dept_filter
    if not where_clause and tenant_filter:
        where_clause = "WHERE 1=1 " + tenant_filter
    elif tenant_filter:
        where_clause += " " + tenant_filter

    # Tenants
    tenants = query(
        f"""
        SELECT t.tenant_id, t.display_name, t.department
        FROM tenants t
        {where_clause}
        ORDER BY t.display_name
        """,
        params,
    )

    and_dept = "AND t.department = %(dept)s" if department else ""
    and_tenant = "AND t.tenant_id = %(tenant_id)s" if tenant_id else ""

    # Labels summary
    labels_summary = query_one(
        f"""
        SELECT
            (SELECT COUNT(*)::int FROM sensitivity_labels sl
             JOIN tenants t ON t.tenant_id = sl.tenant_id
             WHERE sl.snapshot_date = (
                SELECT MAX(snapshot_date) FROM sensitivity_labels _sub
                WHERE _sub.tenant_id = sl.tenant_id
            )
               {and_dept} {and_tenant}) AS sensitivity_labels,
            (SELECT COUNT(*)::int FROM sensitivity_labels sl
             JOIN tenants t ON t.tenant_id = sl.tenant_id
             WHERE sl.snapshot_date = (
                SELECT MAX(snapshot_date) FROM sensitivity_labels _sub
                WHERE _sub.tenant_id = sl.tenant_id
            )
               AND sl.has_protection = TRUE
               {and_dept} {and_tenant}) AS protected_labels
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
        WHERE da.snapshot_date = (
                SELECT MAX(snapshot_date) FROM dlp_alerts _sub
                WHERE _sub.tenant_id = da.tenant_id
            )
          {and_dept}
          {and_tenant}
        """,
        params,
    )

    # Audit record summary
    audit_summary = query_one(
        f"""
        SELECT COUNT(*)::int AS total_records
        FROM audit_records ar
        JOIN tenants t ON t.tenant_id = ar.tenant_id
        WHERE ar.snapshot_date = (
                SELECT MAX(snapshot_date) FROM audit_records _sub
                WHERE _sub.tenant_id = ar.tenant_id
            )
          {and_dept}
          {and_tenant}
        """,
        params,
    )

    # Threat assessment summary
    threat_summary = query_one(
        f"""
        SELECT
            COUNT(*)::int AS total_requests,
            COUNT(*) FILTER (WHERE ta.category = 'spam')::int AS spam,
            COUNT(*) FILTER (WHERE ta.category = 'phishing')::int AS phishing,
            COUNT(*) FILTER (WHERE ta.category = 'malware')::int AS malware
        FROM threat_assessment_requests ta
        JOIN tenants t ON t.tenant_id = ta.tenant_id
        WHERE ta.snapshot_date = (
                SELECT MAX(snapshot_date) FROM threat_assessment_requests _sub
                WHERE _sub.tenant_id = ta.tenant_id
            )
          {and_dept}
          {and_tenant}
        """,
        params,
    )

    return {
        "tenants": tenants,
        "labels_summary": labels_summary or {},
        "dlp_summary": dlp_summary or {},
        "audit_summary": audit_summary or {},
        "threat_summary": threat_summary or {},
    }


def get_labels(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/labels — sensitivity + retention labels."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    sensitivity = query(
        f"""
        SELECT sl.label_id, sl.name, sl.description, sl.color, sl.is_active,
               sl.parent_id, sl.priority, sl.tooltip, sl.has_protection,
               sl.applicable_to, sl.application_mode,
               sl.is_endpoint_protection_enabled,
               t.display_name AS tenant_name
        FROM sensitivity_labels sl
        JOIN tenants t ON t.tenant_id = sl.tenant_id
        WHERE sl.snapshot_date = (
                SELECT MAX(snapshot_date) FROM sensitivity_labels _sub
                WHERE _sub.tenant_id = sl.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        ORDER BY sl.priority
        LIMIT 1000
        """,
        params,
    )

    retention_events = query(
        f"""
        SELECT re.event_id, re.display_name, re.event_type, re.created, re.event_status,
               t.display_name AS tenant_name
        FROM retention_events re
        JOIN tenants t ON t.tenant_id = re.tenant_id
        WHERE re.snapshot_date = (
                SELECT MAX(snapshot_date) FROM retention_events _sub
                WHERE _sub.tenant_id = re.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        ORDER BY re.created DESC
        LIMIT 1000
        """,
        params,
    )

    retention_labels = query(
        f"""
        SELECT rl.label_id, rl.name, rl.description, rl.is_in_use,
               rl.retention_duration, rl.action_after, rl.default_record_behavior,
               rl.created, rl.modified,
               t.display_name AS tenant_name
        FROM retention_labels rl
        JOIN tenants t ON t.tenant_id = rl.tenant_id
        WHERE rl.snapshot_date = (
                SELECT MAX(snapshot_date) FROM retention_labels _sub
                WHERE _sub.tenant_id = rl.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        ORDER BY rl.name
        LIMIT 1000
        """,
        params,
    )

    return {
        "sensitivity_labels": sensitivity,
        "retention_labels": retention_labels,
        "retention_events": retention_events,
    }


def get_audit(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/audit — audit log records."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    records = query(
        f"""
        SELECT ar.record_id, ar.record_type, ar.operation, ar.service,
               ar.user_id, ar.created, ar.ip_address, ar.client_app,
               ar.result_status, t.display_name AS tenant_name
        FROM audit_records ar
        JOIN tenants t ON t.tenant_id = ar.tenant_id
        WHERE ar.snapshot_date = (
                SELECT MAX(snapshot_date) FROM audit_records _sub
                WHERE _sub.tenant_id = ar.tenant_id
            )
          {dept_filter}
          {tenant_filter}
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
        WHERE ar.snapshot_date = (
                SELECT MAX(snapshot_date) FROM audit_records _sub
                WHERE _sub.tenant_id = ar.tenant_id
            )
          {dept_filter}
          {tenant_filter}
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
        WHERE ar.snapshot_date = (
                SELECT MAX(snapshot_date) FROM audit_records _sub
                WHERE _sub.tenant_id = ar.tenant_id
            )
          {dept_filter}
          {tenant_filter}
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


def _compute_evidence_summary(alerts: list[dict]) -> dict:
    """Compute evidence summary from alert rows that include an evidence JSONB column."""
    remediation_counts: dict[str, int] = {}
    verdict_counts: dict[str, int] = {}
    type_counts: dict[str, int] = {}
    total = 0

    for alert in alerts:
        evidence = alert.get("evidence") or []
        if isinstance(evidence, str):
            import json as _json

            try:
                evidence = _json.loads(evidence)
            except (ValueError, TypeError):
                evidence = []
        for e in evidence:
            total += 1
            rs = e.get("remediation_status", "") or ""
            if rs:
                remediation_counts[rs] = remediation_counts.get(rs, 0) + 1
            v = e.get("verdict", "") or ""
            if v:
                verdict_counts[v] = verdict_counts.get(v, 0) + 1
            et = e.get("type", "") or ""
            if et:
                type_counts[et] = type_counts.get(et, 0) + 1

    return {
        "remediation_breakdown": [{"status": k, "count": v} for k, v in remediation_counts.items()],
        "verdict_breakdown": [{"verdict": k, "count": v} for k, v in verdict_counts.items()],
        "evidence_type_breakdown": [{"type": k, "count": v} for k, v in type_counts.items()],
        "total_evidence_items": total,
    }


def _evidence_summary_sql(table: str, alias: str, dept_filter: str, tenant_filter: str) -> str:
    """Return SQL for evidence summary from a JSONB evidence column."""
    latest = f"SELECT MAX(snapshot_date) FROM {table} _sub WHERE _sub.tenant_id = {alias}.tenant_id"
    return f"""
        WITH latest_alerts AS (
            SELECT {alias}.evidence
            FROM {table} {alias}
            JOIN tenants t ON t.tenant_id = {alias}.tenant_id
            WHERE {alias}.snapshot_date = ({latest})
              {dept_filter}
              {tenant_filter}
        ),
        evidence_items AS (
            SELECT e->>'type' AS etype,
                   e->>'remediation_status' AS remediation_status,
                   e->>'verdict' AS verdict
            FROM latest_alerts, jsonb_array_elements(evidence) AS e
        )
        SELECT
            COALESCE(json_agg(DISTINCT jsonb_build_object('status', remediation_status, 'count', rem_cnt))
                     FILTER (WHERE remediation_status IS NOT NULL AND remediation_status != ''), '[]'::json)
                AS remediation_breakdown,
            COALESCE(json_agg(DISTINCT jsonb_build_object('verdict', verdict, 'count', verd_cnt))
                     FILTER (WHERE verdict IS NOT NULL AND verdict != ''), '[]'::json)
                AS verdict_breakdown,
            COALESCE(json_agg(DISTINCT jsonb_build_object('type', etype, 'count', type_cnt))
                     FILTER (WHERE etype IS NOT NULL AND etype != ''), '[]'::json)
                AS evidence_type_breakdown,
            COUNT(*)::int AS total_evidence_items
        FROM (
            SELECT remediation_status, verdict, etype,
                   COUNT(*) OVER (PARTITION BY remediation_status) AS rem_cnt,
                   COUNT(*) OVER (PARTITION BY verdict) AS verd_cnt,
                   COUNT(*) OVER (PARTITION BY etype) AS type_cnt
            FROM evidence_items
        ) sub
    """


def get_dlp(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/dlp — DLP alerts."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    alerts = query(
        f"""
        SELECT da.alert_id, da.title, da.severity, da.status, da.category,
               da.policy_name, da.created, da.resolved, da.description,
               da.assigned_to, da.classification, da.determination,
               da.recommended_actions, da.incident_id, da.mitre_techniques,
               da.evidence, t.display_name AS tenant_name
        FROM dlp_alerts da
        JOIN tenants t ON t.tenant_id = da.tenant_id
        WHERE da.snapshot_date = (
                SELECT MAX(snapshot_date) FROM dlp_alerts _sub
                WHERE _sub.tenant_id = da.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        ORDER BY
            CASE da.severity
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END,
            da.created DESC
        LIMIT 1000
        """,
        params,
    )

    severity_breakdown = query(
        f"""
        SELECT da.severity, COUNT(*)::int AS total,
               COUNT(*) FILTER (WHERE da.status != 'resolved')::int AS active
        FROM dlp_alerts da
        JOIN tenants t ON t.tenant_id = da.tenant_id
        WHERE da.snapshot_date = (
                SELECT MAX(snapshot_date) FROM dlp_alerts _sub
                WHERE _sub.tenant_id = da.tenant_id
            )
          {dept_filter}
          {tenant_filter}
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
        WHERE da.snapshot_date = (
                SELECT MAX(snapshot_date) FROM dlp_alerts _sub
                WHERE _sub.tenant_id = da.tenant_id
            )
          AND da.policy_name != ''
          {dept_filter}
          {tenant_filter}
        GROUP BY da.policy_name
        ORDER BY total DESC
        LIMIT 20
        """,
        params,
    )

    classification_breakdown = query(
        f"""
        SELECT da.classification, COUNT(*)::int AS count
        FROM dlp_alerts da
        JOIN tenants t ON t.tenant_id = da.tenant_id
        WHERE da.snapshot_date = (
                SELECT MAX(snapshot_date) FROM dlp_alerts _sub
                WHERE _sub.tenant_id = da.tenant_id
            )
          AND da.classification != ''
          {dept_filter}
          {tenant_filter}
        GROUP BY da.classification
        ORDER BY count DESC
        """,
        params,
    )

    evidence_summary = _compute_evidence_summary(alerts)

    return {
        "alerts": alerts,
        "severity_breakdown": severity_breakdown,
        "policy_breakdown": policy_breakdown,
        "evidence_summary": evidence_summary,
        "classification_breakdown": classification_breakdown,
    }


def get_governance(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/governance — protection scopes."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    scopes = query(
        f"""
        SELECT ps.scope_type, ps.execution_mode, ps.locations, ps.activity_types,
               t.display_name AS tenant_name
        FROM protection_scopes ps
        JOIN tenants t ON t.tenant_id = ps.tenant_id
        WHERE ps.snapshot_date = (
                SELECT MAX(snapshot_date) FROM protection_scopes _sub
                WHERE _sub.tenant_id = ps.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        ORDER BY ps.scope_type
        LIMIT 1000
        """,
        params,
    )

    return {"scopes": scopes}


def get_trend(department: str | None = None, days: int = 30, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/trend — compliance workload counts over time."""
    params: dict = {}
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    trend_filter = "WHERE ct.department IS NULL" if not department else "WHERE ct.department = %(dept)s"
    if department:
        params["dept"] = department

    trend = query(
        f"""
        SELECT
            ct.snapshot_date::text,
            COALESCE((to_jsonb(ct) ->> 'sensitivity_labels')::int, (to_jsonb(ct) ->> 'sensitivity')::int, 0)
                AS sensitivity_labels,
            COALESCE((to_jsonb(ct) ->> 'dlp_alerts')::int, (to_jsonb(ct) ->> 'dlp')::int, 0) AS dlp_alerts,
            COALESCE((to_jsonb(ct) ->> 'audit_records')::int, (to_jsonb(ct) ->> 'audit')::int, 0) AS audit_records,
            COALESCE((to_jsonb(ct) ->> 'tenant_count')::int, (to_jsonb(ct) ->> 'tenants')::int, 0) AS tenant_count
        FROM compliance_trend ct
        {trend_filter}
          AND ct.snapshot_date >= %(cutoff)s
        ORDER BY ct.snapshot_date
        """,
        {**params, "cutoff": cutoff},
    )

    return {"trend": trend}


def get_irm(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/irm — Insider Risk Management alerts."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    alerts = query(
        f"""
        SELECT ia.alert_id, ia.title, ia.severity, ia.status, ia.category,
               ia.policy_name, ia.created, ia.resolved, ia.description,
               ia.assigned_to, ia.classification, ia.determination,
               ia.recommended_actions, ia.incident_id, ia.mitre_techniques,
               ia.evidence, t.display_name AS tenant_name
        FROM irm_alerts ia
        JOIN tenants t ON t.tenant_id = ia.tenant_id
        WHERE ia.snapshot_date = (
                SELECT MAX(snapshot_date) FROM irm_alerts _sub
                WHERE _sub.tenant_id = ia.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        ORDER BY
            CASE ia.severity
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END,
            ia.created DESC
        LIMIT 1000
        """,
        params,
    )

    severity_breakdown = query(
        f"""
        SELECT ia.severity, COUNT(*)::int AS total,
               COUNT(*) FILTER (WHERE ia.status != 'resolved')::int AS active
        FROM irm_alerts ia
        JOIN tenants t ON t.tenant_id = ia.tenant_id
        WHERE ia.snapshot_date = (
                SELECT MAX(snapshot_date) FROM irm_alerts _sub
                WHERE _sub.tenant_id = ia.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        GROUP BY ia.severity
        ORDER BY
            CASE ia.severity
                WHEN 'high' THEN 1
                WHEN 'medium' THEN 2
                WHEN 'low' THEN 3
                ELSE 4
            END
        """,
        params,
    )

    classification_breakdown = query(
        f"""
        SELECT ia.classification, COUNT(*)::int AS count
        FROM irm_alerts ia
        JOIN tenants t ON t.tenant_id = ia.tenant_id
        WHERE ia.snapshot_date = (
                SELECT MAX(snapshot_date) FROM irm_alerts _sub
                WHERE _sub.tenant_id = ia.tenant_id
            )
          AND ia.classification != ''
          {dept_filter}
          {tenant_filter}
        GROUP BY ia.classification
        ORDER BY count DESC
        """,
        params,
    )

    evidence_summary = _compute_evidence_summary(alerts)

    return {
        "alerts": alerts,
        "severity_breakdown": severity_breakdown,
        "evidence_summary": evidence_summary,
        "classification_breakdown": classification_breakdown,
    }




def get_info_barriers(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/info-barriers — Information Barrier policies."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    policies = query(
        f"""
        SELECT ib.policy_id, ib.display_name, ib.state, ib.segments_applied,
               t.display_name AS tenant_name
        FROM info_barrier_policies ib
        JOIN tenants t ON t.tenant_id = ib.tenant_id
        WHERE ib.snapshot_date = (
                SELECT MAX(snapshot_date) FROM info_barrier_policies _sub
                WHERE _sub.tenant_id = ib.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        ORDER BY ib.display_name
        LIMIT 1000
        """,
        params,
    )

    return {"policies": policies}


def get_dlp_policies(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/dlp-policies — DLP policies."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    policies = query(
        f"""
        SELECT dp.policy_id, dp.display_name, dp.status, dp.policy_type,
               dp.rules_count, dp.created, dp.modified, dp.mode,
               t.display_name AS tenant_name
        FROM dlp_policies dp
        JOIN tenants t ON t.tenant_id = dp.tenant_id
        WHERE dp.snapshot_date = (
                SELECT MAX(snapshot_date) FROM dlp_policies _sub
                WHERE _sub.tenant_id = dp.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        ORDER BY dp.display_name
        LIMIT 1000
        """,
        params,
    )

    status_breakdown = query(
        f"""
        SELECT dp.status, COUNT(*)::int AS total
        FROM dlp_policies dp
        JOIN tenants t ON t.tenant_id = dp.tenant_id
        WHERE dp.snapshot_date = (
                SELECT MAX(snapshot_date) FROM dlp_policies _sub
                WHERE _sub.tenant_id = dp.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        GROUP BY dp.status
        ORDER BY total DESC
        """,
        params,
    )

    return {"policies": policies, "status_breakdown": status_breakdown}


def get_irm_policies(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/irm-policies — Insider Risk Management policies."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    policies = query(
        f"""
        SELECT ip.policy_id, ip.display_name, ip.status, ip.policy_type,
               ip.created, ip.triggers, t.display_name AS tenant_name
        FROM irm_policies ip
        JOIN tenants t ON t.tenant_id = ip.tenant_id
        WHERE ip.snapshot_date = (
                SELECT MAX(snapshot_date) FROM irm_policies _sub
                WHERE _sub.tenant_id = ip.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        ORDER BY ip.display_name
        LIMIT 1000
        """,
        params,
    )

    return {"policies": policies}


def get_purview_incidents(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/purview-incidents — Purview-prioritized incidents."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    incidents = query(
        f"""
        SELECT pi.incident_id, pi.display_name, pi.severity, pi.status,
               pi.classification, pi.determination, pi.created, pi.last_update,
               pi.assigned_to, pi.alerts_count, pi.purview_alerts_count,
               t.display_name AS tenant_name
        FROM purview_incidents pi
        JOIN tenants t ON t.tenant_id = pi.tenant_id
        WHERE pi.snapshot_date = (
                SELECT MAX(snapshot_date) FROM purview_incidents _sub
                WHERE _sub.tenant_id = pi.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        ORDER BY
            CASE pi.severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
            END,
            pi.last_update DESC,
            pi.created DESC
        LIMIT 1000
        """,
        params,
    )

    severity_breakdown = query(
        f"""
        SELECT pi.severity, COUNT(*)::int AS total,
               COUNT(*) FILTER (WHERE pi.status NOT IN ('resolved', 'dismissed'))::int AS active
        FROM purview_incidents pi
        JOIN tenants t ON t.tenant_id = pi.tenant_id
        WHERE pi.snapshot_date = (
                SELECT MAX(snapshot_date) FROM purview_incidents _sub
                WHERE _sub.tenant_id = pi.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        GROUP BY pi.severity
        ORDER BY
            CASE pi.severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
            END
        """,
        params,
    )

    status_breakdown = query(
        f"""
        SELECT pi.status, COUNT(*)::int AS total
        FROM purview_incidents pi
        JOIN tenants t ON t.tenant_id = pi.tenant_id
        WHERE pi.snapshot_date = (
                SELECT MAX(snapshot_date) FROM purview_incidents _sub
                WHERE _sub.tenant_id = pi.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        GROUP BY pi.status
        ORDER BY total DESC
        """,
        params,
    )

    return {
        "incidents": incidents,
        "severity_breakdown": severity_breakdown,
        "status_breakdown": status_breakdown,
    }


def get_sensitive_info_types(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/sensitive-info-types — Sensitive Information Types."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    types = query(
        f"""
        SELECT si.type_id, si.name, si.description, si.is_custom,
               si.category, si.scope, si.state, t.display_name AS tenant_name
        FROM sensitive_info_types si
        JOIN tenants t ON t.tenant_id = si.tenant_id
        WHERE si.snapshot_date = (
                SELECT MAX(snapshot_date) FROM sensitive_info_types _sub
                WHERE _sub.tenant_id = si.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        ORDER BY si.name
        LIMIT 1000
        """,
        params,
    )

    custom_count = sum(1 for t in types if t.get("is_custom"))
    builtin_count = len(types) - custom_count

    return {"types": types, "custom_count": custom_count, "builtin_count": builtin_count}


def get_compliance_assessments(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/assessments — Compliance Assessments."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    assessments = query(
        f"""
        SELECT ca.assessment_id, ca.display_name, ca.status, ca.framework,
               ca.completion_percentage, ca.created, ca.category,
               t.display_name AS tenant_name
        FROM compliance_assessments ca
        JOIN tenants t ON t.tenant_id = ca.tenant_id
        WHERE ca.snapshot_date = (
                SELECT MAX(snapshot_date) FROM compliance_assessments _sub
                WHERE _sub.tenant_id = ca.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        ORDER BY ca.display_name
        LIMIT 1000
        """,
        params,
    )

    framework_breakdown = query(
        f"""
        SELECT ca.framework, COUNT(*)::int AS total
        FROM compliance_assessments ca
        JOIN tenants t ON t.tenant_id = ca.tenant_id
        WHERE ca.snapshot_date = (
                SELECT MAX(snapshot_date) FROM compliance_assessments _sub
                WHERE _sub.tenant_id = ca.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        GROUP BY ca.framework
        ORDER BY total DESC
        """,
        params,
    )

    return {"assessments": assessments, "framework_breakdown": framework_breakdown}


def get_improvement_actions(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/actions — Secure Score and improvement actions."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    score = query_one(
        f"""
        SELECT COALESCE(SUM(ss.current_score), 0)::real AS current_score,
               COALESCE(SUM(ss.max_score), 0)::real AS max_score,
               MAX(ss.score_date)::text AS score_date,
               COALESCE(SUM(ss.data_current_score), 0)::real AS data_current_score,
               COALESCE(SUM(ss.data_max_score), 0)::real AS data_max_score
        FROM secure_scores ss
        JOIN tenants t ON t.tenant_id = ss.tenant_id
        WHERE ss.snapshot_date = (
                SELECT MAX(snapshot_date) FROM secure_scores _sub
                WHERE _sub.tenant_id = ss.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        """,
        params,
    )

    actions = query(
        f"""
        SELECT ia.control_id, ia.title, ia.control_category, ia.max_score,
               ia.current_score, ia.implementation_cost, ia.user_impact,
               ia.tier, ia.service, ia.threats, ia.remediation, ia.state,
               ia.rank, t.display_name AS tenant_name
        FROM improvement_actions ia
        JOIN tenants t ON t.tenant_id = ia.tenant_id
        WHERE ia.snapshot_date = (
                SELECT MAX(snapshot_date) FROM improvement_actions _sub
                WHERE _sub.tenant_id = ia.tenant_id
            )
          AND ia.deprecated = FALSE
          AND ia.control_category = 'Data'
          {dept_filter}
          {tenant_filter}
        ORDER BY ia.rank
        LIMIT 1000
        """,
        params,
    )

    category_breakdown = query(
        f"""
        SELECT ia.control_category, COUNT(*)::int AS total,
               SUM(ia.max_score)::real AS total_max_score
        FROM improvement_actions ia
        JOIN tenants t ON t.tenant_id = ia.tenant_id
        WHERE ia.snapshot_date = (
                SELECT MAX(snapshot_date) FROM improvement_actions _sub
                WHERE _sub.tenant_id = ia.tenant_id
            )
          AND ia.deprecated = FALSE
          AND ia.control_category = 'Data'
          {dept_filter}
          {tenant_filter}
        GROUP BY ia.control_category
        ORDER BY total_max_score DESC
        """,
        params,
    )

    return {
        "secure_score": score
        or {
            "current_score": 0,
            "max_score": 0,
            "score_date": None,
            "data_current_score": 0,
            "data_max_score": 0,
        },
        "actions": actions,
        "category_breakdown": category_breakdown,
    }


def get_threat_assessments(department: str | None = None, tenant_id: str | None = None) -> dict:
    """POST /api/advisor/threat-assessments — Threat Assessment Requests."""
    dept_filter = ""
    tenant_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    requests_list = query(
        f"""
        SELECT ta.request_id, ta.category, ta.content_type, ta.status,
               ta.created, ta.result_type, ta.result_message,
               t.display_name AS tenant_name
        FROM threat_assessment_requests ta
        JOIN tenants t ON t.tenant_id = ta.tenant_id
        WHERE ta.snapshot_date = (
                SELECT MAX(snapshot_date) FROM threat_assessment_requests _sub
                WHERE _sub.tenant_id = ta.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        ORDER BY ta.created DESC
        LIMIT 1000
        """,
        params,
    )

    status_breakdown = query(
        f"""
        SELECT ta.status, COUNT(*)::int AS total
        FROM threat_assessment_requests ta
        JOIN tenants t ON t.tenant_id = ta.tenant_id
        WHERE ta.snapshot_date = (
                SELECT MAX(snapshot_date) FROM threat_assessment_requests _sub
                WHERE _sub.tenant_id = ta.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        GROUP BY ta.status
        ORDER BY total DESC
        """,
        params,
    )

    category_breakdown = query(
        f"""
        SELECT ta.category, COUNT(*)::int AS total
        FROM threat_assessment_requests ta
        JOIN tenants t ON t.tenant_id = ta.tenant_id
        WHERE ta.snapshot_date = (
                SELECT MAX(snapshot_date) FROM threat_assessment_requests _sub
                WHERE _sub.tenant_id = ta.tenant_id
            )
          {dept_filter}
          {tenant_filter}
        GROUP BY ta.category
        ORDER BY total DESC
        """,
        params,
    )

    return {
        "requests": requests_list,
        "status_breakdown": status_breakdown,
        "category_breakdown": category_breakdown,
    }


def _parse_timestamp(value: str | None) -> datetime | None:
    """Parse timestamp/date strings safely."""
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        pass
    if len(text) >= 10:
        try:
            return datetime.fromisoformat(text[:10])
        except ValueError:
            return None
    return None


def get_purview_insights(department: str | None = None, tenant_id: str | None = None, days: int = 30) -> dict:
    """POST /api/advisor/purview-insights — advanced Purview KPI and risk analytics."""
    params: dict = {}
    dept_filter = ""
    tenant_filter = ""
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND t.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id

    today = date.today()
    start_date = today - timedelta(days=max(days - 1, 0))
    params["start_date"] = start_date.isoformat()
    params["end_date"] = today.isoformat()

    tenant_health_rows = query(
        f"""
        SELECT
            t.tenant_id,
            t.display_name,
            t.department,
            t.collected_at::text AS collected_at,
            il.snapshot_date::text AS last_snapshot_date,
            il.ingested_at::text AS last_payload_at,
            il.record_counts
        FROM tenants t
        LEFT JOIN LATERAL (
            SELECT i.snapshot_date, i.ingested_at, i.record_counts
            FROM ingestion_log i
            WHERE i.tenant_id = t.tenant_id
            ORDER BY i.ingested_at DESC
            LIMIT 1
        ) il ON TRUE
        WHERE 1=1
          {dept_filter}
          {tenant_filter}
        ORDER BY t.display_name
        """,
        params,
    )

    alert_metrics = query_one(
        f"""
        WITH latest_alerts AS (
            SELECT
                da.tenant_id,
                da.severity,
                da.status,
                da.classification,
                da.assigned_to,
                da.created,
                da.resolved
            FROM dlp_alerts da
            JOIN tenants t ON t.tenant_id = da.tenant_id
            WHERE da.snapshot_date = (
                SELECT MAX(snapshot_date) FROM dlp_alerts _sub WHERE _sub.tenant_id = da.tenant_id
            )
              {dept_filter}
              {tenant_filter}
            UNION ALL
            SELECT
                ia.tenant_id,
                ia.severity,
                ia.status,
                ia.classification,
                ia.assigned_to,
                ia.created,
                ia.resolved
            FROM irm_alerts ia
            JOIN tenants t ON t.tenant_id = ia.tenant_id
            WHERE ia.snapshot_date = (
                SELECT MAX(snapshot_date) FROM irm_alerts _sub WHERE _sub.tenant_id = ia.tenant_id
            )
              {dept_filter}
              {tenant_filter}
        )
        SELECT
            COUNT(*)::int AS total_alerts,
            COUNT(*) FILTER (
                WHERE lower(COALESCE(status, '')) IN ('resolved', 'dismissed')
            )::int AS resolved_alerts,
            COUNT(*) FILTER (
                WHERE lower(COALESCE(status, '')) NOT IN ('resolved', 'dismissed')
            )::int AS active_alerts,
            COUNT(*) FILTER (
                WHERE regexp_replace(lower(COALESCE(classification, '')), '[^a-z]', '', 'g') = 'truepositive'
            )::int AS true_positive_alerts,
            COUNT(*) FILTER (
                WHERE lower(COALESCE(status, '')) NOT IN ('resolved', 'dismissed')
                  AND lower(COALESCE(severity, '')) = 'high'
            )::int AS unresolved_high_alerts,
            COUNT(*) FILTER (
                WHERE lower(COALESCE(status, '')) NOT IN ('resolved', 'dismissed')
                  AND lower(COALESCE(severity, '')) = 'medium'
            )::int AS unresolved_medium_alerts,
            AVG(
                CASE
                    WHEN created ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'
                         AND resolved ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'
                    THEN EXTRACT(EPOCH FROM (resolved::timestamptz - created::timestamptz)) / 3600.0
                    ELSE NULL
                END
            )::real AS mttr_hours
        FROM latest_alerts
        """,
        params,
    ) or {}

    repeat_offenders = query(
        f"""
        WITH latest_alerts AS (
            SELECT
                da.tenant_id,
                COALESCE(NULLIF(da.assigned_to, ''), 'Unassigned') AS owner,
                da.severity,
                da.status,
                da.created
            FROM dlp_alerts da
            JOIN tenants t ON t.tenant_id = da.tenant_id
            WHERE da.snapshot_date = (
                SELECT MAX(snapshot_date) FROM dlp_alerts _sub WHERE _sub.tenant_id = da.tenant_id
            )
              {dept_filter}
              {tenant_filter}
            UNION ALL
            SELECT
                ia.tenant_id,
                COALESCE(NULLIF(ia.assigned_to, ''), 'Unassigned') AS owner,
                ia.severity,
                ia.status,
                ia.created
            FROM irm_alerts ia
            JOIN tenants t ON t.tenant_id = ia.tenant_id
            WHERE ia.snapshot_date = (
                SELECT MAX(snapshot_date) FROM irm_alerts _sub WHERE _sub.tenant_id = ia.tenant_id
            )
              {dept_filter}
              {tenant_filter}
        )
        SELECT
            owner,
            COUNT(*)::int AS total_alerts,
            COUNT(*) FILTER (
                WHERE lower(COALESCE(status, '')) NOT IN ('resolved', 'dismissed')
            )::int AS open_alerts,
            COUNT(*) FILTER (
                WHERE lower(COALESCE(status, '')) NOT IN ('resolved', 'dismissed')
                  AND lower(COALESCE(severity, '')) = 'high'
            )::int AS high_severity,
            AVG(
                CASE
                    WHEN created ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'
                    THEN EXTRACT(EPOCH FROM (NOW() - created::timestamptz)) / 86400.0
                    ELSE NULL
                END
            )::real AS avg_age_days
        FROM latest_alerts
        GROUP BY owner
        ORDER BY open_alerts DESC, high_severity DESC, total_alerts DESC
        LIMIT 10
        """,
        params,
    )

    label_summary = query_one(
        f"""
        SELECT
            COUNT(*)::int AS total_labels,
            COUNT(*) FILTER (WHERE sl.has_protection = TRUE)::int AS protected_labels
        FROM sensitivity_labels sl
        JOIN tenants t ON t.tenant_id = sl.tenant_id
        WHERE sl.snapshot_date = (
            SELECT MAX(snapshot_date) FROM sensitivity_labels _sub WHERE _sub.tenant_id = sl.tenant_id
        )
          {dept_filter}
          {tenant_filter}
        """,
        params,
    ) or {}

    coverage_breakdown = query(
        f"""
        SELECT
            COALESCE(NULLIF(sl.applicable_to, ''), 'unspecified') AS applicable_to,
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE sl.has_protection = TRUE)::int AS protected
        FROM sensitivity_labels sl
        JOIN tenants t ON t.tenant_id = sl.tenant_id
        WHERE sl.snapshot_date = (
            SELECT MAX(snapshot_date) FROM sensitivity_labels _sub WHERE _sub.tenant_id = sl.tenant_id
        )
          {dept_filter}
          {tenant_filter}
        GROUP BY COALESCE(NULLIF(sl.applicable_to, ''), 'unspecified')
        ORDER BY total DESC
        """,
        params,
    )

    trend_rows = query(
        f"""
        SELECT
            day_bucket.snapshot_date::text,
            COALESCE(dlp.daily_dlp_alerts, 0)::int AS dlp_alerts,
            COALESCE(inc.daily_active_incidents, 0)::int AS active_incidents,
            COALESCE(scores.data_score_pct, 0)::real AS data_score_pct,
            COALESCE(policy_changes.policy_changes, 0)::int AS policy_changes
        FROM (
            SELECT generate_series(%(start_date)s::date, %(end_date)s::date, interval '1 day')::date AS snapshot_date
        ) day_bucket
        LEFT JOIN (
            SELECT da.snapshot_date, COUNT(*)::int AS daily_dlp_alerts
            FROM dlp_alerts da
            JOIN tenants t ON t.tenant_id = da.tenant_id
            WHERE da.snapshot_date BETWEEN %(start_date)s::date AND %(end_date)s::date
              {dept_filter}
              {tenant_filter}
            GROUP BY da.snapshot_date
        ) dlp ON dlp.snapshot_date = day_bucket.snapshot_date
        LEFT JOIN (
            SELECT pi.snapshot_date,
                   COUNT(*) FILTER (
                       WHERE lower(COALESCE(pi.status, '')) NOT IN ('resolved', 'dismissed')
                   )::int AS daily_active_incidents
            FROM purview_incidents pi
            JOIN tenants t ON t.tenant_id = pi.tenant_id
            WHERE pi.snapshot_date BETWEEN %(start_date)s::date AND %(end_date)s::date
              {dept_filter}
              {tenant_filter}
            GROUP BY pi.snapshot_date
        ) inc ON inc.snapshot_date = day_bucket.snapshot_date
        LEFT JOIN (
            SELECT
                ss.snapshot_date,
                CASE
                    WHEN SUM(ss.data_max_score) = 0 THEN 0
                    ELSE ROUND((((SUM(ss.data_current_score) / SUM(ss.data_max_score)) * 100.0)::numeric), 2)
                END::real AS data_score_pct
            FROM secure_scores ss
            JOIN tenants t ON t.tenant_id = ss.tenant_id
            WHERE ss.snapshot_date BETWEEN %(start_date)s::date AND %(end_date)s::date
              {dept_filter}
              {tenant_filter}
            GROUP BY ss.snapshot_date
        ) scores ON scores.snapshot_date = day_bucket.snapshot_date
        LEFT JOIN (
            SELECT p.change_date AS snapshot_date, COUNT(*)::int AS policy_changes
            FROM (
                SELECT
                    CASE
                        WHEN dp.modified ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'
                            THEN substring(dp.modified from 1 for 10)::date
                        WHEN dp.created ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'
                            THEN substring(dp.created from 1 for 10)::date
                        ELSE NULL
                    END AS change_date
                FROM dlp_policies dp
                JOIN tenants t ON t.tenant_id = dp.tenant_id
                WHERE dp.snapshot_date = (
                    SELECT MAX(snapshot_date) FROM dlp_policies _sub WHERE _sub.tenant_id = dp.tenant_id
                )
                  {dept_filter}
                  {tenant_filter}
                UNION ALL
                SELECT
                    CASE
                        WHEN ip.created ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}'
                            THEN substring(ip.created from 1 for 10)::date
                        ELSE NULL
                    END AS change_date
                FROM irm_policies ip
                JOIN tenants t ON t.tenant_id = ip.tenant_id
                WHERE ip.snapshot_date = (
                    SELECT MAX(snapshot_date) FROM irm_policies _sub WHERE _sub.tenant_id = ip.tenant_id
                )
                  {dept_filter}
                  {tenant_filter}
            ) p
            WHERE p.change_date BETWEEN %(start_date)s::date AND %(end_date)s::date
            GROUP BY p.change_date
        ) policy_changes ON policy_changes.snapshot_date = day_bucket.snapshot_date
        ORDER BY day_bucket.snapshot_date
        """,
        params,
    )

    assessments_rows = query(
        f"""
        SELECT
            ca.assessment_id,
            ca.display_name,
            ca.framework,
            COALESCE(ca.completion_percentage, 0)::real AS completion_percentage,
            ca.status,
            t.display_name AS tenant_name
        FROM compliance_assessments ca
        JOIN tenants t ON t.tenant_id = ca.tenant_id
        WHERE ca.snapshot_date = (
            SELECT MAX(snapshot_date) FROM compliance_assessments _sub WHERE _sub.tenant_id = ca.tenant_id
        )
          {dept_filter}
          {tenant_filter}
        ORDER BY ca.framework, ca.display_name
        """,
        params,
    )

    open_actions = query(
        f"""
        SELECT
            ia.control_id,
            ia.title,
            ia.control_category,
            ia.max_score,
            ia.current_score,
            ia.threats,
            ia.remediation,
            ia.state,
            ia.rank,
            t.display_name AS tenant_name
        FROM improvement_actions ia
        JOIN tenants t ON t.tenant_id = ia.tenant_id
        WHERE ia.snapshot_date = (
            SELECT MAX(snapshot_date) FROM improvement_actions _sub WHERE _sub.tenant_id = ia.tenant_id
        )
          AND ia.deprecated = FALSE
          AND ia.control_category = 'Data'
          AND ia.max_score > ia.current_score
          {dept_filter}
          {tenant_filter}
        ORDER BY (ia.max_score - ia.current_score) DESC, ia.rank ASC
        LIMIT 20
        """,
        params,
    )

    open_incidents = query(
        f"""
        SELECT
            pi.incident_id,
            pi.display_name,
            pi.severity,
            pi.status,
            COALESCE(NULLIF(pi.assigned_to, ''), 'Unassigned') AS owner,
            pi.last_update,
            t.display_name AS tenant_name
        FROM purview_incidents pi
        JOIN tenants t ON t.tenant_id = pi.tenant_id
        WHERE pi.snapshot_date = (
            SELECT MAX(snapshot_date) FROM purview_incidents _sub WHERE _sub.tenant_id = pi.tenant_id
        )
          AND lower(COALESCE(pi.status, '')) NOT IN ('resolved', 'dismissed')
          {dept_filter}
          {tenant_filter}
        ORDER BY
            CASE lower(COALESCE(pi.severity, ''))
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                ELSE 5
            END,
            pi.last_update DESC
        LIMIT 20
        """,
        params,
    )

    total_alerts = int(alert_metrics.get("total_alerts") or 0)
    resolved_alerts = int(alert_metrics.get("resolved_alerts") or 0)
    active_alerts = int(alert_metrics.get("active_alerts") or 0)
    true_positive_alerts = int(alert_metrics.get("true_positive_alerts") or 0)
    mttr_hours = float(alert_metrics.get("mttr_hours") or 0.0)
    closure_rate = round((resolved_alerts / total_alerts) * 100, 1) if total_alerts else 0.0
    true_positive_rate = round((true_positive_alerts / total_alerts) * 100, 1) if total_alerts else 0.0

    total_labels = int(label_summary.get("total_labels") or 0)
    protected_labels = int(label_summary.get("protected_labels") or 0)
    unprotected_labels = max(total_labels - protected_labels, 0)
    coverage_pct = round((protected_labels / total_labels) * 100, 1) if total_labels else 0.0

    trend_timeline: list[dict] = []
    correlated_days = 0
    spike_days = 0
    previous_dlp_points: list[int] = []
    previous_data_score = None
    for row in trend_rows:
        dlp_alerts = int(row.get("dlp_alerts") or 0)
        policy_changes = int(row.get("policy_changes") or 0)
        data_score_pct = float(row.get("data_score_pct") or 0.0)

        window = previous_dlp_points[-7:]
        baseline = (sum(window) / len(window)) if window else 0.0
        if baseline > 0:
            risk_spike = dlp_alerts >= (baseline * 1.25) and (dlp_alerts - baseline) >= 2
        else:
            risk_spike = dlp_alerts >= 3
        if risk_spike:
            spike_days += 1
        correlated = bool(risk_spike and policy_changes > 0)
        if correlated:
            correlated_days += 1
        secure_score_delta = round(data_score_pct - previous_data_score, 2) if previous_data_score is not None else 0.0

        trend_timeline.append(
            {
                "snapshot_date": row.get("snapshot_date"),
                "dlp_alerts": dlp_alerts,
                "active_incidents": int(row.get("active_incidents") or 0),
                "policy_changes": policy_changes,
                "data_score_pct": data_score_pct,
                "risk_spike": risk_spike,
                "correlated_change": correlated,
                "secure_score_delta": secure_score_delta,
            }
        )
        previous_dlp_points.append(dlp_alerts)
        previous_data_score = data_score_pct

    unresolved_high = int(alert_metrics.get("unresolved_high_alerts") or 0)
    unresolved_medium = int(alert_metrics.get("unresolved_medium_alerts") or 0)
    active_incidents_now = sum(1 for i in open_incidents)
    weighted_points = {
        "high_alert_weighted": unresolved_high * 5,
        "medium_alert_weighted": unresolved_medium * 3,
        "active_incident_weighted": active_incidents_now * 4,
        "unprotected_label_weighted": unprotected_labels * 2,
    }
    risk_score = min(100.0, round(sum(weighted_points.values()) * 1.5, 1))
    if risk_score >= 80:
        risk_level = "Critical"
    elif risk_score >= 60:
        risk_level = "High"
    elif risk_score >= 35:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    owners: dict[str, dict] = {}
    for row in repeat_offenders:
        owner = row.get("owner") or "Unassigned"
        owners[owner] = {
            "owner": owner,
            "open_alerts": int(row.get("open_alerts") or 0),
            "high_severity": int(row.get("high_severity") or 0),
            "active_incidents": 0,
            "avg_age_days": round(float(row.get("avg_age_days") or 0), 1),
        }
    for incident in open_incidents:
        owner = incident.get("owner") or "Unassigned"
        if owner not in owners:
            owners[owner] = {
                "owner": owner,
                "open_alerts": 0,
                "high_severity": 0,
                "active_incidents": 0,
                "avg_age_days": 0.0,
            }
        owners[owner]["active_incidents"] += 1
    owner_rows = sorted(
        owners.values(),
        key=lambda r: (r["open_alerts"] + r["active_incidents"], r["high_severity"]),
        reverse=True,
    )

    priority_actions: list[dict] = []
    default_owner = owner_rows[0]["owner"] if owner_rows else "Compliance Team"
    for action in open_actions[:10]:
        gap = float(action.get("max_score") or 0) - float(action.get("current_score") or 0)
        threats = str(action.get("threats") or "").lower()
        threat_multiplier = 1.25 if ("exfiltration" in threats or "insider" in threats or "leak" in threats) else 1.0
        reduction_score = round(max(gap, 0) * threat_multiplier, 2)
        priority = "High" if reduction_score >= 8 else ("Medium" if reduction_score >= 4 else "Low")
        priority_actions.append(
            {
                "action_type": "Secure Score Improvement",
                "title": action.get("title") or "",
                "owner": default_owner,
                "priority": priority,
                "risk_reduction_score": reduction_score,
                "tenant_name": action.get("tenant_name") or "",
                "evidence_link": (
                    f"https://security.microsoft.com/securescore?viewid=actions&control={action.get('control_id', '')}"
                ),
            }
        )
    for incident in open_incidents[:5]:
        severity = str(incident.get("severity") or "").lower()
        priority = "High" if severity in {"critical", "high"} else "Medium"
        reduction_score = 9.0 if severity == "critical" else (7.0 if severity == "high" else 4.5)
        priority_actions.append(
            {
                "action_type": "Incident Triage",
                "title": incident.get("display_name") or "",
                "owner": incident.get("owner") or default_owner,
                "priority": priority,
                "risk_reduction_score": reduction_score,
                "tenant_name": incident.get("tenant_name") or "",
                "evidence_link": (
                    "https://purview.microsoft.com/insiderriskmanagement?view=alerts"
                    f"&incidentId={incident.get('incident_id', '')}"
                ),
            }
        )
    priority_actions.sort(key=lambda r: (r["risk_reduction_score"], r["priority"] == "High"), reverse=True)

    framework_rows: dict[str, list[dict]] = {}
    for assessment in assessments_rows:
        framework = assessment.get("framework") or "Unspecified"
        framework_rows.setdefault(framework, []).append(assessment)
    if framework_rows:
        cjis_nist = [f for f in framework_rows if ("cjis" in f.lower() or "nist" in f.lower())]
        selected_frameworks = cjis_nist if cjis_nist else list(framework_rows.keys())[:2]
    else:
        selected_frameworks = []

    framework_summary: list[dict] = []
    controls: list[dict] = []
    for framework in selected_frameworks:
        assessments = framework_rows.get(framework, [])
        avg_completion = (
            round(sum(float(a.get("completion_percentage") or 0) for a in assessments) / len(assessments), 1)
            if assessments
            else 0.0
        )
        framework_summary.append(
            {
                "framework": framework,
                "total_assessments": len(assessments),
                "avg_completion": avg_completion,
                "estimated_gap_count": sum(1 for a in assessments if float(a.get("completion_percentage") or 0) < 80),
            }
        )
        top_assessment = assessments[0] if assessments else {}
        for action in open_actions[:3]:
            score_gap = float(action.get("max_score") or 0) - float(action.get("current_score") or 0)
            controls.append(
                {
                    "framework": framework,
                    "control_id": action.get("control_id") or "",
                    "control_title": action.get("title") or "",
                    "status": action.get("state") or "Unknown",
                    "priority": "High" if score_gap >= 8 else "Medium",
                    "owner": default_owner,
                    "completion_percentage": float(top_assessment.get("completion_percentage") or 0),
                    "evidence_links": [
                        {
                            "label": f"Assessment {top_assessment.get('assessment_id', 'N/A')}",
                            "url": (
                                "https://purview.microsoft.com/compliancemanager/assessments/"
                                f"{top_assessment.get('assessment_id', '')}"
                            ),
                        },
                        {
                            "label": f"Secure Score Control {action.get('control_id', '')}",
                            "url": (
                                "https://security.microsoft.com/securescore?viewid=actions"
                                f"&control={action.get('control_id', '')}"
                            ),
                        },
                    ],
                }
            )

    required_datasets = [
        "sensitivity_labels",
        "audit_records",
        "dlp_alerts",
        "irm_alerts",
        "info_barrier_policies",
        "protection_scopes",
        "dlp_policies",
        "irm_policies",
        "sensitive_info_types",
        "compliance_assessments",
        "threat_assessment_requests",
        "purview_incidents",
    ]
    now_utc = datetime.now(timezone.utc)
    tenant_health: list[dict] = []
    stale_tenants = 0
    complete_tenants = 0
    freshest_sync: datetime | None = None
    for row in tenant_health_rows:
        collected_at = _parse_timestamp(row.get("collected_at"))
        if collected_at and collected_at.tzinfo is None:
            collected_at = collected_at.replace(tzinfo=timezone.utc)
        if collected_at and (freshest_sync is None or collected_at > freshest_sync):
            freshest_sync = collected_at

        record_counts = row.get("record_counts") or {}
        if isinstance(record_counts, str):
            try:
                record_counts = json.loads(record_counts)
            except (TypeError, ValueError):
                record_counts = {}

        missing = [dataset for dataset in required_datasets if int(record_counts.get(dataset, 0) or 0) <= 0]
        completeness_pct = round(((len(required_datasets) - len(missing)) / len(required_datasets)) * 100, 1)

        is_stale = True
        if collected_at is not None:
            is_stale = (now_utc - collected_at) > timedelta(hours=48)
        if is_stale:
            stale_tenants += 1
        if not missing:
            complete_tenants += 1

        tenant_health.append(
            {
                "tenant_id": row.get("tenant_id"),
                "display_name": row.get("display_name"),
                "department": row.get("department"),
                "last_collected_at": row.get("collected_at"),
                "last_snapshot_date": row.get("last_snapshot_date"),
                "last_payload_at": row.get("last_payload_at"),
                "is_stale": is_stale,
                "completeness_pct": completeness_pct,
                "missing_datasets": missing,
            }
        )

    return {
        "effectiveness": {
            "total_alerts": total_alerts,
            "resolved_alerts": resolved_alerts,
            "active_alerts": active_alerts,
            "closure_rate_pct": closure_rate,
            "true_positive_rate_pct": true_positive_rate,
            "mttr_hours": round(mttr_hours, 2),
            "repeat_offenders": repeat_offenders,
        },
        "classification_coverage": {
            "total_labels": total_labels,
            "protected_labels": protected_labels,
            "coverage_pct": coverage_pct,
            "breakdown": coverage_breakdown,
        },
        "policy_drift": {
            "window_days": days,
            "timeline": trend_timeline,
            "summary": {
                "total_policy_changes": sum(int(r.get("policy_changes") or 0) for r in trend_rows),
                "risk_spike_days": spike_days,
                "correlated_days": correlated_days,
            },
        },
        "data_at_risk": {
            "score": risk_score,
            "risk_level": risk_level,
            "components": {
                "unresolved_high_alerts": unresolved_high,
                "unresolved_medium_alerts": unresolved_medium,
                "active_incidents": active_incidents_now,
                "unprotected_labels": unprotected_labels,
            },
            "weighted_points": weighted_points,
        },
        "control_mapping": {
            "framework_summary": framework_summary,
            "controls": controls,
        },
        "owner_actions": {
            "owners": owner_rows,
            "priority_actions": priority_actions[:15],
        },
        "collection_health": {
            "required_datasets": required_datasets,
            "newest_sync": freshest_sync.isoformat() if freshest_sync else None,
            "stale_tenants": stale_tenants,
            "complete_tenants": complete_tenants,
            "tenant_health": tenant_health,
        },
    }


def get_hunt_results(
    department: str | None = None, tenant_id: str | None = None, severity: str | None = None, days: int = 30
) -> dict:
    """POST /api/advisor/hunt-results — stored threat hunting results."""
    dept_filter = ""
    tenant_filter = ""
    severity_filter = ""
    params: dict = {"days": days}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department
    if tenant_id:
        tenant_filter = "AND hr.tenant_id = %(tenant_id)s"
        params["tenant_id"] = tenant_id
    if severity:
        severity_filter = "AND hr.severity = %(severity)s"
        params["severity"] = severity

    results = query(
        f"""
        SELECT hr.id, hr.finding_type, hr.severity, hr.account_upn,
               hr.object_name, hr.action_type, hr.evidence,
               hr.detected_at::text, hr.snapshot_date::text,
               run.question, run.template_name, run.kql_query
        FROM hunt_results hr
        JOIN hunt_runs run ON hr.run_id = run.id
        JOIN tenants t ON hr.tenant_id = t.tenant_id
        WHERE hr.snapshot_date >= CURRENT_DATE - %(days)s
        {dept_filter} {tenant_filter} {severity_filter}
        ORDER BY hr.detected_at DESC NULLS LAST
        LIMIT 200
        """,
        params,
    )

    summary = query_one(
        f"""
        SELECT
            COUNT(*)::int AS total,
            COUNT(*) FILTER (WHERE hr.severity = 'high')::int AS high,
            COUNT(*) FILTER (WHERE hr.severity = 'medium')::int AS medium,
            COUNT(*) FILTER (WHERE hr.severity = 'low')::int AS low,
            COUNT(*) FILTER (WHERE hr.severity = 'info')::int AS info
        FROM hunt_results hr
        JOIN tenants t ON hr.tenant_id = t.tenant_id
        WHERE hr.snapshot_date >= CURRENT_DATE - %(days)s
        {dept_filter} {tenant_filter}
        """,
        params,
    )

    runs = query(
        f"""
        SELECT run.id, run.template_name, run.question, run.result_count,
               run.run_at::text, run.ai_narrative
        FROM hunt_runs run
        JOIN tenants t ON run.tenant_id = t.tenant_id
        WHERE run.snapshot_date >= CURRENT_DATE - %(days)s
        {dept_filter} {tenant_filter}
        ORDER BY run.run_at DESC
        LIMIT 20
        """,
        params,
    )

    return {
        "results": results,
        "summary": summary if summary else {"total": 0, "high": 0, "medium": 0, "low": 0, "info": 0},
        "recent_runs": runs,
    }
