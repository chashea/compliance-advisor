"""
Fetch the latest Compliance Manager scores for every active tenant from Azure SQL.
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../src/"))

from shared.sql_client import get_connection, set_admin_context


def fetch_scores() -> list[dict]:
    conn = get_connection()
    try:
        # Cross-tenant read — admin context required for RLS predicate
        set_admin_context(conn)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                tenant_id,
                display_name,
                department,
                risk_tier,
                snapshot_date,
                compliance_pct,
                current_score,
                max_score
            FROM v_latest_compliance_scores
            ORDER BY compliance_pct ASC
        """)
        cols = [col[0] for col in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    finally:
        conn.close()
