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
    """GET /api/advisor/status"""
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


def get_compliance(department: str | None = None, days: int = 30) -> dict:
    """GET /api/advisor/compliance"""
    dept_filter = ""
    params: dict = {"days": days}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    # Latest scores per tenant
    latest_scores = query(
        f"""
        SELECT DISTINCT ON (ps.tenant_id)
            ps.tenant_id, t.display_name, t.department, t.risk_tier,
            ps.compliance_pct, ps.compliance_score AS current_score,
            ps.max_score, ps.snapshot_date::text
        FROM posture_snapshots ps
        JOIN tenants t ON t.tenant_id = ps.tenant_id
        WHERE 1=1 {dept_filter}
        ORDER BY ps.tenant_id, ps.snapshot_date DESC
        """,
        params,
    )

    # Compliance trend
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    trend_filter = "WHERE ct.department IS NULL" if not department else "WHERE ct.department = %(dept)s"
    compliance_trend = query(
        f"""
        SELECT ct.snapshot_date::text, ct.avg_compliance_pct,
               ct.min_compliance_pct, ct.max_compliance_pct
        FROM compliance_trend ct
        {trend_filter}
          AND ct.snapshot_date >= %(cutoff)s
        ORDER BY ct.snapshot_date
        """,
        {**params, "cutoff": cutoff},
    )

    # Week-over-week changes
    weekly_changes = query(
        f"""
        WITH current_week AS (
            SELECT DISTINCT ON (ps.tenant_id)
                ps.tenant_id, ps.compliance_pct AS current_pct, ps.snapshot_date
            FROM posture_snapshots ps
            ORDER BY ps.tenant_id, ps.snapshot_date DESC
        ),
        prior_week AS (
            SELECT DISTINCT ON (ps.tenant_id)
                ps.tenant_id, ps.compliance_pct AS prior_pct
            FROM posture_snapshots ps
            WHERE ps.snapshot_date <= CURRENT_DATE - INTERVAL '7 days'
            ORDER BY ps.tenant_id, ps.snapshot_date DESC
        )
        SELECT t.display_name, t.department,
               cw.current_pct, COALESCE(pw.prior_pct, cw.current_pct) AS prior_pct,
               ROUND((cw.current_pct - COALESCE(pw.prior_pct, cw.current_pct))::numeric, 2) AS wow_change,
               CASE
                   WHEN cw.current_pct > COALESCE(pw.prior_pct, cw.current_pct) THEN 'Improving'
                   WHEN cw.current_pct < COALESCE(pw.prior_pct, cw.current_pct) THEN 'Declining'
                   ELSE 'Stable'
               END AS trend_direction
        FROM current_week cw
        JOIN tenants t ON t.tenant_id = cw.tenant_id
        LEFT JOIN prior_week pw ON pw.tenant_id = cw.tenant_id
        WHERE 1=1 {dept_filter}
        ORDER BY wow_change ASC
        """,
        params,
    )

    # Department rollup
    department_rollup = query(
        f"""
        WITH latest AS (
            SELECT DISTINCT ON (ps.tenant_id)
                ps.tenant_id, ps.compliance_pct
            FROM posture_snapshots ps
            ORDER BY ps.tenant_id, ps.snapshot_date DESC
        )
        SELECT t.department,
               COUNT(*)::int AS tenant_count,
               ROUND(AVG(l.compliance_pct)::numeric, 2) AS avg_compliance_pct,
               ROUND(MIN(l.compliance_pct)::numeric, 2) AS min_compliance_pct,
               ROUND(MAX(l.compliance_pct)::numeric, 2) AS max_compliance_pct,
               COALESCE(SUM(asmt.total_assessments), 0)::int AS total_assessments,
               COALESCE(SUM(asmt.total_failed), 0)::int AS total_failed_controls
        FROM latest l
        JOIN tenants t ON t.tenant_id = l.tenant_id
        LEFT JOIN LATERAL (
            SELECT COUNT(*)::int AS total_assessments,
                   SUM(a.failed_controls)::int AS total_failed
            FROM assessments a
            WHERE a.tenant_id = t.tenant_id
              AND a.snapshot_date = (SELECT MAX(snapshot_date) FROM assessments)
        ) asmt ON TRUE
        WHERE 1=1 {dept_filter}
        GROUP BY t.department
        ORDER BY avg_compliance_pct ASC
        """,
        params,
    )

    return {
        "latest_scores": latest_scores,
        "compliance_trend": compliance_trend,
        "weekly_changes": weekly_changes,
        "department_rollup": department_rollup,
    }


def get_assessments(department: str | None = None) -> dict:
    """GET /api/advisor/assessments"""
    dept_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    assessments = query(
        f"""
        SELECT a.assessment_name, a.regulation, t.display_name,
               a.compliance_score, a.pass_rate,
               a.passed_controls, a.failed_controls, a.total_controls
        FROM assessments a
        JOIN tenants t ON t.tenant_id = a.tenant_id
        WHERE a.snapshot_date = (SELECT MAX(snapshot_date) FROM assessments)
          {dept_filter}
        ORDER BY a.compliance_score ASC
        """,
        params,
    )

    # Top gaps (highest-impact unimplemented actions)
    top_gaps = query(
        f"""
        SELECT ia.control_name, ia.control_family, ia.regulation,
               ia.implementation_status, ia.test_status,
               ia.point_value AS points_gap, ia.owner, ia.service,
               ia.description, ia.remediation_steps,
               t.display_name, ia.action_category
        FROM improvement_actions ia
        JOIN tenants t ON t.tenant_id = ia.tenant_id
        WHERE ia.implementation_status != 'implemented'
          AND ia.snapshot_date = (SELECT MAX(snapshot_date) FROM improvement_actions)
          {dept_filter}
        ORDER BY ia.point_value DESC
        LIMIT 20
        """,
        params,
    )

    # Control family rollup
    control_families = query(
        f"""
        SELECT ia.control_family,
               COUNT(*)::int AS total_controls,
               COUNT(*) FILTER (WHERE ia.implementation_status = 'implemented')::int AS implemented,
               COUNT(*) FILTER (WHERE ia.test_status = 'passed')::int AS passed,
               COUNT(*) FILTER (WHERE ia.implementation_status != 'implemented')::int AS failed,
               ROUND(AVG(ia.point_value)::numeric, 1) AS avg_gap
        FROM improvement_actions ia
        JOIN tenants t ON t.tenant_id = ia.tenant_id
        WHERE ia.snapshot_date = (SELECT MAX(snapshot_date) FROM improvement_actions)
          {dept_filter}
        GROUP BY ia.control_family
        ORDER BY failed DESC
        """,
        params,
    )

    return {
        "assessments": assessments,
        "top_gaps": top_gaps,
        "control_families": control_families,
    }


def get_regulations() -> dict:
    """GET /api/advisor/regulations"""
    regulations = query(
        """
        SELECT a.regulation,
               COUNT(DISTINCT a.tenant_id)::int AS tenant_count,
               COUNT(*)::int AS assessment_count,
               ROUND(AVG(a.compliance_score)::numeric, 1) AS avg_compliance_score,
               SUM(a.passed_controls)::int AS total_passed,
               SUM(a.failed_controls)::int AS total_failed,
               SUM(a.total_controls)::int AS total_controls,
               ROUND(
                   (SUM(a.passed_controls)::numeric /
                    NULLIF(SUM(a.total_controls), 0) * 100), 1
               ) AS overall_pass_rate
        FROM assessments a
        WHERE a.snapshot_date = (SELECT MAX(snapshot_date) FROM assessments)
        GROUP BY a.regulation
        ORDER BY avg_compliance_score ASC
        """
    )
    return {"regulations": regulations}


def get_actions(department: str | None = None) -> dict:
    """GET /api/advisor/actions"""
    dept_filter = ""
    params: dict = {}
    if department:
        dept_filter = "AND t.department = %(dept)s"
        params["dept"] = department

    actions = query(
        f"""
        SELECT ia.action_id, ia.control_name, ia.control_family, ia.regulation,
               ia.implementation_status, ia.test_status, ia.action_category,
               ia.is_mandatory, ia.point_value, ia.owner, ia.service,
               ia.description, ia.remediation_steps,
               t.display_name, t.department
        FROM improvement_actions ia
        JOIN tenants t ON t.tenant_id = ia.tenant_id
        WHERE ia.snapshot_date = (SELECT MAX(snapshot_date) FROM improvement_actions)
          {dept_filter}
        ORDER BY ia.point_value DESC
        """,
        params,
    )

    # Summary
    summary_row = query_one(
        f"""
        SELECT COUNT(*)::int AS total,
               COUNT(*) FILTER (WHERE ia.implementation_status = 'implemented')::int AS implemented,
               COUNT(*) FILTER (WHERE ia.implementation_status = 'planned')::int AS planned,
               COUNT(*) FILTER (WHERE ia.implementation_status = 'notImplemented')::int AS not_implemented,
               SUM(ia.point_value)::int AS total_points,
               SUM(ia.point_value) FILTER (WHERE ia.implementation_status = 'implemented')::int AS earned_points,
               COUNT(*) FILTER (WHERE ia.point_value >= 27)::int AS high_impact,
               COUNT(*) FILTER (WHERE ia.point_value >= 3 AND ia.point_value < 27)::int AS medium_impact,
               COUNT(*) FILTER (WHERE ia.point_value < 3)::int AS low_impact
        FROM improvement_actions ia
        JOIN tenants t ON t.tenant_id = ia.tenant_id
        WHERE ia.snapshot_date = (SELECT MAX(snapshot_date) FROM improvement_actions)
          {dept_filter}
        """,
        params,
    )

    # Owner breakdown
    owner_breakdown = query(
        f"""
        SELECT ia.owner,
               COUNT(*)::int AS total,
               COUNT(*) FILTER (WHERE ia.implementation_status = 'implemented')::int AS implemented,
               COUNT(*) FILTER (WHERE ia.implementation_status != 'implemented')::int AS pending,
               SUM(ia.point_value)::int AS total_points
        FROM improvement_actions ia
        JOIN tenants t ON t.tenant_id = ia.tenant_id
        WHERE ia.snapshot_date = (SELECT MAX(snapshot_date) FROM improvement_actions)
          {dept_filter}
        GROUP BY ia.owner
        ORDER BY pending DESC
        """,
        params,
    )

    return {
        "actions": actions,
        "summary": summary_row or {},
        "owner_breakdown": owner_breakdown,
    }
