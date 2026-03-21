"""
Microsoft Graph API client for compliance workload data collection.

Pulls data from:
- GET  /v1.0/security/cases/ediscoveryCases                     — eDiscovery cases
- GET  /beta/security/informationProtection/sensitivityLabels    — sensitivity labels
- GET  /v1.0/security/labels/retentionLabels                     — retention labels
- GET  /v1.0/security/triggers/retentionEvents                   — retention events
- GET  /v1.0/security/triggerTypes/retentionEventTypes           — retention event types
- POST /v1.0/security/auditLog/queries + GET records             — audit log (async)
- GET  /v1.0/security/alerts_v2?$filter=serviceSource             — DLP + IRM alerts
- POST /v1.0/dataSecurityAndGovernance/protectionScopes/compute  — protection scopes
- POST /v1.0/users/{id}/dataSecurityAndGovernance/processContent — user content policies
- GET  /beta/security/informationProtection/dataLossPreventionPolicies — DLP policies
- GET  /beta/security/insiderRiskManagement/policies              — IRM policies
- GET  /beta/dataClassification/sensitiveTypes                    — sensitive info types
- GET  /beta/security/complianceManagement/assessments            — compliance assessments

Required Microsoft Graph Application permissions:
- eDiscovery.Read.All                     — eDiscovery cases
- InformationProtectionPolicy.Read.All    — sensitivity labels (beta endpoint)
- SensitivityLabel.Read                   — sensitivity labels (v1.0 fallback)
- RecordsManagement.Read.All              — retention labels (delegated only!), retention events, retention event types
- AuditLogsQuery.Read.All                 — audit log queries
- SecurityAlert.Read.All                  — DLP + IRM alerts (alerts_v2)
- DataSecurityAndGovernance.Read.All      — protection scopes, user content policies
- SecurityEvents.Read.All                 — Secure Score + improvement actions
- SubjectRightsRequest.Read.All           — subject rights requests
- CommunicationCompliance.Read.All        — communication compliance policies
- InformationBarrierPolicy.Read.All       — information barrier policies
- InsiderRiskManagement.Read.All          — IRM policies
- ComplianceManager.Read.All              — compliance assessments
- User.Read.All                           — user enumeration for content policies

NOTE: Retention labels API does NOT support application permissions.
      The collector will attempt the call but it may return 403 with app-only auth.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

log = logging.getLogger(__name__)

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_BETA = "https://graph.microsoft.com/beta"


def _session(token: str) -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
        respect_retry_after_header=True,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update(
        {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
    )
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


def _log_api_error(label: str, exc: requests.exceptions.RequestException, hint: str = "") -> None:
    """Log a Graph API failure with HTTP status and permission hints."""
    status = getattr(getattr(exc, "response", None), "status_code", None)
    body = ""
    try:
        body = exc.response.text[:500] if exc.response is not None else ""
    except Exception:
        pass

    parts = [f"{label} failed"]
    if status:
        parts.append(f"HTTP {status}")
    parts.append(str(exc))
    if status in (401, 403) and hint:
        parts.append(f"Required permission: {hint}")
    log.warning(" — ".join(parts))
    if body:
        log.debug("%s response body: %s", label, body)


# ── eDiscovery ────────────────────────────────────────────────────


def get_ediscovery_cases(token: str) -> list[dict[str, Any]]:
    """Return eDiscovery cases."""
    sess = _session(token)
    url = f"{GRAPH_BASE}/security/cases/ediscoveryCases"

    try:
        items = _paginate(sess, url)
    except requests.exceptions.RequestException as e:
        _log_api_error("ediscoveryCases", e, "eDiscovery.Read.All")
        return []

    cases = []
    for item in items:
        custodians = item.get("custodians", [])
        cases.append(
            {
                "case_id": item.get("id", ""),
                "display_name": item.get("displayName", ""),
                "status": item.get("status", ""),
                "created": item.get("createdDateTime", ""),
                "closed": item.get("closedDateTime", ""),
                "external_id": item.get("externalId", ""),
                "custodian_count": len(custodians) if isinstance(custodians, list) else 0,
            }
        )

    log.info("Retrieved %d eDiscovery cases", len(cases))
    return cases


# ── Information Protection (sensitivity labels) ───────────────────


def get_sensitivity_labels(token: str) -> list[dict[str, Any]]:
    """Return sensitivity labels.

    Tries endpoints in order:
    1. beta /security/informationProtection/sensitivityLabels
       (InformationProtectionPolicy.Read.All — Commercial only)
    2. v1.0 /security/dataSecurityAndGovernance/sensitivityLabels
       (SensitivityLabel.Read — Commercial + GCC L4)
    """
    sess = _session(token)

    # Try beta informationProtection endpoint first
    url = f"{GRAPH_BETA}/security/informationProtection/sensitivityLabels"
    try:
        items = _paginate(sess, url)
        if items:
            log.info("Retrieved %d sensitivity labels (beta/informationProtection)", len(items))
            return _map_sensitivity_labels(items)
    except requests.exceptions.RequestException as e:
        _log_api_error("sensitivityLabels (beta/informationProtection)", e, "InformationProtectionPolicy.Read.All")

    # Fallback: v1.0 dataSecurityAndGovernance endpoint
    url = f"{GRAPH_BASE}/security/dataSecurityAndGovernance/sensitivityLabels"
    try:
        items = _paginate(sess, url)
    except requests.exceptions.RequestException as e:
        _log_api_error("sensitivityLabels (v1.0/dataSecurityAndGovernance)", e, "SensitivityLabel.Read")
        return []

    labels = _map_sensitivity_labels(items)
    log.info("Retrieved %d sensitivity labels (v1.0/dataSecurityAndGovernance)", len(labels))
    return labels


def _map_sensitivity_labels(items: list[dict]) -> list[dict[str, Any]]:
    """Map Graph API sensitivity label response to our schema."""
    labels = []
    for item in items:
        labels.append(
            {
                "label_id": item.get("id", ""),
                "name": item.get("name", "") or item.get("displayName", ""),
                "description": item.get("description", ""),
                "color": item.get("color", ""),
                "is_active": item.get("isActive", item.get("isEnabled", True)),
                "parent_id": item.get("parent", {}).get("id", "") if isinstance(item.get("parent"), dict) else "",
                "priority": item.get("priority", 0),
                "tooltip": item.get("toolTip", "") or item.get("tooltip", ""),
            }
        )
    return labels


# ── Records Management (retention labels) ─────────────────────────


def get_retention_labels(token: str) -> list[dict[str, Any]]:
    """Return retention labels.

    Required Graph permission: RecordsManagement.Read.All (delegated only).
    NOTE: This API does NOT support application permissions per Microsoft docs.
    With app-only (client credentials) auth, this call will return 403.
    """
    sess = _session(token)
    url = f"{GRAPH_BASE}/security/labels/retentionLabels"

    try:
        items = _paginate(sess, url)
    except requests.exceptions.RequestException as e:
        _log_api_error(
            "retentionLabels", e,
            "RecordsManagement.Read.All (NOTE: delegated only — app-only auth is not supported by this API)"
        )
        return []

    labels = []
    for item in items:
        duration = item.get("retentionDuration", {})
        duration_str = ""
        if isinstance(duration, dict):
            duration_str = duration.get("period", "") or str(duration.get("days", ""))
        elif duration:
            duration_str = str(duration)

        descriptors = item.get("descriptors") or {}
        labels.append(
            {
                "label_id": item.get("id", ""),
                "display_name": item.get("displayName", ""),
                "retention_duration": duration_str,
                "retention_trigger": item.get("retentionTrigger", ""),
                "action_after_retention": item.get("actionAfterRetentionPeriod", ""),
                "is_in_use": item.get("isInUse", False),
                "status": item.get("status", ""),
                "file_plan_authority": (descriptors.get("authorityTemplate") or {}).get("displayName", ""),
                "file_plan_citation": (descriptors.get("citationTemplate") or {}).get("displayName", ""),
                "file_plan_department": (descriptors.get("departmentTemplate") or {}).get("displayName", ""),
                "file_plan_category": (descriptors.get("categoryTemplate") or {}).get("displayName", ""),
                "file_plan_subcategory": (descriptors.get("subcategoryTemplate") or {}).get("displayName", ""),
            }
        )

    log.info("Retrieved %d retention labels", len(labels))
    return labels


# ── Records Management (retention events) ─────────────────────────


def get_retention_events(token: str) -> list[dict[str, Any]]:
    """Return retention events.

    Required Graph permission (Application): RecordsManagement.Read.All
    """
    sess = _session(token)
    url = f"{GRAPH_BASE}/security/triggers/retentionEvents"

    try:
        items = _paginate(sess, url)
    except requests.exceptions.RequestException as e:
        _log_api_error("retentionEvents", e, "RecordsManagement.Read.All")
        return []

    events = []
    for item in items:
        event_type = item.get("eventType", {})
        event_type_name = ""
        if isinstance(event_type, dict):
            event_type_name = event_type.get("displayName", "")
        elif event_type:
            event_type_name = str(event_type)

        events.append(
            {
                "event_id": item.get("id", ""),
                "display_name": item.get("displayName", ""),
                "event_type": event_type_name,
                "created": item.get("createdDateTime", ""),
                "event_status": (
                    item.get("eventStatus", {}).get("status", "")
                    if isinstance(item.get("eventStatus"), dict)
                    else str(item.get("eventStatus", ""))
                ),
            }
        )

    log.info("Retrieved %d retention events", len(events))
    return events


# ── Audit Log (async query API) ───────────────────────────────────


def get_audit_log_records(token: str, days: int = 1) -> list[dict[str, Any]]:
    """Create an audit log query, poll until complete, then fetch records."""
    sess = _session(token)
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    query_body = {
        "displayName": f"compliance-advisor-{now.strftime('%Y%m%d%H%M%S')}",
        "filterStartDateTime": start,
        "filterEndDateTime": end,
        "recordTypeFilters": [
            "dlpRule",
            "retentionPolicy",
            "sensitivityLabelAction",
            "sensitivityLabeledFileAction",
            "eDDiscovery",
            "complianceDLPExchange",
            "complianceDLPSharePoint",
            "complianceDLPSharePointClassification",
        ],
    }

    # Create query
    try:
        resp = sess.post(f"{GRAPH_BASE}/security/auditLog/queries", json=query_body, timeout=30)
        resp.raise_for_status()
        query_data = resp.json()
        query_id = query_data.get("id", "")
    except requests.exceptions.RequestException as e:
        _log_api_error("auditLog query creation", e, "AuditLogsQuery.Read.All")
        return []

    if not query_id:
        log.warning("auditLog query returned no id")
        return []

    # Poll for completion with exponential backoff
    poll_url = f"{GRAPH_BASE}/security/auditLog/queries/{query_id}"
    wait = 2
    max_wait = 60
    total_waited = 0
    max_total = 300  # 5 minutes max

    while total_waited < max_total:
        time.sleep(wait)
        total_waited += wait

        try:
            resp = sess.get(poll_url, timeout=30)
            resp.raise_for_status()
            status_data = resp.json()
        except requests.exceptions.RequestException as e:
            _log_api_error("auditLog query poll", e, "AuditLogsQuery.Read.All")
            return []

        status = status_data.get("status", "")
        if status == "succeeded":
            break
        if status in ("failed", "cancelled"):
            log.warning("auditLog query %s: %s", status, query_id)
            return []

        wait = min(wait * 2, max_wait)

    else:
        log.warning("auditLog query timed out after %ds: %s", max_total, query_id)
        return []

    # Fetch records
    records_url = f"{poll_url}/records"
    try:
        items = _paginate(sess, records_url)
    except requests.exceptions.RequestException as e:
        _log_api_error("auditLog records fetch", e, "AuditLogsQuery.Read.All")
        return []

    records = []
    for item in items:
        records.append(
            {
                "record_id": item.get("id", ""),
                "record_type": item.get("auditLogRecordType", ""),
                "operation": item.get("operation", ""),
                "service": item.get("service", ""),
                "user_id": item.get("userPrincipalName", "") or item.get("userId", ""),
                "created": item.get("createdDateTime", ""),
                "ip_address": item.get("clientIP", "") or item.get("ipAddress", ""),
                "client_app": item.get("clientAppUsed", ""),
                "result_status": item.get("resultStatus", ""),
            }
        )

    log.info("Retrieved %d audit log records", len(records))
    return records


# ── DLP Alerts ────────────────────────────────────────────────────


def _alerts_v2(token: str, service_source: str, label: str) -> list[dict[str, Any]]:
    """Return alerts from /security/alerts_v2 filtered by serviceSource."""
    sess = _session(token)
    url = (
        f"{GRAPH_BASE}/security/alerts_v2"
        f"?$filter=serviceSource eq '{service_source}'"
        "&$top=100&$orderby=createdDateTime desc"
    )

    try:
        items = _paginate(sess, url, max_pages=5)
    except requests.exceptions.RequestException as e:
        _log_api_error(f"{label} alerts_v2", e, "SecurityAlert.Read.All")
        return []

    alerts = []
    for item in items:
        alerts.append(
            {
                "alert_id": item.get("id", ""),
                "title": item.get("title", ""),
                "severity": item.get("severity", ""),
                "status": item.get("status", ""),
                "category": item.get("category", ""),
                "created": item.get("createdDateTime", ""),
                "resolved": item.get("resolvedDateTime", ""),
                "policy_name": item.get("alertPolicyId", ""),
                "description": item.get("description", ""),
                "assigned_to": item.get("assignedTo", ""),
            }
        )

    log.info("Retrieved %d %s alerts", len(alerts), label)
    return alerts


def get_dlp_alerts(token: str) -> list[dict[str, Any]]:
    """Return DLP alerts (alerts_v2, serviceSource=microsoftDataLossPrevention)."""
    return _alerts_v2(token, "microsoftDataLossPrevention", "DLP")


# ── Insider Risk Management alerts ────────────────────────────────


def get_irm_alerts(token: str) -> list[dict[str, Any]]:
    """Return IRM alerts (alerts_v2, serviceSource=microsoftInsiderRiskManagement)."""
    return _alerts_v2(token, "microsoftInsiderRiskManagement", "IRM")


# ── Data Security & Governance (protection scopes) ────────────────


def get_protection_scopes(token: str) -> list[dict[str, Any]]:
    """Return tenant-level protection scopes."""
    sess = _session(token)
    url = f"{GRAPH_BASE}/dataSecurityAndGovernance/protectionScopes/compute"

    try:
        resp = sess.post(url, json={}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        _log_api_error("protectionScopes", e, "DataSecurityAndGovernance.Read.All")
        return []

    items = data.get("value", []) if isinstance(data.get("value"), list) else [data] if data else []

    scopes = []
    for item in items:
        locations = item.get("monitoredLocations", [])
        location_str = ", ".join(locations) if isinstance(locations, list) else str(locations or "")

        activity_types = item.get("activityTypes", [])
        activity_str = ", ".join(activity_types) if isinstance(activity_types, list) else str(activity_types or "")

        scopes.append(
            {
                "scope_type": item.get("policyType", "") or item.get("@odata.type", ""),
                "execution_mode": item.get("executionMode", ""),
                "locations": location_str,
                "activity_types": activity_str,
            }
        )

    log.info("Retrieved %d protection scopes", len(scopes))
    return scopes


# ── Secure Score ──────────────────────────────────────────────────


def get_secure_scores(token: str) -> list[dict[str, Any]]:
    """Return the most recent Secure Score snapshot with Data category breakdown."""
    sess = _session(token)

    try:
        resp = sess.get(f"{GRAPH_BASE}/security/secureScores?$top=1", timeout=30)
        resp.raise_for_status()
        items = resp.json().get("value", [])
    except requests.exceptions.RequestException as e:
        _log_api_error("secureScores", e, "SecurityEvents.Read.All")
        return []

    if not items:
        return []

    # Build per-control current score lookup from the snapshot
    item = items[0]
    control_scores: dict[str, float] = {
        cs["controlName"]: float(cs.get("score") or 0)
        for cs in item.get("controlScores", [])
        if isinstance(cs, dict) and cs.get("controlName")
    }

    # Fetch Data category control profiles to compute Data score
    data_current = 0.0
    data_max = 0.0
    try:
        profiles = _paginate(
            sess,
            f"{GRAPH_BASE}/security/secureScoreControlProfiles" "?$filter=controlCategory eq 'Data'",
            max_pages=5,
        )
        for p in profiles:
            if p.get("deprecated", False):
                continue
            data_max += float(p.get("maxScore") or 0)
            data_current += control_scores.get(p.get("id", ""), 0)
    except requests.exceptions.RequestException as e:
        _log_api_error("secureScoreControlProfiles (Data)", e, "SecurityEvents.Read.All")

    scores = [
        {
            "current_score": item.get("currentScore", 0),
            "max_score": item.get("maxScore", 0),
            "score_date": item.get("createdDateTime", "")[:10],
            "data_current_score": round(data_current, 2),
            "data_max_score": round(data_max, 2),
        }
    ]

    log.info("Retrieved secure score snapshot (data: %.1f/%.1f)", data_current, data_max)
    return scores


# ── Improvement Actions (Secure Score Control Profiles) ───────────


def get_improvement_actions(token: str, services: set[str] | None = None) -> list[dict[str, Any]]:
    """Return Secure Score control profiles (improvement actions).

    Args:
        services: Set of product/service names to include (case-insensitive).
                  Filtered client-side after fetch. If None, returns all Data-category actions.
    """
    sess = _session(token)
    url = f"{GRAPH_BASE}/security/secureScoreControlProfiles"

    try:
        items = _paginate(sess, url, max_pages=5)
    except requests.exceptions.RequestException as e:
        _log_api_error("secureScoreControlProfiles", e, "SecurityEvents.Read.All")
        return []

    unique_services = {i.get("service", "") for i in items}
    log.info("Secure Score service values in tenant: %s", sorted(unique_services))

    if services:
        services_lower = {s.lower() for s in services}
        items = [i for i in items if i.get("service", "").lower() in services_lower]
    else:
        items = [i for i in items if i.get("controlCategory", "").lower() == "data"]

    actions = []
    for item in items:
        if item.get("deprecated", False):
            continue

        threats = item.get("threats", [])
        threats_str = ", ".join(threats) if isinstance(threats, list) else str(threats or "")

        state = "Default"
        updates = item.get("controlStateUpdates", [])
        if isinstance(updates, list) and updates:
            state = updates[-1].get("state", "Default") if isinstance(updates[-1], dict) else "Default"

        current_score = 0
        # currentScore may be in controlScores of the latest secureScore, not here;
        # we default to 0 and can enrich later from secureScores data.

        actions.append(
            {
                "control_id": item.get("id", ""),
                "title": item.get("title", ""),
                "control_category": item.get("controlCategory", ""),
                "max_score": item.get("maxScore", 0),
                "current_score": current_score,
                "implementation_cost": item.get("implementationCost", ""),
                "user_impact": item.get("userImpact", ""),
                "tier": item.get("tier", ""),
                "service": item.get("service", ""),
                "threats": threats_str,
                "remediation": item.get("remediation", ""),
                "state": state,
                "deprecated": False,
                "rank": item.get("rank", 0),
            }
        )

    log.info("Retrieved %d improvement actions", len(actions))
    return actions


# ── Subject Rights Requests ───────────────────────────────────────


def get_subject_rights_requests(token: str) -> list[dict[str, Any]]:
    """Return Subject Rights Requests (v1.0 security namespace)."""
    sess = _session(token)
    url = f"{GRAPH_BASE}/security/subjectRightsRequests"

    try:
        items = _paginate(sess, url, max_pages=10)
    except requests.exceptions.RequestException as e:
        _log_api_error("subjectRightsRequests", e, "SubjectRightsRequest.Read.All")
        return []

    results = []
    for item in items:
        results.append(
            {
                "request_id": item.get("id", ""),
                "display_name": item.get("displayName", ""),
                "request_type": item.get("type", ""),
                "status": item.get("status", ""),
                "created": item.get("createdDateTime", ""),
                "closed": item.get("closedDateTime", ""),
                "data_subject_type": item.get("dataSubjectType", ""),
            }
        )

    log.info("Retrieved %d subject rights requests", len(results))
    return results


# ── Communication Compliance ──────────────────────────────────────


def get_comm_compliance_policies(token: str) -> list[dict[str, Any]]:
    """Return Communication Compliance policies from Graph beta API."""
    sess = _session(token)
    url = f"{GRAPH_BETA}/security/communicationCompliance/policies"

    try:
        items = _paginate(sess, url, max_pages=10)
    except requests.exceptions.RequestException as e:
        _log_api_error("communicationCompliance policies", e, "CommunicationCompliance.Read.All")
        return []

    results = []
    for item in items:
        results.append(
            {
                "policy_id": item.get("id", ""),
                "display_name": item.get("displayName", ""),
                "status": item.get("status", ""),
                "policy_type": item.get("policyType", ""),
                "review_pending_count": item.get("pendingReviewCount", 0),
            }
        )

    log.info("Retrieved %d communication compliance policies", len(results))
    return results


# ── Information Barriers ──────────────────────────────────────────


def get_info_barrier_policies(token: str) -> list[dict[str, Any]]:
    """Return Information Barrier policies from Graph beta API."""
    sess = _session(token)
    url = f"{GRAPH_BETA}/identityGovernance/informationBarriers/policies"

    try:
        items = _paginate(sess, url, max_pages=10)
    except requests.exceptions.RequestException as e:
        _log_api_error("informationBarriers policies", e, "InformationBarrierPolicy.Read.All")
        return []

    results = []
    for item in items:
        segments = item.get("segments", [])
        segments_str = (
            ", ".join(s.get("displayName", "") for s in segments) if isinstance(segments, list) else str(segments or "")
        )

        results.append(
            {
                "policy_id": item.get("id", ""),
                "display_name": item.get("displayName", ""),
                "state": item.get("state", ""),
                "segments_applied": segments_str,
            }
        )

    log.info("Retrieved %d information barrier policies", len(results))
    return results


# ── DLP Policies ─────────────────────────────────────────────────


def get_dlp_policies(token: str) -> list[dict[str, Any]]:
    """Return DLP policies (beta informationProtection API)."""
    sess = _session(token)
    url = f"{GRAPH_BETA}/security/informationProtection/dataLossPreventionPolicies"

    try:
        items = _paginate(sess, url)
    except requests.exceptions.RequestException as e:
        _log_api_error("DLP policies", e, "InformationProtectionPolicy.Read.All")
        return []

    results = []
    for item in items:
        rules = item.get("rules", [])
        status = item.get("state", "")
        if not status and item.get("isEnabled") is not None:
            status = "enabled" if item["isEnabled"] else "disabled"

        results.append(
            {
                "policy_id": item.get("id", ""),
                "display_name": item.get("displayName", "") or item.get("name", ""),
                "status": status,
                "policy_type": item.get("type", ""),
                "rules_count": len(rules) if isinstance(rules, list) else 0,
                "created": item.get("createdDateTime", ""),
                "modified": item.get("lastModifiedDateTime", ""),
                "mode": item.get("enforcementMode", "") or item.get("mode", ""),
            }
        )

    log.info("Retrieved %d DLP policies", len(results))
    return results


# ── IRM Policies ─────────────────────────────────────────────────


def get_irm_policies(token: str) -> list[dict[str, Any]]:
    """Return Insider Risk Management policies (beta API)."""
    sess = _session(token)
    url = f"{GRAPH_BETA}/security/insiderRiskManagement/policies"

    try:
        items = _paginate(sess, url)
    except requests.exceptions.RequestException as e:
        _log_api_error("IRM policies", e, "InsiderRiskManagement.Read.All")
        return []

    results = []
    for item in items:
        status = item.get("state", "")
        if not status and item.get("isEnabled") is not None:
            status = "enabled" if item["isEnabled"] else "disabled"

        triggers = item.get("insiderRiskPolicyTriggers", [])
        triggers_str = ", ".join(str(t) for t in triggers) if isinstance(triggers, list) else str(triggers or "")

        results.append(
            {
                "policy_id": item.get("id", ""),
                "display_name": item.get("displayName", ""),
                "status": status,
                "policy_type": item.get("policyType", ""),
                "created": item.get("createdDateTime", ""),
                "triggers": triggers_str,
            }
        )

    log.info("Retrieved %d IRM policies", len(results))
    return results


# ── Sensitive Information Types ──────────────────────────────────


def get_sensitive_info_types(token: str) -> list[dict[str, Any]]:
    """Return sensitive information types (beta dataClassification API)."""
    sess = _session(token)
    url = f"{GRAPH_BETA}/dataClassification/sensitiveTypes"

    try:
        items = _paginate(sess, url)
    except requests.exceptions.RequestException as e:
        _log_api_error("sensitiveTypes", e, "InformationProtectionPolicy.Read.All")
        return []

    results = []
    for item in items:
        results.append(
            {
                "type_id": item.get("id", ""),
                "name": item.get("name", ""),
                "description": item.get("description", ""),
                "is_custom": item.get("publisherName", "Microsoft") != "Microsoft",
                "category": item.get("category", ""),
                "scope": item.get("scope", ""),
                "state": item.get("state", ""),
            }
        )

    log.info("Retrieved %d sensitive info types", len(results))
    return results


# ── Compliance Assessments ───────────────────────────────────────


def get_compliance_assessments(token: str) -> list[dict[str, Any]]:
    """Return compliance assessments (beta complianceManagement API)."""
    sess = _session(token)
    url = f"{GRAPH_BETA}/security/complianceManagement/assessments"

    try:
        items = _paginate(sess, url)
    except requests.exceptions.RequestException as e:
        _log_api_error("compliance assessments", e, "ComplianceManager.Read.All")
        return []

    results = []
    for item in items:
        results.append(
            {
                "assessment_id": item.get("id", ""),
                "display_name": item.get("displayName", ""),
                "status": item.get("status", ""),
                "framework": item.get("complianceStandard", "") or item.get("framework", ""),
                "completion_percentage": float(item.get("completionPercentage", 0) or 0),
                "created": item.get("createdDateTime", ""),
                "category": item.get("category", ""),
            }
        )

    log.info("Retrieved %d compliance assessments", len(results))
    return results


# ── Threat Assessment Requests ────────────────────────────────────


def get_threat_assessment_requests(token: str) -> list[dict[str, Any]]:
    """Return threat assessment requests (v1.0 informationProtection API)."""
    sess = _session(token)
    url = f"{GRAPH_BASE}/informationProtection/threatAssessmentRequests"

    try:
        items = _paginate(sess, url, max_pages=10)
    except requests.exceptions.RequestException as e:
        _log_api_error("threatAssessmentRequests", e, "ThreatAssessment.Read.All")
        return []

    results = []
    for item in items:
        result_type = ""
        result_message = ""
        assessment_results = item.get("results", [])
        if assessment_results:
            first = assessment_results[0]
            result_type = first.get("resultType", "")
            result_message = first.get("message", "")

        results.append(
            {
                "request_id": item.get("id", ""),
                "category": item.get("category", ""),
                "content_type": item.get("contentType", item.get("@odata.type", "").split(".")[-1]),
                "status": item.get("status", ""),
                "created": item.get("createdDateTime", ""),
                "result_type": result_type,
                "result_message": result_message,
            }
        )

    log.info("Retrieved %d threat assessment requests", len(results))
    return results


# ── User Content Policies (userDataSecurityAndGovernance) ─────────


def _get_users(sess: requests.Session, max_pages: int = 5) -> list[dict]:
    """Return list of {id, userPrincipalName} dicts for all users."""
    url = f"{GRAPH_BASE}/users?$select=id,userPrincipalName&$top=100"
    try:
        items = _paginate(sess, url, max_pages=max_pages)
    except requests.exceptions.RequestException as e:
        _log_api_error("users enumeration", e, "User.Read.All")
        return []
    return [{"id": u.get("id", ""), "userPrincipalName": u.get("userPrincipalName", "")} for u in items]


def get_user_content_policies(token: str) -> list[dict[str, Any]]:
    """Submit a standard test content payload to each user and return per-user policy results."""
    sess = _session(token)
    users = _get_users(sess)

    probe_body = {
        "contentToProcess": {
            "@odata.type": "#microsoft.graph.textContent",
            "identifier": "compliance-advisor-probe",
            "name": "probe",
            "content": "SSN: 123-45-6789. Credit Card: 4111-1111-1111-1111.",
            "contentMetaData": {
                "@odata.type": "#microsoft.graph.processConversationMetadata",
                "messageIdentifier": "probe-1",
                "conversationIdentifier": "probe-conv-1",
            },
        },
        "activityMetaData": {
            "@odata.type": "#microsoft.graph.activityMetaData",
            "activityType": "uploadText",
        },
        "deviceMetaData": {
            "@odata.type": "#microsoft.graph.deviceMetaData",
            "operatingSystemSpecifications": {
                "@odata.type": "#microsoft.graph.operatingSystemSpecifications",
                "operatingSystemPlatform": "",
                "operatingSystemVersion": "",
            },
        },
        "integratedAppMetaData": {
            "@odata.type": "#microsoft.graph.integratedAppMetaData",
            "name": "compliance-advisor-collector",
        },
    }

    results = []
    for user in users:
        user_id = user["id"]
        user_upn = user["userPrincipalName"]
        url = f"{GRAPH_BASE}/users/{user_id}/dataSecurityAndGovernance/processContent"
        try:
            resp = sess.post(url, json=probe_body, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            log.warning("processContent failed for user %s: %s", user_upn, e)
            continue

        action = "none"
        policy_id = ""
        policy_name = ""
        rule_id = ""
        rule_name = ""
        match_count = 0

        if resp.status_code == 200:
            try:
                data = resp.json()
                policy_actions = data.get("policyActions", [])
                match_count = len(policy_actions)
                if policy_actions:
                    first = policy_actions[0]
                    action = first.get("action", "none")
                    policy_id = first.get("policyId", "")
                    policy_name = first.get("policyName", "")
                    rule_id = first.get("ruleId", "")
                    rule_name = first.get("ruleName", "")
            except Exception:
                pass

        results.append(
            {
                "user_id": user_id,
                "user_upn": user_upn,
                "action": action,
                "policy_id": policy_id,
                "policy_name": policy_name,
                "rule_id": rule_id,
                "rule_name": rule_name,
                "match_count": match_count,
            }
        )

    log.info("Retrieved user content policies for %d/%d users", len(results), len(users))
    return results
