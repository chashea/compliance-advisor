"""
Microsoft Graph API client for Purview/security data collection.

Pulls data from:
- GET /v1.0/security/secureScores              — Microsoft Secure Score (daily)
- GET /v1.0/security/secureScoreControlProfiles — control-level details
- GET /v1.0/security/alerts_v2                  — security alerts
- GET /v1.0/security/incidents                  — security incidents
- GET /v1.0/identityProtection/riskyUsers       — risky users
- GET /v1.0/identity/conditionalAccess/policies — CA policies
- GET /v1.0/admin/serviceAnnouncement/healthOverviews — service health
"""

import logging
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _session(token: str) -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        respect_retry_after_header=True,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    return s


def _paginate(sess: requests.Session, url: str, max_pages: int = 10) -> list[dict]:
    """Follow @odata.nextLink pagination."""
    items = []
    page = 0
    while url and page < max_pages:
        resp = sess.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        items.extend(data.get("value", []))
        url = data.get("@odata.nextLink")
        page += 1
    return items


# ── Secure Score ──────────────────────────────────────────────────


def get_secure_scores(token: str, days: int = 7) -> list[dict[str, Any]]:
    """Return recent Secure Score snapshots (one per day)."""
    sess = _session(token)
    url = f"{GRAPH_BASE}/security/secureScores?$top={days}&$orderby=createdDateTime desc"

    try:
        items = _paginate(sess, url, max_pages=1)
    except requests.HTTPError as e:
        log.warning("secureScores failed: %s", e)
        return []

    scores = []
    for item in items:
        control_scores = item.get("controlScores", [])
        scores.append({
            "date": item.get("createdDateTime", "")[:10],
            "current_score": float(item.get("currentScore", 0)),
            "max_score": float(item.get("maxScore", 0)),
            "active_user_count": item.get("activeUserCount", 0),
            "licensed_user_count": item.get("licensedUserCount", 0),
            "enabled_services": item.get("enabledServices", []),
            "control_scores_count": len(control_scores),
            "controls_implemented": sum(
                1 for c in control_scores
                if c.get("scoreInPercentage", 0) == 100
            ),
        })

    log.info("Retrieved %d secure score snapshots", len(scores))
    return scores


# ── Secure Score Control Profiles ─────────────────────────────────


def get_control_profiles(token: str) -> list[dict[str, Any]]:
    """Return all Secure Score control profiles."""
    sess = _session(token)
    url = f"{GRAPH_BASE}/security/secureScoreControlProfiles"

    try:
        items = _paginate(sess, url)
    except requests.HTTPError as e:
        log.warning("secureScoreControlProfiles failed: %s", e)
        return []

    controls = []
    for item in items:
        if item.get("deprecated"):
            continue
        controls.append({
            "control_id": item.get("id", ""),
            "title": item.get("title", ""),
            "max_score": float(item.get("maxScore", 0)),
            "service": item.get("service", ""),
            "category": item.get("controlCategory", ""),
            "action_type": item.get("actionType", ""),
            "tier": item.get("tier", ""),
            "implementation_cost": item.get("implementationCost", ""),
            "user_impact": item.get("userImpact", ""),
        })

    log.info("Retrieved %d control profiles", len(controls))
    return controls


# ── Current Control Scores (from latest Secure Score) ─────────────


def get_control_scores(token: str) -> list[dict[str, Any]]:
    """Return per-control scores from the latest Secure Score snapshot."""
    sess = _session(token)
    url = f"{GRAPH_BASE}/security/secureScores?$top=1"

    try:
        resp = sess.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("value", [])
    except requests.HTTPError as e:
        log.warning("secureScores (for controls) failed: %s", e)
        return []

    if not items:
        return []

    control_scores = items[0].get("controlScores", [])
    results = []
    for cs in control_scores:
        results.append({
            "control_name": cs.get("controlName", ""),
            "category": cs.get("controlCategory", ""),
            "score": float(cs.get("score", 0)),
            "score_pct": float(cs.get("scoreInPercentage", 0)),
            "implementation_status": cs.get("implementationStatus", ""),
            "last_synced": cs.get("lastSynced", ""),
            "on": cs.get("on", ""),
            "description": cs.get("description", ""),
        })

    log.info("Retrieved %d control scores", len(results))
    return results


# ── Security Alerts ───────────────────────────────────────────────


def get_security_alerts(token: str) -> list[dict[str, Any]]:
    """Return active security alerts."""
    sess = _session(token)
    url = f"{GRAPH_BASE}/security/alerts_v2?$top=100&$orderby=createdDateTime desc"

    try:
        items = _paginate(sess, url, max_pages=5)
    except requests.HTTPError as e:
        log.warning("security alerts failed: %s", e)
        return []

    alerts = []
    for item in items:
        alerts.append({
            "alert_id": item.get("id", ""),
            "title": item.get("title", ""),
            "severity": item.get("severity", ""),
            "status": item.get("status", ""),
            "category": item.get("category", ""),
            "service_source": item.get("serviceSource", ""),
            "created": item.get("createdDateTime", ""),
            "resolved": item.get("resolvedDateTime", ""),
        })

    log.info("Retrieved %d security alerts", len(alerts))
    return alerts


# ── Security Incidents ────────────────────────────────────────────


def get_security_incidents(token: str) -> list[dict[str, Any]]:
    """Return security incidents."""
    sess = _session(token)
    url = f"{GRAPH_BASE}/security/incidents?$top=100"

    try:
        items = _paginate(sess, url, max_pages=5)
    except requests.HTTPError as e:
        log.warning("security incidents failed: %s", e)
        return []

    incidents = []
    for item in items:
        incidents.append({
            "incident_id": item.get("id", ""),
            "display_name": item.get("displayName", ""),
            "severity": item.get("severity", ""),
            "status": item.get("status", ""),
            "classification": item.get("classification", ""),
            "created": item.get("createdDateTime", ""),
            "last_update": item.get("lastUpdateDateTime", ""),
            "assigned_to": item.get("assignedTo", ""),
        })

    log.info("Retrieved %d security incidents", len(incidents))
    return incidents


# ── Risky Users ───────────────────────────────────────────────────


def get_risky_users(token: str) -> list[dict[str, Any]]:
    """Return users flagged as risky by Identity Protection."""
    sess = _session(token)
    url = f"{GRAPH_BASE}/identityProtection/riskyUsers?$top=100"

    try:
        items = _paginate(sess, url, max_pages=3)
    except requests.HTTPError as e:
        log.warning("risky users failed: %s", e)
        return []

    users = []
    for item in items:
        users.append({
            "user_id": item.get("id", ""),
            "user_display_name": item.get("userDisplayName", ""),
            "user_principal_name": item.get("userPrincipalName", ""),
            "risk_level": item.get("riskLevel", ""),
            "risk_state": item.get("riskState", ""),
            "risk_detail": item.get("riskDetail", ""),
            "risk_last_updated": item.get("riskLastUpdatedDateTime", ""),
        })

    log.info("Retrieved %d risky users", len(users))
    return users


# ── Service Health ────────────────────────────────────────────────


def get_service_health(token: str) -> list[dict[str, Any]]:
    """Return M365 service health overview."""
    sess = _session(token)
    url = f"{GRAPH_BASE}/admin/serviceAnnouncement/healthOverviews"

    try:
        resp = sess.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("value", [])
    except requests.HTTPError as e:
        log.warning("service health failed: %s", e)
        return []

    services = []
    for item in items:
        services.append({
            "service_name": item.get("service", ""),
            "status": item.get("status", ""),
        })

    log.info("Retrieved health for %d services", len(services))
    return services
