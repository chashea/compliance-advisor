"""
Compute enterprise rollup stats and surface the top cross-tenant compliance gaps.
Operates on Compliance Manager data — assessments and compliance scores.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../src/"))

from shared.sql_client import get_connection, set_admin_context


def compute_gaps(scores: list[dict]) -> dict:
    if not scores:
        return {"tenant_summaries": [], "enterprise_rollup": {}, "top_gaps": [],
                "weekly_changes": [], "department_rollup": []}

    total_current = sum(s.get("current_score", 0) for s in scores)
    total_max     = sum(s.get("max_score", 1)     for s in scores)
    avg_pct       = sum(s.get("compliance_pct", 0) for s in scores) / len(scores)

    enterprise_rollup = {
        "tenant_count":      len(scores),
        "avg_compliance_pct": round(avg_pct, 1),
        "min_compliance_pct": round(min(s.get("compliance_pct", 0) for s in scores), 1),
        "max_compliance_pct": round(max(s.get("compliance_pct", 0) for s in scores), 1),
        "lowest_tenant":     scores[0]["display_name"],   # already sorted ASC
    }

    conn = get_connection()
    try:
        # Cross-tenant aggregation — admin context required for RLS predicate
        set_admin_context(conn)
        cursor = conn.cursor()

        # Top assessment control gaps
        cursor.execute("""
            SELECT TOP 10
                control_name,
                control_family,
                regulation,
                implementation_status,
                COUNT(DISTINCT tenant_id) AS affected_tenants,
                AVG(points_gap)           AS avg_gap,
                SUM(points_gap)           AS total_gap
            FROM v_assessment_gaps
            GROUP BY control_name, control_family, regulation, implementation_status
            ORDER BY total_gap DESC
        """)
        cols = [col[0] for col in cursor.description]
        top_gaps = [dict(zip(cols, row)) for row in cursor.fetchall()]

        # Week-over-week compliance changes
        cursor.execute("""
            SELECT display_name, department, current_pct, prior_pct,
                   wow_change, trend_direction
            FROM v_compliance_weekly_change
            ORDER BY wow_change ASC
        """)
        cols = [col[0] for col in cursor.description]
        weekly_changes = [dict(zip(cols, row)) for row in cursor.fetchall()]

        # Department rollup for agency-level view
        cursor.execute("""
            SELECT department, tenant_count, avg_compliance_pct,
                   min_compliance_pct, max_compliance_pct,
                   total_assessments, total_failed_controls
            FROM v_compliance_department_rollup
            ORDER BY avg_compliance_pct ASC
        """)
        cols = [col[0] for col in cursor.description]
        department_rollup = [dict(zip(cols, row)) for row in cursor.fetchall()]

    finally:
        conn.close()

    return {
        "tenant_summaries": scores,
        "enterprise_rollup": enterprise_rollup,
        "top_gaps": top_gaps,
        "weekly_changes": weekly_changes,
        "department_rollup": department_rollup,
    }
