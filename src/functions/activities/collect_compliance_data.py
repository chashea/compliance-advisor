"""
Activity: pull Compliance Manager data for a single tenant and persist it.
Fetches compliance score, assessments, and assessment controls.
One instance of this runs per tenant, all in parallel.

Uses the msgraph-beta-sdk for typed access to Compliance Manager endpoints.
Falls back to raw HTTP if the SDK encounters issues.
"""
import logging
import sys
import os
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from shared.auth import get_graph_client, get_graph_token
from shared.graph_client import (
    # SDK-based (preferred)
    get_compliance_score_sdk,
    get_compliance_score_breakdown_sdk,
    get_compliance_assessments_sdk,
    get_assessment_controls_sdk,
    # Raw HTTP fallbacks
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
        # Create both an SDK client and a raw token so we can fall back
        client = get_graph_client(tenant)
        log.info("Created Graph SDK client for tenant %s", tenant_id)

        # Keep a raw token for fallback — lazily fetched only if needed
        _raw_token = None

        def _get_raw_token():
            nonlocal _raw_token
            if _raw_token is None:
                _raw_token = get_graph_token(tenant)
            return _raw_token

        # ── 1. Compliance Score ───────────────────────────────────────────
        score_data = get_compliance_score_sdk(client)
        if score_data is None:
            log.info("SDK score unavailable, trying raw HTTP fallback")
            score_data = get_compliance_score(_get_raw_token())

        score_count = 0
        if score_data:
            current = score_data.get("currentScore", score_data.get("current_score", 0))
            max_sc = score_data.get("maxScore", score_data.get("max_score", 0))
            score_count = 1
        else:
            current, max_sc = 0, 0

        # Category breakdown
        categories = get_compliance_score_breakdown_sdk(client)
        if not categories:
            categories = get_compliance_score_breakdown(_get_raw_token())
        cat_count = len(categories)

        # ── 2. Assessments ────────────────────────────────────────────────
        assessments = get_compliance_assessments_sdk(client)
        if not assessments:
            log.info("SDK assessments empty, trying raw HTTP fallback")
            assessments = get_compliance_assessments(_get_raw_token())
        log.info("Fetched %d assessments", len(assessments))

        # If we didn't get a direct compliance score, derive from assessments
        if not score_data and assessments:
            scores_list = [
                a.get("complianceScore", a.get("compliance_score", 0)) or 0
                for a in assessments
                if a.get("complianceScore", a.get("compliance_score")) is not None
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
                    cat.get("currentScore", cat.get("current_score", 0)),
                    cat.get("maxScore", cat.get("max_score", 0)),
                    cat.get("categoryName",
                            cat.get("category_name",
                                    cat.get("displayName",
                                            cat.get("display_name", "unknown")))),
                )

            # Upsert each assessment and its controls
            ctrl_count = 0
            for assessment in assessments:
                # Normalize SDK model keys to Graph API camelCase for sql_client
                normalized = _normalize_assessment(assessment)
                upsert_assessment(conn, tenant_id, normalized)

                assessment_id = assessment.get("id")
                if not assessment_id:
                    continue

                # Prefer SDK for controls, fall back to HTTP
                controls = get_assessment_controls_sdk(client, assessment_id)
                if not controls:
                    controls = get_assessment_controls(
                        _get_raw_token(), assessment_id)

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
    """
    Ensure assessment dict uses the camelCase keys that sql_client.upsert_assessment
    expects, regardless of whether data came from SDK (snake_case attrs) or raw HTTP.
    """
    return {
        "id":                    a.get("id"),
        "displayName":           a.get("displayName", a.get("display_name", "")),
        "description":           a.get("description"),
        "status":                a.get("status"),
        "regulation":            a.get("regulation"),
        "regulationName":        a.get("regulationName", a.get("regulation_name")),
        "complianceStandard":    a.get("complianceStandard", a.get("compliance_standard")),
        "complianceScore":       a.get("complianceScore", a.get("compliance_score")),
        "passedControls":        a.get("passedControls", a.get("passed_controls")),
        "failedControls":        a.get("failedControls", a.get("failed_controls")),
        "totalControls":         a.get("totalControls", a.get("total_controls")),
        "createdDateTime":       a.get("createdDateTime", a.get("created_date_time")),
        "lastModifiedDateTime":  a.get("lastModifiedDateTime",
                                       a.get("last_modified_date_time")),
    }


def _normalize_control(c: dict) -> dict:
    """
    Normalize control dict keys to the camelCase that sql_client expects.
    Includes solution/remediation fields from Compliance Manager.
    """
    return {
        "id":                    c.get("id"),
        "displayName":           c.get("displayName", c.get("display_name",
                                       c.get("controlName", c.get("control_name", "")))),
        "controlFamily":         c.get("controlFamily", c.get("control_family")),
        "controlCategory":       c.get("controlCategory", c.get("control_category")),
        "implementationStatus":  c.get("implementationStatus",
                                       c.get("implementation_status")),
        "testStatus":            c.get("testStatus", c.get("test_status")),
        "score":                 c.get("score"),
        "maxScore":              c.get("maxScore", c.get("max_score")),
        "scoreImpact":           c.get("scoreImpact", c.get("score_impact")),
        "owner":                 c.get("owner"),
        "actionUrl":             c.get("actionUrl", c.get("action_url")),
        # Solution / remediation detail fields
        "implementationDetails": c.get("implementationDetails",
                                       c.get("implementation_details")),
        "testPlan":              c.get("testPlan", c.get("test_plan")),
        "managementResponse":    c.get("managementResponse",
                                       c.get("management_response")),
        "evidenceOfCompletion":  c.get("evidenceOfCompletion",
                                       c.get("evidence_of_completion")),
        "service":               c.get("service"),
    }
