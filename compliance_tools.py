"""
Compliance Advisor — function tools for the Azure AI Foundry agent.

Each function queries the local SQLite database (data/compliance.db) via the
shared sql_client and returns a JSON string for the agent to interpret.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
from shared.ai_search_client import search_knowledge_documents
from shared.sql_client import get_connection


def _rows_to_dicts(cursor) -> list[dict]:
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def get_secure_score() -> str:
    """Return the tenant's current Microsoft Secure Score and 30-day trend.

    Queries v_latest_scores for the current score and v_score_trend for the
    past 30 days of daily snapshots. Returns score percentage, current/max
    points, and a trend list.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM v_latest_scores LIMIT 1")
        cols = [c[0] for c in cursor.description]
        row = cursor.fetchone()
        latest = dict(zip(cols, row)) if row else {}

        cursor.execute(
            """
            SELECT snapshot_date, score_pct, current_score, max_score
            FROM v_score_trend
            WHERE snapshot_date >= date('now', '-30 days')
            ORDER BY snapshot_date
        """
        )
        trend = _rows_to_dicts(cursor)

        return json.dumps({"latest": latest, "trend": trend}, default=str)
    finally:
        conn.close()


def get_top_gaps(count: int = 10) -> str:
    """Return the top control gaps ranked by unrealised points.

    Queries v_top_gaps and returns the controls with the largest gap between
    current score and maximum possible score. Includes control name, category,
    gap points, and remediation URL.

    Args:
        count: Number of gaps to return (default 10).
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT control_name, title, control_category,
                   score, max_score, points_gap, rank, action_type, remediation_url
            FROM v_top_gaps
            ORDER BY points_gap DESC
            LIMIT ?
        """,
            (int(count),),
        )
        gaps = _rows_to_dicts(cursor)
        return json.dumps(gaps, default=str)
    finally:
        conn.close()


def get_weekly_change() -> str:
    """Return week-over-week change for both Secure Score and Compliance Score.

    Queries v_weekly_change (Secure Score WoW) and v_compliance_weekly_change
    (Compliance Manager WoW). Returns current/prior percentages, delta, and
    trend direction (Improving / Stable / Declining) for each.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT tenant_id, display_name, current_pct, prior_pct,
                   wow_change, trend_direction
            FROM v_weekly_change
        """
        )
        secure_wow = _rows_to_dicts(cursor)

        cursor.execute(
            """
            SELECT tenant_id, display_name, current_pct, prior_pct,
                   wow_change, trend_direction
            FROM v_compliance_weekly_change
        """
        )
        compliance_wow = _rows_to_dicts(cursor)

        return json.dumps(
            {"secure_score_weekly": secure_wow, "compliance_score_weekly": compliance_wow},
            default=str,
        )
    finally:
        conn.close()


def get_compliance_score() -> str:
    """Return the tenant's current Compliance Manager score and 30-day trend.

    Queries v_latest_compliance_scores for the current overall compliance
    percentage and v_compliance_trend for the past 30 days of snapshots.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM v_latest_compliance_scores LIMIT 1")
        cols = [c[0] for c in cursor.description]
        row = cursor.fetchone()
        latest = dict(zip(cols, row)) if row else {}

        cursor.execute(
            """
            SELECT snapshot_date, compliance_pct, current_score, max_score, category
            FROM v_compliance_trend
            WHERE snapshot_date >= date('now', '-30 days')
              AND category = 'overall'
            ORDER BY snapshot_date
        """
        )
        trend = _rows_to_dicts(cursor)

        return json.dumps({"latest": latest, "trend": trend}, default=str)
    finally:
        conn.close()


def get_assessments(regulation: str | None = None) -> str:
    """Return a summary of Compliance Manager assessments.

    Queries v_assessment_summary. Optionally filters by regulation/framework
    name (case-insensitive substring match).

    Args:
        regulation: Optional regulation name to filter by (e.g. "NIST 800-53").
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if regulation:
            cursor.execute(
                """
                SELECT assessment_id, assessment_name, regulation, status,
                       compliance_score, passed_controls, failed_controls,
                       total_controls, pass_rate, last_modified
                FROM v_assessment_summary
                WHERE regulation LIKE ?
                ORDER BY pass_rate ASC
            """,
                (f"%{regulation}%",),
            )
        else:
            cursor.execute(
                """
                SELECT assessment_id, assessment_name, regulation, status,
                       compliance_score, passed_controls, failed_controls,
                       total_controls, pass_rate, last_modified
                FROM v_assessment_summary
                ORDER BY pass_rate ASC
            """
            )
        assessments = _rows_to_dicts(cursor)
        return json.dumps(assessments, default=str)
    finally:
        conn.close()


def get_improvement_actions(count: int = 10, regulation: str | None = None) -> str:
    """Return prioritised improvement actions from Compliance Manager.

    Queries v_improvement_actions. Actions are ordered by priority rank
    (not-implemented + high-impact first). Optionally filters by regulation.

    Args:
        count: Number of actions to return (default 10).
        regulation: Optional regulation name to filter by (e.g. "NIST 800-53").
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        if regulation:
            cursor.execute(
                """
                SELECT control_name, control_family, assessment_name, regulation,
                       implementation_status, test_status, score, max_score,
                       points_gap, score_impact, owner, action_url,
                       implementation_details, test_plan, service, priority_rank
                FROM v_improvement_actions
                WHERE regulation LIKE ?
                ORDER BY priority_rank ASC, points_gap DESC
                LIMIT ?
            """,
                (f"%{regulation}%", int(count)),
            )
        else:
            cursor.execute(
                """
                SELECT control_name, control_family, assessment_name, regulation,
                       implementation_status, test_status, score, max_score,
                       points_gap, score_impact, owner, action_url,
                       implementation_details, test_plan, service, priority_rank
                FROM v_improvement_actions
                ORDER BY priority_rank ASC, points_gap DESC
                LIMIT ?
            """,
                (int(count),),
            )
        actions = _rows_to_dicts(cursor)
        return json.dumps(actions, default=str)
    finally:
        conn.close()


def get_regulation_coverage() -> str:
    """Return pass rates and coverage statistics for each compliance framework.

    Queries v_regulation_coverage and returns total/passed/failed control counts
    and overall pass rate for every active regulation assessment.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT regulation, tenant_count, assessment_count,
                   avg_compliance_score, total_passed, total_failed,
                   total_controls, overall_pass_rate
            FROM v_regulation_coverage
            ORDER BY overall_pass_rate ASC
        """
        )
        coverage = _rows_to_dicts(cursor)
        return json.dumps(coverage, default=str)
    finally:
        conn.close()


def get_category_breakdown() -> str:
    """Return control category breakdown with average gap and compliance trend.

    Combines v_category_trend (Secure Score categories) and
    v_compliance_category_trend (Compliance Manager control families) to show
    where the largest gaps exist by category.
    """
    conn = get_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT control_category, snapshot_date,
                   avg_score, avg_max_score, avg_gap, tenant_count
            FROM v_category_trend
            WHERE snapshot_date >= date('now', '-30 days')
            ORDER BY avg_gap DESC
        """
        )
        secure_categories = _rows_to_dicts(cursor)

        cursor.execute(
            """
            SELECT control_family, regulation,
                   total_controls, implemented, passed, failed, avg_gap
            FROM v_compliance_category_trend
            ORDER BY avg_gap DESC
        """
        )
        compliance_categories = _rows_to_dicts(cursor)

        return json.dumps(
            {
                "secure_score_categories": secure_categories,
                "compliance_categories": compliance_categories,
            },
            default=str,
        )
    finally:
        conn.close()


def search_knowledge(query: str, top: int = 5, category: str | None = None) -> str:
    """Search compliance knowledge documents indexed in Azure AI Search.

    Use this for regulation text, policy narratives, and remediation guidance
    that is not represented in structured score tables.

    Args:
        query: Natural-language search query.
        top: Maximum number of documents to return (default 5, max 20).
        category: Optional document category filter (for example: "NIST",
            "ISO27001", "SOC2", "RemediationGuide").
    """
    if not query or not query.strip():
        raise ValueError("'query' is required")

    docs = search_knowledge_documents(query=query.strip(), top=top, category=category)
    return json.dumps({"results": docs}, default=str)
