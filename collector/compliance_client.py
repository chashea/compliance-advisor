"""
Compliance Manager portal API client.

Calls the Compliance Manager portal APIs directly:
- GET /api/ComplianceScore       — overall compliance score
- GET /api/Assessments           — all assessments
- GET /api/ImprovementActions    — detailed improvement actions

All scores are passed through as-is — no custom formulas.
Point values (27/9/3/1) are computed per Microsoft's published methodology.
"""

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

# Point values per Microsoft's Compliance Manager scoring methodology
# https://learn.microsoft.com/en-us/purview/compliance-manager-scoring
POINT_VALUES = {
    ("preventative", True): 27,   # Preventative mandatory
    ("preventative", False): 9,   # Preventative discretionary
    ("detective", True): 3,       # Detective mandatory
    ("detective", False): 1,      # Detective discretionary
    ("corrective", True): 3,      # Corrective mandatory
    ("corrective", False): 1,     # Corrective discretionary
}


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _compute_point_value(category: str, is_mandatory: bool) -> int:
    """Compute the point value for an improvement action."""
    key = (category.lower().strip(), is_mandatory)
    return POINT_VALUES.get(key, 1)


# ── Compliance Score ──────────────────────────────────────────────


def get_compliance_score(base_url: str, token: str) -> dict[str, float]:
    """Return the tenant-level Compliance Manager score.

    Returns:
        {"current_score": float, "max_score": float}

    Falls back to self-calculation from improvement actions if needed.
    """
    sess = _session()
    url = f"{base_url}/api/ComplianceScore"

    try:
        resp = sess.get(url, headers=_headers(token), timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return {
            "current_score": float(data.get("currentScore", data.get("achievedScore", 0))),
            "max_score": float(data.get("maxScore", data.get("possibleScore", 0))),
        }
    except requests.HTTPError as e:
        log.warning("ComplianceScore endpoint failed (%s), will derive from actions", e)
        return {"current_score": 0.0, "max_score": 0.0}


# ── Assessments ───────────────────────────────────────────────────


def get_assessments(base_url: str, token: str) -> list[dict[str, Any]]:
    """Return all Compliance Manager assessments.

    Returns list of:
        {
            "assessment_id": str,
            "assessment_name": str,
            "regulation": str,
            "compliance_score": float,
            "passed_controls": int,
            "failed_controls": int,
            "total_controls": int,
        }
    """
    sess = _session()
    url = f"{base_url}/api/Assessments"

    assessments = []
    try:
        resp = sess.get(url, headers=_headers(token), timeout=30)
        resp.raise_for_status()
        data = resp.json()

        items = data if isinstance(data, list) else data.get("value", data.get("assessments", []))

        for item in items:
            passed = int(item.get("passedControls", item.get("passedControlCount", 0)))
            failed = int(item.get("failedControls", item.get("failedControlCount", 0)))
            total = int(item.get("totalControls", item.get("totalControlCount", 0)))

            assessments.append({
                "assessment_id": str(item.get("id", "")),
                "assessment_name": item.get("displayName", item.get("name", "")),
                "regulation": item.get(
                    "complianceStandard",
                    item.get("regulationName", item.get("regulation", "")),
                ),
                "compliance_score": float(item.get("complianceScore", item.get("score", 0))),
                "passed_controls": passed,
                "failed_controls": failed,
                "total_controls": total,
            })
    except requests.HTTPError as e:
        log.warning("Assessments query failed: %s", e)

    log.info("Retrieved %d assessments", len(assessments))
    return assessments


# ── Improvement Actions (detailed) ───────────────────────────────


def get_improvement_actions_detail(base_url: str, token: str) -> list[dict[str, Any]]:
    """Return detailed improvement actions with scoring data.

    Returns list of:
        {
            "action_id": str,
            "control_name": str,
            "control_family": str,
            "regulation": str,
            "implementation_status": str,
            "test_status": str,
            "action_category": str,
            "is_mandatory": bool,
            "point_value": int,
            "owner": str,
            "service": str,
            "description": str,
            "remediation_steps": str,
        }
    """
    sess = _session()
    url = f"{base_url}/api/ImprovementActions"

    actions = []
    try:
        resp = sess.get(url, headers=_headers(token), timeout=60)
        resp.raise_for_status()
        data = resp.json()

        items = data if isinstance(data, list) else data.get("value", data.get("improvementActions", []))

        for item in items:
            category = (
                item.get("actionCategory", item.get("category", ""))
                .lower()
                .replace(" ", "")
            )
            is_mandatory = item.get("isMandatory", not item.get("isDiscretionary", False))
            point_value = _compute_point_value(category, is_mandatory)

            # Use the API's score if available, otherwise computed
            api_points = item.get("maxScore", item.get("pointsPossible", 0))
            if api_points and api_points > 0:
                point_value = int(api_points)

            impl_status = (
                item.get("implementationStatus", item.get("status", ""))
                .replace(" ", "")
            )
            # Normalize common status values
            status_map = {
                "notstarted": "notImplemented",
                "inprogress": "planned",
                "completed": "implemented",
                "notimplemented": "notImplemented",
            }
            impl_status = status_map.get(impl_status.lower(), impl_status)

            actions.append({
                "action_id": str(item.get("id", "")),
                "control_name": item.get("title", item.get("displayName", "")),
                "control_family": item.get(
                    "controlFamily",
                    item.get("complianceCategory", item.get("category", "")),
                ),
                "regulation": item.get("regulation", item.get("regulationName", "")),
                "implementation_status": impl_status,
                "test_status": item.get("testStatus", item.get("verificationStatus", "")),
                "action_category": category,
                "is_mandatory": is_mandatory,
                "point_value": point_value,
                "owner": item.get("assignedTo", item.get("owner", "")),
                "service": item.get("service", item.get("productService", "")),
                "description": item.get("description", ""),
                "remediation_steps": item.get(
                    "implementationInstructions",
                    item.get("remediationSteps", item.get("howToImplement", "")),
                ),
            })
    except requests.HTTPError as e:
        log.warning("ImprovementActions query failed: %s", e)

    log.info("Retrieved %d improvement actions", len(actions))
    return actions


def compute_score_from_actions(actions: list[dict]) -> dict[str, float]:
    """Self-calculate compliance score from improvement actions.

    Used as a fallback when the ComplianceScore endpoint is unavailable.

    Returns:
        {"current_score": float, "max_score": float}
    """
    max_score = sum(a.get("point_value", 0) for a in actions)
    current_score = sum(
        a.get("point_value", 0)
        for a in actions
        if a.get("implementation_status") == "implemented"
    )
    return {"current_score": float(current_score), "max_score": float(max_score)}
