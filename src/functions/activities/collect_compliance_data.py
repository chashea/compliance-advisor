"""
Activity: pull Compliance Manager data for a single tenant and persist it.
Fetches compliance score, assessments, and assessment controls.
One instance of this runs per tenant, all in parallel.

M365 GCC connection: This is the only path that connects to M365 (GCC or commercial).
Uses Microsoft Graph global endpoints (login.microsoftonline.com, graph.microsoft.com).
Do not set GRAPH_NATIONAL_CLOUD for M365 GCC — it uses global endpoints.
"""
import logging
import sys
import os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from shared.auth import get_graph_token
from shared.graph_client import (
    get_compliance_score,
    get_compliance_score_breakdown,
    get_compliance_assessments,
    get_assessment_controls,
)
from shared.sql_client import (
    get_connection,
    set_tenant_context,
    upsert_compliance_score,
    upsert_assessment,
    upsert_assessment_control,
    mark_tenant_synced,
)


def main(tenant: dict) -> dict:
    tenant_id = tenant["tenant_id"]
    log = logging.getLogger(f"compliance:{tenant_id}")
    today = date.today().isoformat()

    try:
        # ── Authenticate ──────────────────────────────────────────────────
        token = get_graph_token(tenant)
        log.info("Acquired Graph token for tenant %s", tenant_id)

        # ── 1. Compliance Score ───────────────────────────────────────────
        score_data = get_compliance_score(token)

        score_count = 0
        if score_data:
            current = score_data.get("currentScore", 0)
            max_sc = score_data.get("maxScore", 0)
            score_count = 1
        else:
            current, max_sc = 0, 0

        # Category breakdown
        categories = get_compliance_score_breakdown(token)
        cat_count = len(categories)

        # ── 2. Assessments ────────────────────────────────────────────────
        assessments = get_compliance_assessments(token)
        log.info("Fetched %d assessments", len(assessments))

        # If we didn't get a direct compliance score, derive from assessments
        if not score_data and assessments:
            scores_list = [
                a.get("complianceScore", 0) or 0
                for a in assessments
                if a.get("complianceScore") is not None
            ]
            if scores_list:
                current = sum(scores_list) / len(scores_list)
                max_sc = 100.0
                score_count = 1

        # ── 3. Persist to SQL ─────────────────────────────────────────────
        conn = get_connection()
        try:
            set_tenant_context(conn, tenant_id)

            # Upsert overall compliance score
            if score_count > 0 or current > 0:
                upsert_compliance_score(conn, tenant_id, today,
                                        current, max_sc, "overall")

            # Upsert category scores
            for cat in categories:
                upsert_compliance_score(
                    conn, tenant_id, today,
                    cat.get("currentScore", 0),
                    cat.get("maxScore", 0),
                    cat.get("categoryName",
                            cat.get("displayName", "unknown")),
                )

            # Upsert each assessment and its controls
            ctrl_count = 0
            for assessment in assessments:
                normalized = _normalize_assessment(assessment)
                upsert_assessment(conn, tenant_id, normalized)

                assessment_id = assessment.get("id")
                if not assessment_id:
                    continue

                controls = get_assessment_controls(token, assessment_id)

                for ctrl in controls:
                    normalized_ctrl = _normalize_control(ctrl)
                    upsert_assessment_control(conn, tenant_id,
                                              assessment_id, normalized_ctrl)
                    ctrl_count += 1

            mark_tenant_synced(conn, tenant_id)
        finally:
            conn.close()

        return {
            "tenant_id": tenant_id,
            "success": True,
            "compliance_score": current,
            "assessments": len(assessments),
            "controls": ctrl_count,
            "categories": cat_count,
        }

    except Exception as exc:
        log.error("Failed to sync compliance data for %s: %s", tenant_id, exc)
        return {"tenant_id": tenant_id, "success": False, "error": str(exc)}


def _normalize_assessment(a: dict) -> dict:
    """Ensure assessment dict uses the camelCase keys that sql_client expects."""
    return {
        "id":                    a.get("id"),
        "displayName":           a.get("displayName", ""),
        "description":           a.get("description"),
        "status":                a.get("status"),
        "regulation":            a.get("regulation"),
        "regulationName":        a.get("regulationName"),
        "complianceStandard":    a.get("complianceStandard"),
        "complianceScore":       a.get("complianceScore"),
        "passedControls":        a.get("passedControls"),
        "failedControls":        a.get("failedControls"),
        "totalControls":         a.get("totalControls"),
        "createdDateTime":       a.get("createdDateTime"),
        "lastModifiedDateTime":  a.get("lastModifiedDateTime"),
    }


def _normalize_control(c: dict) -> dict:
    """Normalize control dict keys to the camelCase that sql_client expects."""
    return {
        "id":                    c.get("id"),
        "displayName":           c.get("displayName",
                                       c.get("controlName", "")),
        "controlFamily":         c.get("controlFamily"),
        "controlCategory":       c.get("controlCategory"),
        "implementationStatus":  c.get("implementationStatus"),
        "testStatus":            c.get("testStatus"),
        "score":                 c.get("score"),
        "maxScore":              c.get("maxScore"),
        "scoreImpact":           c.get("scoreImpact"),
        "owner":                 c.get("owner"),
        "actionUrl":             c.get("actionUrl"),
        "implementationDetails": c.get("implementationDetails"),
        "testPlan":              c.get("testPlan"),
        "managementResponse":    c.get("managementResponse"),
        "evidenceOfCompletion":  c.get("evidenceOfCompletion"),
        "service":               c.get("service"),
    }
