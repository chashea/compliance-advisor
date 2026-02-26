"""
HTTP API — exposes compliance advisor endpoints for dashboards, Teams bots,
and external consumers.

Routes:
    POST /api/advisor/ask            — Ask the compliance advisor a question
    POST /api/advisor/briefing       — Generate an executive briefing
    POST /api/advisor/trends         — Get score trends and week-over-week changes
    POST /api/advisor/departments    — Get department/agency rollup
    POST /api/advisor/status         — Health check
    POST /api/advisor/compliance     — Compliance Manager scores & trends
    POST /api/advisor/assessments    — Assessment summary & gaps
    POST /api/advisor/regulations    — Regulation coverage overview
    POST /api/advisor/actions        — Improvement actions with solution details
"""
import json
import logging
import os
import sys

import azure.functions as func

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from shared.sql_client import get_connection, set_admin_context


def main(req: func.HttpRequest) -> func.HttpResponse:
    action = req.route_params.get("action", "").lower()
    log = logging.getLogger("http_api")

    try:
        body = req.get_json() if req.get_body() else {}
    except ValueError:
        body = {}

    dispatch = {
        "ask":         _handle_ask,
        "briefing":    _handle_briefing,
        "trends":      _handle_trends,
        "departments": _handle_departments,
        "status":      _handle_status,
        "compliance":  _handle_compliance,
        "assessments": _handle_assessments,
        "regulations": _handle_regulations,
        "actions":     _handle_actions,
    }

    handler = dispatch.get(action)
    if not handler:
        return _json_response(
            {"error": f"Unknown action: {action}",
             "available_actions": list(dispatch.keys())},
            status_code=404,
        )

    try:
        result = handler(body, log)
        return _json_response(result)
    except ValueError as e:
        return _json_response({"error": str(e)}, status_code=400)
    except Exception as e:
        log.exception("Unhandled error in /advisor/%s", action)
        return _json_response({"error": "Internal server error"}, status_code=500)


# ── Handlers ──────────────────────────────────────────────────────────────────

def _handle_ask(body: dict, log: logging.Logger) -> dict:
    """Ask the compliance advisor agent a question (grounded via AI Search)."""
    question = body.get("question", "").strip()
    tenant_id = body.get("tenant_id", "").strip()
    cross_tenant = body.get("cross_tenant", False)

    if not question:
        raise ValueError("'question' is required")

    from shared.agents.compliance_advisor import ask_advisor

    result = ask_advisor(question, tenant_id=tenant_id, cross_tenant=cross_tenant)
    log.info("Advisor answered question: %s", question[:80])
    return result


def _handle_briefing(body: dict, log: logging.Logger) -> dict:
    """Generate a structured executive briefing via the Microsoft Foundry briefing agent."""
    department = body.get("department")

    from shared.agents.executive_briefing import generate_briefing

    try:
        result = generate_briefing(department=department)
        log.info("Generated executive briefing (department=%s)", department)
        return result
    except Exception:
        log.warning("Executive briefing agent unavailable, returning raw SQL data")

    # Fallback to raw SQL data if agent is not configured
    conn = get_connection()
    try:
        set_admin_context(conn)
        cursor = conn.cursor()

        if department:
            cursor.execute("""
                SELECT tenant_id, display_name, department, risk_tier,
                       score_pct, current_score, max_score, snapshot_date
                FROM v_latest_scores
                WHERE department = ?
                ORDER BY score_pct ASC
            """, department)
        else:
            cursor.execute("""
                SELECT tenant_id, display_name, department, risk_tier,
                       score_pct, current_score, max_score, snapshot_date
                FROM v_latest_scores
                ORDER BY score_pct ASC
            """)
        cols = [c[0] for c in cursor.description]
        scores = [dict(zip(cols, r)) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM v_department_rollup ORDER BY avg_score_pct ASC")
        cols = [c[0] for c in cursor.description]
        dept_rollup = [dict(zip(cols, r)) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT TOP 10 control_name, title, control_category,
                   points_gap, display_name, remediation_url
            FROM v_top_gaps ORDER BY points_gap DESC
        """)
        cols = [c[0] for c in cursor.description]
        top_gaps = [dict(zip(cols, r)) for r in cursor.fetchall()]

    finally:
        conn.close()

    return {"scores": scores, "department_rollup": dept_rollup, "top_gaps": top_gaps}


def _handle_trends(body: dict, log: logging.Logger) -> dict:
    """Return score trend data for a given tenant, department, or enterprise-wide."""
    tenant_id = body.get("tenant_id")
    department = body.get("department")
    days = min(body.get("days", 30), 90)

    conn = get_connection()
    try:
        set_admin_context(conn)
        cursor = conn.cursor()

        # Score trend over time
        if tenant_id:
            cursor.execute("""
                SELECT snapshot_date, score_pct, current_score, max_score
                FROM v_score_trend
                WHERE tenant_id = ?
                  AND snapshot_date >= DATEADD(DAY, ?, CAST(SYSUTCDATETIME() AS DATE))
                ORDER BY snapshot_date ASC
            """, tenant_id, -days)
        elif department:
            cursor.execute("""
                SELECT snapshot_date,
                       AVG(score_pct) AS avg_score_pct,
                       MIN(score_pct) AS min_score_pct,
                       MAX(score_pct) AS max_score_pct
                FROM v_score_trend
                WHERE department = ?
                  AND snapshot_date >= DATEADD(DAY, ?, CAST(SYSUTCDATETIME() AS DATE))
                GROUP BY snapshot_date
                ORDER BY snapshot_date ASC
            """, department, -days)
        else:
            cursor.execute("""
                SELECT snapshot_date,
                       AVG(score_pct) AS avg_score_pct,
                       MIN(score_pct) AS min_score_pct,
                       MAX(score_pct) AS max_score_pct,
                       COUNT(DISTINCT tenant_id) AS tenant_count
                FROM v_score_trend
                WHERE snapshot_date >= DATEADD(DAY, ?, CAST(SYSUTCDATETIME() AS DATE))
                GROUP BY snapshot_date
                ORDER BY snapshot_date ASC
            """, -days)

        cols = [c[0] for c in cursor.description]
        trend_data = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # Week-over-week changes
        if department:
            cursor.execute("""
                SELECT display_name, department, current_pct, prior_pct,
                       wow_change, trend_direction
                FROM v_weekly_change
                WHERE department = ?
                ORDER BY wow_change ASC
            """, department)
        else:
            cursor.execute("""
                SELECT display_name, department, current_pct, prior_pct,
                       wow_change, trend_direction
                FROM v_weekly_change
                ORDER BY wow_change ASC
            """)
        cols = [c[0] for c in cursor.description]
        weekly_changes = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # Category trends
        if department:
            cursor.execute("""
                SELECT control_category, snapshot_date, avg_score, avg_max_score, avg_gap
                FROM v_category_trend
                WHERE department = ?
                  AND snapshot_date >= DATEADD(DAY, ?, CAST(SYSUTCDATETIME() AS DATE))
                ORDER BY control_category, snapshot_date
            """, department, -days)
        else:
            cursor.execute("""
                SELECT control_category, snapshot_date,
                       AVG(avg_score) AS avg_score,
                       AVG(avg_max_score) AS avg_max_score,
                       AVG(avg_gap) AS avg_gap
                FROM v_category_trend
                WHERE snapshot_date >= DATEADD(DAY, ?, CAST(SYSUTCDATETIME() AS DATE))
                GROUP BY control_category, snapshot_date
                ORDER BY control_category, snapshot_date
            """, -days)
        cols = [c[0] for c in cursor.description]
        category_trends = [dict(zip(cols, r)) for r in cursor.fetchall()]

    finally:
        conn.close()

    return {
        "score_trend": trend_data,
        "weekly_changes": weekly_changes,
        "category_trends": category_trends,
        "filters": {"tenant_id": tenant_id, "department": department, "days": days},
    }


def _handle_departments(body: dict, log: logging.Logger) -> dict:
    """Return department/agency rollup with risk-tier breakdown."""
    conn = get_connection()
    try:
        set_admin_context(conn)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM v_department_rollup ORDER BY avg_score_pct ASC")
        cols = [c[0] for c in cursor.description]
        departments = [dict(zip(cols, r)) for r in cursor.fetchall()]

        cursor.execute("SELECT * FROM v_risk_tier_summary ORDER BY avg_score_pct ASC")
        cols = [c[0] for c in cursor.description]
        risk_tiers = [dict(zip(cols, r)) for r in cursor.fetchall()]
    finally:
        conn.close()

    return {
        "departments": departments,
        "risk_tiers": risk_tiers,
    }


def _handle_status(body: dict, log: logging.Logger) -> dict:
    """Quick health check showing tenant count and last sync times."""
    conn = get_connection()
    try:
        set_admin_context(conn)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) AS active_tenants,
                   MIN(last_synced_at) AS oldest_sync,
                   MAX(last_synced_at) AS newest_sync
            FROM tenants WHERE is_active = 1
        """)
        row = cursor.fetchone()
    finally:
        conn.close()

    return {
        "active_tenants": row[0],
        "oldest_sync": str(row[1]) if row[1] else None,
        "newest_sync": str(row[2]) if row[2] else None,
        "status": "healthy",
    }


def _handle_compliance(body: dict, log: logging.Logger) -> dict:
    """Return compliance scores, trends, and week-over-week changes."""
    department = body.get("department")
    days = min(body.get("days", 30), 90)

    conn = get_connection()
    try:
        set_admin_context(conn)
        cursor = conn.cursor()

        # Latest compliance scores
        if department:
            cursor.execute("""
                SELECT tenant_id, display_name, department, risk_tier,
                       compliance_pct, current_score, max_score, snapshot_date
                FROM v_latest_compliance_scores
                WHERE department = ?
                ORDER BY compliance_pct ASC
            """, department)
        else:
            cursor.execute("""
                SELECT tenant_id, display_name, department, risk_tier,
                       compliance_pct, current_score, max_score, snapshot_date
                FROM v_latest_compliance_scores
                ORDER BY compliance_pct ASC
            """)
        cols = [c[0] for c in cursor.description]
        latest_scores = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # Compliance trend over time
        if department:
            cursor.execute("""
                SELECT snapshot_date,
                       AVG(compliance_pct) AS avg_compliance_pct,
                       MIN(compliance_pct) AS min_compliance_pct,
                       MAX(compliance_pct) AS max_compliance_pct
                FROM v_compliance_trend
                WHERE department = ? AND category = 'overall'
                  AND snapshot_date >= DATEADD(DAY, ?, CAST(SYSUTCDATETIME() AS DATE))
                GROUP BY snapshot_date
                ORDER BY snapshot_date ASC
            """, department, -days)
        else:
            cursor.execute("""
                SELECT snapshot_date,
                       AVG(compliance_pct) AS avg_compliance_pct,
                       MIN(compliance_pct) AS min_compliance_pct,
                       MAX(compliance_pct) AS max_compliance_pct,
                       COUNT(DISTINCT tenant_id) AS tenant_count
                FROM v_compliance_trend
                WHERE category = 'overall'
                  AND snapshot_date >= DATEADD(DAY, ?, CAST(SYSUTCDATETIME() AS DATE))
                GROUP BY snapshot_date
                ORDER BY snapshot_date ASC
            """, -days)
        cols = [c[0] for c in cursor.description]
        trend_data = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # Weekly changes
        if department:
            cursor.execute("""
                SELECT display_name, department, current_pct, prior_pct,
                       wow_change, trend_direction
                FROM v_compliance_weekly_change
                WHERE department = ?
                ORDER BY wow_change ASC
            """, department)
        else:
            cursor.execute("""
                SELECT display_name, department, current_pct, prior_pct,
                       wow_change, trend_direction
                FROM v_compliance_weekly_change
                ORDER BY wow_change ASC
            """)
        cols = [c[0] for c in cursor.description]
        weekly_changes = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # Department compliance rollup
        cursor.execute("""
            SELECT * FROM v_compliance_department_rollup
            ORDER BY avg_compliance_pct ASC
        """)
        cols = [c[0] for c in cursor.description]
        dept_rollup = [dict(zip(cols, r)) for r in cursor.fetchall()]

    finally:
        conn.close()

    return {
        "latest_scores": latest_scores,
        "compliance_trend": trend_data,
        "weekly_changes": weekly_changes,
        "department_rollup": dept_rollup,
        "filters": {"department": department, "days": days},
    }


def _handle_assessments(body: dict, log: logging.Logger) -> dict:
    """Return assessment summaries and top control gaps."""
    department = body.get("department")
    regulation = body.get("regulation")
    top_n = min(body.get("top_gaps", 20), 50)

    conn = get_connection()
    try:
        set_admin_context(conn)
        cursor = conn.cursor()

        # Assessment summary
        query = "SELECT * FROM v_assessment_summary WHERE 1=1"
        params = []
        if department:
            query += " AND department = ?"
            params.append(department)
        if regulation:
            query += " AND regulation = ?"
            params.append(regulation)
        query += " ORDER BY compliance_score ASC"

        cursor.execute(query, *params)
        cols = [c[0] for c in cursor.description]
        assessments = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # Top gaps
        gap_query = f"SELECT TOP {top_n} * FROM v_assessment_gaps WHERE 1=1"
        gap_params = []
        if department:
            gap_query += " AND department = ?"
            gap_params.append(department)
        if regulation:
            gap_query += " AND regulation = ?"
            gap_params.append(regulation)
        gap_query += " ORDER BY points_gap DESC"

        cursor.execute(gap_query, *gap_params)
        cols = [c[0] for c in cursor.description]
        gaps = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # Control family breakdown
        family_query = """
            SELECT control_family,
                   COUNT(*) AS total_controls,
                   SUM(CASE WHEN implementation_status = 'implemented' THEN 1 ELSE 0 END) AS implemented,
                   SUM(CASE WHEN test_status = 'passed' THEN 1 ELSE 0 END) AS passed,
                   SUM(CASE WHEN test_status = 'failed' THEN 1 ELSE 0 END) AS failed,
                   AVG(max_score - ISNULL(score, 0)) AS avg_gap
            FROM assessment_controls ac
            JOIN assessments a ON a.tenant_id = ac.tenant_id AND a.assessment_id = ac.assessment_id
            JOIN tenants t ON t.tenant_id = ac.tenant_id
            WHERE t.is_active = 1 AND a.status = 'active'
        """
        fam_params = []
        if department:
            family_query += " AND t.department = ?"
            fam_params.append(department)
        if regulation:
            family_query += " AND a.regulation = ?"
            fam_params.append(regulation)
        family_query += " GROUP BY control_family ORDER BY avg_gap DESC"

        cursor.execute(family_query, *fam_params)
        cols = [c[0] for c in cursor.description]
        families = [dict(zip(cols, r)) for r in cursor.fetchall()]

    finally:
        conn.close()

    return {
        "assessments": assessments,
        "top_gaps": gaps,
        "control_families": families,
        "filters": {"department": department, "regulation": regulation},
    }


def _handle_regulations(body: dict, log: logging.Logger) -> dict:
    """Return regulation coverage across the enterprise."""
    conn = get_connection()
    try:
        set_admin_context(conn)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM v_regulation_coverage ORDER BY overall_pass_rate ASC")
        cols = [c[0] for c in cursor.description]
        regulations = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # Category compliance breakdown
        cursor.execute("SELECT * FROM v_compliance_category_trend ORDER BY avg_gap DESC")
        cols = [c[0] for c in cursor.description]
        category_trends = [dict(zip(cols, r)) for r in cursor.fetchall()]

    finally:
        conn.close()

    return {
        "regulations": regulations,
        "category_trends": category_trends,
    }


def _handle_actions(body: dict, log: logging.Logger) -> dict:
    """Return improvement actions with full solution/remediation details.

    Filters: department, regulation, status, owner, score_impact, top_n.
    Sorted by priority (highest-impact not-implemented first).
    """
    department = body.get("department")
    regulation = body.get("regulation")
    status_filter = body.get("status")         # notImplemented, planned, alternative
    owner_filter = body.get("owner")
    impact_filter = body.get("score_impact")    # high, medium, low
    top_n = min(body.get("top_n", 50), 200)

    conn = get_connection()
    try:
        set_admin_context(conn)
        cursor = conn.cursor()

        # ── Prioritized improvement actions ───────────────────────────────
        query = f"SELECT TOP {top_n} * FROM v_improvement_actions WHERE 1=1"
        params = []
        if department:
            query += " AND department = ?"
            params.append(department)
        if regulation:
            query += " AND regulation = ?"
            params.append(regulation)
        if status_filter:
            query += " AND implementation_status = ?"
            params.append(status_filter)
        if owner_filter:
            query += " AND owner = ?"
            params.append(owner_filter)
        if impact_filter:
            query += " AND score_impact = ?"
            params.append(impact_filter)
        query += " ORDER BY priority_rank ASC, points_gap DESC"

        cursor.execute(query, *params)
        cols = [c[0] for c in cursor.description]
        actions = [dict(zip(cols, r)) for r in cursor.fetchall()]

        # ── Summary stats ─────────────────────────────────────────────────
        stats_query = """
            SELECT
                COUNT(*) AS total_actions,
                SUM(CASE WHEN score_impact = 'high' THEN 1 ELSE 0 END) AS high_impact,
                SUM(CASE WHEN score_impact = 'medium' THEN 1 ELSE 0 END) AS medium_impact,
                SUM(CASE WHEN score_impact = 'low' THEN 1 ELSE 0 END) AS low_impact,
                SUM(points_gap) AS total_points_gap,
                COUNT(DISTINCT owner) AS distinct_owners,
                COUNT(DISTINCT regulation) AS distinct_regulations,
                COUNT(DISTINCT service) AS distinct_services
            FROM v_improvement_actions
            WHERE 1=1
        """
        stat_params = []
        if department:
            stats_query += " AND department = ?"
            stat_params.append(department)
        cursor.execute(stats_query, *stat_params)
        cols = [c[0] for c in cursor.description]
        row = cursor.fetchone()
        summary = dict(zip(cols, row)) if row else {}

        # ── Owner breakdown ───────────────────────────────────────────────
        owner_query = """
            SELECT owner,
                   COUNT(*) AS action_count,
                   SUM(points_gap) AS total_gap,
                   SUM(CASE WHEN score_impact = 'high' THEN 1 ELSE 0 END) AS high_impact
            FROM v_improvement_actions
            WHERE owner IS NOT NULL
        """
        owner_params = []
        if department:
            owner_query += " AND department = ?"
            owner_params.append(department)
        owner_query += " GROUP BY owner ORDER BY total_gap DESC"
        cursor.execute(owner_query, *owner_params)
        cols = [c[0] for c in cursor.description]
        owners = [dict(zip(cols, r)) for r in cursor.fetchall()]

    finally:
        conn.close()

    return {
        "actions": actions,
        "summary": summary,
        "owner_breakdown": owners,
        "filters": {
            "department": department,
            "regulation": regulation,
            "status": status_filter,
            "owner": owner_filter,
            "score_impact": impact_filter,
            "top_n": top_n,
        },
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _json_response(data: dict, status_code: int = 200) -> func.HttpResponse:
    """Return a JSON HTTP response with proper content type and date serialization."""
    return func.HttpResponse(
        body=json.dumps(data, default=str),
        status_code=status_code,
        mimetype="application/json",
    )
