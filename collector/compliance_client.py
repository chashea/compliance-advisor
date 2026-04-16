"""
Microsoft Graph API client for compliance workload data collection.

Pulls data from:
- GET  /v1.0/security/dataSecurityAndGovernance/sensitivityLabels — sensitivity labels (v1.0 GA)
- GET  /v1.0/security/triggers/retentionEvents                   — retention events
- GET  /v1.0/security/triggerTypes/retentionEventTypes           — retention event types
- POST /v1.0/security/auditLog/queries + GET records             — audit log (async)
- GET  /v1.0/security/alerts_v2?$filter=serviceSource             — DLP + IRM alerts
- GET  /v1.0/security/incidents                                   — Purview-prioritized incidents
- POST /v1.0/dataSecurityAndGovernance/protectionScopes/compute  — protection scopes
- POST /v1.0/users/{id}/dataSecurityAndGovernance/processContent — user content policies
- GET  /beta/security/informationProtection/dataLossPreventionPolicies — DLP policies
- GET  /beta/security/insiderRiskManagement/policies              — IRM policies
- GET  /beta/dataClassification/sensitiveTypes                    — sensitive info types
- GET  /beta/security/complianceManagement/assessments            — compliance assessments

Required Microsoft Graph Application permissions:
- InformationProtectionPolicy.Read.All    — sensitivity labels (beta endpoint)
- SensitivityLabel.Read                   — sensitivity labels (v1.0 fallback)
- RecordsManagement.Read.All              — retention labels (delegated only!), retention events, retention event types
- AuditLogsQuery.Read.All                 — audit log queries
- SecurityAlert.Read.All                  — DLP + IRM alerts (alerts_v2)
- SecurityIncident.Read.All               — incidents
- DataSecurityAndGovernance.Read.All      — protection scopes, user content policies
- SecurityEvents.Read.All                 — Secure Score + improvement actions
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


# ── Information Protection (sensitivity labels) ───────────────────


def get_sensitivity_labels(token: str) -> list[dict[str, Any]]:
    """Return sensitivity labels.

    Tries endpoints in order:
    1. v1.0 /security/dataSecurityAndGovernance/sensitivityLabels
       (SensitivityLabel.Read — Commercial + GCC, richer properties)
    2. beta /security/informationProtection/sensitivityLabels
       (InformationProtectionPolicy.Read.All — fallback)
    """
    sess = _session(token)

    # Try v1.0 GA endpoint first (richer properties)
    url = f"{GRAPH_BASE}/security/dataSecurityAndGovernance/sensitivityLabels"
    try:
        items = _paginate(sess, url)
        if items:
            labels = _map_sensitivity_labels(items)
            log.info("Retrieved %d sensitivity labels (v1.0/dataSecurityAndGovernance)", len(labels))
            return labels
    except requests.exceptions.RequestException as e:
        _log_api_error("sensitivityLabels (v1.0/dataSecurityAndGovernance)", e, "SensitivityLabel.Read")

    # Fallback: beta informationProtection endpoint (DEPRECATED by Microsoft —
    # will be removed once all tenants reliably support the v1.0 GA endpoint above).
    log.warning("v1.0 sensitivityLabels endpoint failed or returned empty; falling back to deprecated beta endpoint")
    url = f"{GRAPH_BETA}/security/informationProtection/sensitivityLabels"
    try:
        items = _paginate(sess, url)
    except requests.exceptions.RequestException as e:
        _log_api_error("sensitivityLabels (beta/informationProtection)", e, "InformationProtectionPolicy.Read.All")
        return []

    labels = _map_sensitivity_labels(items)
    log.info("Retrieved %d sensitivity labels (beta/informationProtection — deprecated fallback)", len(labels))
    return labels


def _map_sensitivity_labels(items: list[dict]) -> list[dict[str, Any]]:
    """Map Graph API sensitivity label response to our schema."""
    labels = []
    for item in items:
        # applicableTo can be a comma-separated string or a list
        applicable_raw = item.get("applicableTo", "")
        if isinstance(applicable_raw, list):
            applicable_to = ", ".join(applicable_raw)
        else:
            applicable_to = str(applicable_raw) if applicable_raw else ""

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
                "has_protection": item.get("hasProtection", False),
                "applicable_to": applicable_to,
                "application_mode": item.get("applicationMode", ""),
                "is_endpoint_protection_enabled": item.get("isEndpointProtectionEnabled", False),
            }
        )
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


# ── Records Management (retention event types) ────────────────────


def get_retention_event_types(token: str) -> list[dict[str, Any]]:
    """Return retention event types.

    Required Graph permission (Application): RecordsManagement.Read.All
    """
    sess = _session(token)
    url = f"{GRAPH_BASE}/security/triggerTypes/retentionEventTypes"

    try:
        items = _paginate(sess, url)
    except requests.exceptions.RequestException as e:
        _log_api_error("retentionEventTypes", e, "RecordsManagement.Read.All")
        return []

    event_types = []
    for item in items:
        event_types.append(
            {
                "event_type_id": item.get("id", ""),
                "display_name": item.get("displayName", ""),
                "description": item.get("description", ""),
                "created": item.get("createdDateTime", ""),
                "modified": item.get("lastModifiedDateTime", ""),
            }
        )

    log.info("Retrieved %d retention event types", len(event_types))
    return event_types


# ── Records Management (retention labels) ─────────────────────────


def get_retention_labels(token: str) -> list[dict[str, Any]]:
    """Return retention labels.

    Tries beta endpoint first, then v1.0. Both may return 403 with app-only auth
    since the retentionLabels API currently requires delegated permissions.
    Returns empty list on 403.
    """
    sess = _session(token)

    for base, label in [(GRAPH_BETA, "beta"), (GRAPH_BASE, "v1.0")]:
        url = f"{base}/security/labels/retentionLabels"
        try:
            items = _paginate(sess, url)
            if items is not None:
                labels = [
                    {
                        "label_id": item.get("id", ""),
                        "name": item.get("displayName", ""),
                        "description": item.get("descriptionForUsers", "") or item.get("description", ""),
                        "is_in_use": item.get("isInUse", False),
                        "retention_duration": item.get("retentionDuration", ""),
                        "action_after": item.get("actionAfterRetentionPeriod", ""),
                        "default_record_behavior": item.get("defaultRecordBehavior", ""),
                        "created": item.get("createdDateTime", ""),
                        "modified": item.get("lastModifiedDateTime", ""),
                    }
                    for item in items
                ]
                log.info("Retrieved %d retention labels (%s)", len(labels), label)
                return labels
        except requests.exceptions.RequestException as e:
            resp = getattr(e, "response", None)
            status_code = resp.status_code if resp is not None else 0
            if status_code == 403:
                log.warning("Retention labels API returned 403 (%s) — app-only auth not supported", label)
            else:
                _log_api_error(f"retentionLabels ({label})", e, "RecordsManagement.Read.All")

    log.warning("Retention labels unavailable (app-only auth limitation) — returning empty list")
    return []


# ── Audit Log (async query API) ───────────────────────────────────


def get_audit_log_records(token: str, days: int = 7) -> list[dict[str, Any]]:
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
            "sensitivityLabelAction",
            "sensitivityLabeledFileAction",
            "sensitivityLabelPolicyMatch",
            "complianceDLPExchange",
            "complianceDLPSharePoint",
            "complianceDLPSharePointClassification",
            "complianceDLPEndpoint",
            "complianceSupervisionExchange",
            "recordsManagement",
            "dataGovernance",
            "mipLabel",
            "informationBarrierPolicyApplication",
            "microsoftPurview",
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
        evidence_raw = item.get("evidence") or []
        evidence = [
            {
                "type": (e.get("@odata.type") or "").replace("#microsoft.graph.security.", ""),
                "remediation_status": e.get("remediationStatus", ""),
                "verdict": e.get("verdict", ""),
                "roles": e.get("roles") or [],
                "detailed_roles": e.get("detailedRoles") or [],
            }
            for e in evidence_raw
        ]
        mitre = item.get("mitreTechniques") or []
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
                "classification": item.get("classification", ""),
                "determination": item.get("determination", ""),
                "recommended_actions": item.get("recommendedActions", ""),
                "incident_id": item.get("incidentId", ""),
                "mitre_techniques": ",".join(mitre) if mitre else "",
                "evidence": evidence,
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


def _severity_rank(severity: str) -> int:
    ranks = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    return ranks.get((severity or "").lower(), 0)


def _extract_incident_alert_ids(item: dict[str, Any]) -> set[str]:
    raw_alerts = item.get("alerts") or item.get("alertIds") or []
    if not isinstance(raw_alerts, list):
        return set()

    alert_ids: set[str] = set()
    for alert in raw_alerts:
        if isinstance(alert, dict):
            alert_id = alert.get("id") or alert.get("alertId")
            if alert_id:
                alert_ids.add(str(alert_id))
        elif isinstance(alert, str):
            alert_ids.add(alert)
    return alert_ids


def _derive_purview_incidents_from_alerts(purview_alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for alert in purview_alerts:
        incident_id = str(alert.get("incident_id", "")).strip()
        if not incident_id:
            continue
        grouped.setdefault(incident_id, []).append(alert)

    incidents: list[dict[str, Any]] = []
    for incident_id, alerts in grouped.items():
        top_severity = max((_severity_rank(str(a.get("severity", ""))) for a in alerts), default=0)
        severity = next(
            (s for s in ("critical", "high", "medium", "low") if _severity_rank(s) == top_severity),
            "unknown",
        )
        statuses = [str(a.get("status", "")).lower() for a in alerts]
        is_active = any(status not in {"resolved", "dismissed"} for status in statuses)
        created_values = [str(a.get("created", "")) for a in alerts if a.get("created")]
        last_update_values = [
            str(a.get("resolved", "") or a.get("created", "")) for a in alerts if a.get("resolved") or a.get("created")
        ]
        incidents.append(
            {
                "incident_id": incident_id,
                "display_name": str(alerts[0].get("title", "")),
                "severity": severity,
                "status": "active" if is_active else "resolved",
                "classification": next(
                    (str(a.get("classification", "")) for a in alerts if a.get("classification")),
                    "",
                ),
                "determination": next(
                    (str(a.get("determination", "")) for a in alerts if a.get("determination")),
                    "",
                ),
                "created": min(created_values) if created_values else "",
                "last_update": max(last_update_values) if last_update_values else "",
                "assigned_to": str(alerts[0].get("assigned_to", "")),
                "alerts_count": len(alerts),
                "purview_alerts_count": len(alerts),
            }
        )

    incidents.sort(
        key=lambda i: (_severity_rank(str(i.get("severity", ""))), str(i.get("last_update", ""))),
        reverse=True,
    )
    return incidents


def get_purview_incidents(token: str, purview_alerts: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Return Purview-prioritized incidents.

    Incidents are scoped to those with DLP/IRM alert linkage. If the incidents API call fails
    (for example missing SecurityIncident.Read.All), this falls back to incident-level rollups
    derived from DLP/IRM alerts with incident IDs.
    """
    alerts = purview_alerts if purview_alerts is not None else [*get_dlp_alerts(token), *get_irm_alerts(token)]
    if not alerts:
        log.info("Retrieved 0 Purview incidents (no DLP/IRM alerts to correlate)")
        return []

    purview_alert_ids = {str(a.get("alert_id", "")).strip() for a in alerts if a.get("alert_id")}
    purview_incident_ids = {str(a.get("incident_id", "")).strip() for a in alerts if a.get("incident_id")}

    sess = _session(token)
    url = f"{GRAPH_BASE}/security/incidents?$top=100"
    try:
        items = _paginate(sess, url, max_pages=5)
    except requests.exceptions.RequestException as e:
        _log_api_error("incidents", e, "SecurityIncident.Read.All")
        derived = _derive_purview_incidents_from_alerts(alerts)
        if derived:
            log.warning("Falling back to incident rollups from Purview alerts (%d incidents)", len(derived))
        return derived

    incidents: list[dict[str, Any]] = []
    for item in items:
        incident_id = str(item.get("id", "")).strip()
        if not incident_id:
            continue

        incident_alert_ids = _extract_incident_alert_ids(item)
        matching_alert_ids = incident_alert_ids.intersection(purview_alert_ids)
        has_purview_signal = incident_id in purview_incident_ids or bool(matching_alert_ids)
        if not has_purview_signal:
            continue

        alert_count = len(incident_alert_ids)
        if alert_count == 0:
            alert_count = int(item.get("alertsCount", 0) or 0)

        purview_alerts_count = len(matching_alert_ids)
        if purview_alerts_count == 0 and incident_id in purview_incident_ids:
            purview_alerts_count = sum(1 for a in alerts if str(a.get("incident_id", "")).strip() == incident_id)

        incidents.append(
            {
                "incident_id": incident_id,
                "display_name": item.get("displayName", "") or item.get("title", ""),
                "severity": str(item.get("severity", "")).lower(),
                "status": str(item.get("status", "")).lower(),
                "classification": item.get("classification", ""),
                "determination": item.get("determination", ""),
                "created": item.get("createdDateTime", ""),
                "last_update": item.get("lastUpdateDateTime", ""),
                "assigned_to": item.get("assignedTo", ""),
                "alerts_count": alert_count,
                "purview_alerts_count": purview_alerts_count,
            }
        )

    incidents.sort(
        key=lambda i: (
            _severity_rank(str(i.get("severity", ""))),
            str(i.get("last_update", "")),
            str(i.get("created", "")),
        ),
        reverse=True,
    )
    log.info("Retrieved %d Purview-prioritized incidents", len(incidents))

    if incidents:
        return incidents
    return _derive_purview_incidents_from_alerts(alerts)


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


def get_secure_scores(token: str, days: int = 30) -> list[dict[str, Any]]:
    """Return Secure Score snapshots for the last N days with Data category breakdown."""
    sess = _session(token)

    try:
        resp = sess.get(f"{GRAPH_BASE}/security/secureScores?$top={days}", timeout=30)
        resp.raise_for_status()
        items = resp.json().get("value", [])
    except requests.exceptions.RequestException as e:
        _log_api_error("secureScores", e, "SecurityEvents.Read.All")
        return []

    if not items:
        return []

    # Fetch Data category control profiles once for data score computation
    data_max = 0.0
    data_profile_ids: set[str] = set()
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
            if p.get("id"):
                data_profile_ids.add(p["id"])
    except requests.exceptions.RequestException as e:
        _log_api_error("secureScoreControlProfiles (Data)", e, "SecurityEvents.Read.All")

    scores = []
    seen_dates: set[str] = set()
    for item in items:
        score_date = item.get("createdDateTime", "")[:10]
        if not score_date or score_date in seen_dates:
            continue
        seen_dates.add(score_date)

        control_scores: dict[str, float] = {
            cs["controlName"]: float(cs.get("score") or 0)
            for cs in item.get("controlScores", [])
            if isinstance(cs, dict) and cs.get("controlName")
        }
        data_current = sum(control_scores.get(pid, 0) for pid in data_profile_ids)

        scores.append(
            {
                "current_score": item.get("currentScore", 0),
                "max_score": item.get("maxScore", 0),
                "score_date": score_date,
                "data_current_score": round(data_current, 2),
                "data_max_score": round(data_max, 2),
            }
        )

    log.info("Retrieved %d secure score snapshots (data max: %.1f)", len(scores), data_max)
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
    """Return DLP policies (beta informationProtection API).

    TODO: Monitor Graph changelog — this endpoint may migrate from
    informationProtection to dataSecurityAndGovernance namespace (like
    sensitivity labels did). Check https://developer.microsoft.com/en-us/graph/changelog
    """
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
