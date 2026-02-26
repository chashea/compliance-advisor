"""
Microsoft Graph API client — Compliance Manager & Secure Score.

Uses raw HTTP calls to Microsoft Graph Beta for Compliance Manager endpoints
and v1.0 for Secure Score. Includes retry logic with exponential backoff for
429 / 5xx responses.

M365 GCC uses global endpoints. Set GRAPH_NATIONAL_CLOUD=usgovernment only for
GCC High/DoD to use https://graph.microsoft.us.
"""
import logging
import os
from typing import Generator

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# GCC High/DoD use graph.microsoft.us (not M365 GCC — that uses global)
_graph_cloud = os.environ.get("GRAPH_NATIONAL_CLOUD", "").strip().lower()
_is_usgov = _graph_cloud in ("usgovernment", "usgov", "gcc", "gcc high", "dod")
_graph_host = "https://graph.microsoft.us" if _is_usgov else "https://graph.microsoft.com"
GRAPH_BASE = f"{_graph_host}/v1.0"
GRAPH_BETA = f"{_graph_host}/beta"
MAX_DAYS   = 90
log        = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# HTTP helpers with retry
# ═════════════════════════════════════════════════════════════════════════════

def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def _get(url: str, token: str) -> dict:
    resp = _session().get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _paginate(url: str, token: str) -> Generator[dict, None, None]:
    """Follow @odata.nextLink pagination and yield every item."""
    while url:
        data = _get(url, token)
        yield from data.get("value", [])
        url = data.get("@odata.nextLink")


# ═════════════════════════════════════════════════════════════════════════════
# Secure Score (v1.0)
# ═════════════════════════════════════════════════════════════════════════════

def get_secure_scores(token: str, days: int = MAX_DAYS) -> list[dict]:
    """Return up to `days` daily Secure Score snapshots, newest first."""
    if not isinstance(days, int) or not (1 <= days <= MAX_DAYS):
        raise ValueError(f"days must be an integer between 1 and {MAX_DAYS}")
    url = f"{GRAPH_BASE}/security/secureScores?$top={days}"
    return list(_paginate(url, token))


def get_control_profiles(token: str) -> list[dict]:
    """Return the full Secure Score control profile catalog for this tenant."""
    url = f"{GRAPH_BASE}/security/secureScoreControlProfiles"
    return list(_paginate(url, token))


# ═════════════════════════════════════════════════════════════════════════════
# Compliance Manager (beta)
# ═════════════════════════════════════════════════════════════════════════════

def get_compliance_assessments(token: str) -> list[dict]:
    """Return all Compliance Manager assessments."""
    preferred = f"{GRAPH_BETA}/security/complianceManager/assessments"
    try:
        return list(_paginate(preferred, token))
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            log.warning("complianceManager/assessments not available, "
                        "trying alternative endpoint")
            alt = f"{GRAPH_BETA}/compliance/complianceManagement/assessments"
            try:
                return list(_paginate(alt, token))
            except requests.HTTPError:
                log.warning("No Compliance Manager assessment API available")
                return []
        raise


def get_assessment_controls(token: str, assessment_id: str) -> list[dict]:
    """Return all controls for a specific assessment.
    Includes solution/remediation fields when available from the API."""
    select = ("id,displayName,controlFamily,controlCategory,"
              "implementationStatus,testStatus,score,maxScore,owner,actionUrl,"
              "implementationDetails,testPlan,managementResponse,"
              "evidenceOfCompletion,service,scoreImpact")
    url = (f"{GRAPH_BETA}/security/complianceManager/assessments/"
           f"{assessment_id}/controls?$select={select}")
    try:
        return list(_paginate(url, token))
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            alt = (f"{GRAPH_BETA}/compliance/complianceManagement/assessments/"
                   f"{assessment_id}/controls?$select={select}")
            try:
                return list(_paginate(alt, token))
            except requests.HTTPError:
                log.warning("Could not fetch controls for assessment %s",
                            assessment_id)
                return []
        raise


def get_compliance_score(token: str) -> dict | None:
    """Return the tenant's overall compliance score."""
    url = f"{GRAPH_BETA}/security/complianceManager/complianceScore"
    try:
        return _get(url, token)
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            log.info("complianceScore endpoint unavailable")
            return None
        raise


def get_compliance_score_breakdown(token: str) -> list[dict]:
    """Return compliance score by category."""
    url = f"{GRAPH_BETA}/security/complianceManager/complianceScore/categories"
    try:
        return list(_paginate(url, token))
    except requests.HTTPError as e:
        if e.response is not None and e.response.status_code in (404, 400):
            log.info("Compliance score category breakdown not available")
            return []
        raise
