"""
Persistence layer — single source of truth for upserting a compliance snapshot.

Both the ingest endpoint (raw JSON from the collector CLI) and the
in-process collection runner (``_collect_single_tenant`` in the routes)
call ``persist_payload``. This eliminates ~600 lines of duplicated
``for x in items: upsert_x(...)`` glue.

Each ``_persist_<workload>`` helper is a thin wrapper around the
corresponding ``upsert_*`` function in :mod:`shared.db`. The helpers use
``.get()`` with the same defaults the original handlers used so the wire
behavior is byte-identical.
"""

from __future__ import annotations

import logging
from typing import Iterable, Mapping

from shared.db import (
    upsert_audit_record,
    upsert_compliance_assessment,
    upsert_dlp_alert,
    upsert_dlp_policy,
    upsert_improvement_action,
    upsert_info_barrier_policy,
    upsert_irm_alert,
    upsert_irm_policy,
    upsert_protection_scope,
    upsert_purview_incident,
    upsert_retention_event,
    upsert_retention_event_type,
    upsert_retention_label,
    upsert_secure_score,
    upsert_sensitive_info_type,
    upsert_sensitivity_label,
    upsert_tenant,
    upsert_threat_assessment_request,
    upsert_user_content_policies,
)

log = logging.getLogger(__name__)

# Type alias for any iterable of dict-like records (a workload payload).
_Records = Iterable[Mapping]


def _persist_sensitivity_labels(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for sl in items:
        upsert_sensitivity_label(
            tenant_id=tenant_id,
            label_id=sl.get("label_id", ""),
            name=sl.get("name", ""),
            description=sl.get("description", ""),
            color=sl.get("color", ""),
            is_active=sl.get("is_active", True),
            parent_id=sl.get("parent_id", ""),
            priority=sl.get("priority", 0),
            tooltip=sl.get("tooltip", ""),
            snapshot_date=snapshot_date,
            has_protection=sl.get("has_protection", False),
            applicable_to=sl.get("applicable_to", ""),
            application_mode=sl.get("application_mode", ""),
            is_endpoint_protection_enabled=sl.get("is_endpoint_protection_enabled", False),
        )
        count += 1
    return count


def _persist_retention_events(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for re_ in items:
        upsert_retention_event(
            tenant_id=tenant_id,
            event_id=re_.get("event_id", ""),
            display_name=re_.get("display_name", ""),
            event_type=re_.get("event_type", ""),
            created=re_.get("created", ""),
            event_status=re_.get("event_status", ""),
            snapshot_date=snapshot_date,
        )
        count += 1
    return count


def _persist_retention_event_types(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for ret in items:
        upsert_retention_event_type(
            tenant_id=tenant_id,
            event_type_id=ret.get("event_type_id", ""),
            display_name=ret.get("display_name", ""),
            description=ret.get("description", ""),
            created=ret.get("created", ""),
            modified=ret.get("modified", ""),
            snapshot_date=snapshot_date,
        )
        count += 1
    return count


def _persist_retention_labels(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for rl in items:
        upsert_retention_label(
            tenant_id=tenant_id,
            label_id=rl.get("label_id", ""),
            name=rl.get("name", ""),
            description=rl.get("description", ""),
            is_in_use=rl.get("is_in_use", False),
            retention_duration=rl.get("retention_duration", ""),
            action_after=rl.get("action_after", ""),
            default_record_behavior=rl.get("default_record_behavior", ""),
            created=rl.get("created", ""),
            modified=rl.get("modified", ""),
            snapshot_date=snapshot_date,
        )
        count += 1
    return count


def _persist_audit_records(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for ar in items:
        upsert_audit_record(
            tenant_id=tenant_id,
            record_id=ar.get("record_id", ""),
            record_type=ar.get("record_type", ""),
            operation=ar.get("operation", ""),
            service=ar.get("service", ""),
            user_id=ar.get("user_id", ""),
            created=ar.get("created", ""),
            snapshot_date=snapshot_date,
            ip_address=ar.get("ip_address", ""),
            client_app=ar.get("client_app", ""),
            result_status=ar.get("result_status", ""),
        )
        count += 1
    return count


def _persist_alerts(
    tenant_id: str,
    snapshot_date: str,
    items: _Records,
    upsert_fn,
) -> int:
    """Shared helper for DLP and IRM alerts (same field set)."""
    count = 0
    for a in items:
        upsert_fn(
            tenant_id=tenant_id,
            alert_id=a.get("alert_id", ""),
            title=a.get("title", ""),
            severity=a.get("severity", ""),
            status=a.get("status", ""),
            category=a.get("category", ""),
            policy_name=a.get("policy_name", ""),
            created=a.get("created", ""),
            resolved=a.get("resolved", ""),
            snapshot_date=snapshot_date,
            description=a.get("description", ""),
            assigned_to=a.get("assigned_to", ""),
            classification=a.get("classification", ""),
            determination=a.get("determination", ""),
            recommended_actions=a.get("recommended_actions", ""),
            incident_id=a.get("incident_id", ""),
            mitre_techniques=a.get("mitre_techniques", ""),
            evidence=a.get("evidence", []),
        )
        count += 1
    return count


def _persist_protection_scopes(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for ps in items:
        upsert_protection_scope(
            tenant_id=tenant_id,
            scope_type=ps.get("scope_type", ""),
            execution_mode=ps.get("execution_mode", ""),
            locations=ps.get("locations", ""),
            activity_types=ps.get("activity_types", ""),
            snapshot_date=snapshot_date,
        )
        count += 1
    return count


def _persist_info_barrier_policies(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for ib in items:
        upsert_info_barrier_policy(
            tenant_id=tenant_id,
            policy_id=ib.get("policy_id", ""),
            display_name=ib.get("display_name", ""),
            state=ib.get("state", ""),
            segments_applied=ib.get("segments_applied", ""),
            snapshot_date=snapshot_date,
        )
        count += 1
    return count


def _persist_secure_scores(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for ss in items:
        upsert_secure_score(
            tenant_id=tenant_id,
            current_score=ss.get("current_score", 0),
            max_score=ss.get("max_score", 0),
            score_date=ss.get("score_date", snapshot_date),
            snapshot_date=snapshot_date,
            data_current_score=ss.get("data_current_score", 0),
            data_max_score=ss.get("data_max_score", 0),
        )
        count += 1
    return count


def _persist_improvement_actions(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for ia in items:
        upsert_improvement_action(
            tenant_id=tenant_id,
            control_id=ia.get("control_id", ""),
            title=ia.get("title", ""),
            control_category=ia.get("control_category", ""),
            max_score=ia.get("max_score", 0),
            current_score=ia.get("current_score", 0),
            implementation_cost=ia.get("implementation_cost", ""),
            user_impact=ia.get("user_impact", ""),
            tier=ia.get("tier", ""),
            service=ia.get("service", ""),
            threats=ia.get("threats", ""),
            remediation=ia.get("remediation", ""),
            state=ia.get("state", "Default"),
            deprecated=ia.get("deprecated", False),
            rank=ia.get("rank", 0),
            snapshot_date=snapshot_date,
        )
        count += 1
    return count


def _persist_dlp_policies(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for dp in items:
        upsert_dlp_policy(
            tenant_id=tenant_id,
            policy_id=dp.get("policy_id", ""),
            display_name=dp.get("display_name", ""),
            status=dp.get("status", ""),
            policy_type=dp.get("policy_type", ""),
            rules_count=dp.get("rules_count", 0),
            created=dp.get("created", ""),
            modified=dp.get("modified", ""),
            mode=dp.get("mode", ""),
            snapshot_date=snapshot_date,
        )
        count += 1
    return count


def _persist_irm_policies(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for ip in items:
        upsert_irm_policy(
            tenant_id=tenant_id,
            policy_id=ip.get("policy_id", ""),
            display_name=ip.get("display_name", ""),
            status=ip.get("status", ""),
            policy_type=ip.get("policy_type", ""),
            created=ip.get("created", ""),
            triggers=ip.get("triggers", ""),
            snapshot_date=snapshot_date,
        )
        count += 1
    return count


def _persist_sensitive_info_types(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for si in items:
        upsert_sensitive_info_type(
            tenant_id=tenant_id,
            type_id=si.get("type_id", ""),
            name=si.get("name", ""),
            description=si.get("description", ""),
            is_custom=si.get("is_custom", False),
            category=si.get("category", ""),
            scope=si.get("scope", ""),
            state=si.get("state", ""),
            snapshot_date=snapshot_date,
        )
        count += 1
    return count


def _persist_compliance_assessments(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for ca in items:
        upsert_compliance_assessment(
            tenant_id=tenant_id,
            assessment_id=ca.get("assessment_id", ""),
            display_name=ca.get("display_name", ""),
            status=ca.get("status", ""),
            framework=ca.get("framework", ""),
            completion_percentage=ca.get("completion_percentage", 0),
            created=ca.get("created", ""),
            category=ca.get("category", ""),
            snapshot_date=snapshot_date,
        )
        count += 1
    return count


def _persist_threat_assessment_requests(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for ta in items:
        upsert_threat_assessment_request(
            tenant_id=tenant_id,
            request_id=ta.get("request_id", ""),
            category=ta.get("category", ""),
            content_type=ta.get("content_type", ""),
            status=ta.get("status", ""),
            created=ta.get("created", ""),
            result_type=ta.get("result_type", ""),
            result_message=ta.get("result_message", ""),
            snapshot_date=snapshot_date,
        )
        count += 1
    return count


def _persist_purview_incidents(tenant_id: str, snapshot_date: str, items: _Records) -> int:
    count = 0
    for pi in items:
        upsert_purview_incident(
            tenant_id=tenant_id,
            incident_id=pi.get("incident_id", ""),
            display_name=pi.get("display_name", ""),
            severity=pi.get("severity", ""),
            status=pi.get("status", ""),
            classification=pi.get("classification", ""),
            determination=pi.get("determination", ""),
            created=pi.get("created", ""),
            last_update=pi.get("last_update", ""),
            assigned_to=pi.get("assigned_to", ""),
            alerts_count=pi.get("alerts_count", 0),
            purview_alerts_count=pi.get("purview_alerts_count", 0),
            snapshot_date=snapshot_date,
        )
        count += 1
    return count


def persist_payload(
    *,
    tenant_id: str,
    snapshot_date: str,
    display_name: str | None = None,
    department: str | None = None,
    risk_tier: str | None = None,
    sensitivity_labels: _Records = (),
    retention_events: _Records = (),
    retention_event_types: _Records = (),
    retention_labels: _Records = (),
    audit_records: _Records = (),
    dlp_alerts: _Records = (),
    irm_alerts: _Records = (),
    protection_scopes: _Records = (),
    info_barrier_policies: _Records = (),
    secure_scores: _Records = (),
    improvement_actions: _Records = (),
    user_content_policies: _Records = (),
    dlp_policies: _Records = (),
    irm_policies: _Records = (),
    sensitive_info_types: _Records = (),
    compliance_assessments: _Records = (),
    threat_assessment_requests: _Records = (),
    purview_incidents: _Records = (),
) -> dict[str, int]:
    """Upsert a full compliance snapshot for a tenant.

    The tenant row itself is upserted only when ``display_name`` and
    ``department`` are both provided (the ingest path always supplies them;
    the timer path skips this because tenant metadata is already in PG).

    Returns a per-workload count dict suitable for logging/response bodies.
    """
    if display_name is not None and department is not None:
        kwargs = {
            "tenant_id": tenant_id,
            "display_name": display_name,
            "department": department,
        }
        if risk_tier is not None:
            kwargs["risk_tier"] = risk_tier
        upsert_tenant(**kwargs)

    counts = {
        "sensitivity_labels": _persist_sensitivity_labels(tenant_id, snapshot_date, sensitivity_labels),
        "retention_events": _persist_retention_events(tenant_id, snapshot_date, retention_events),
        "retention_event_types": _persist_retention_event_types(tenant_id, snapshot_date, retention_event_types),
        "retention_labels": _persist_retention_labels(tenant_id, snapshot_date, retention_labels),
        "audit_records": _persist_audit_records(tenant_id, snapshot_date, audit_records),
        "dlp_alerts": _persist_alerts(tenant_id, snapshot_date, dlp_alerts, upsert_dlp_alert),
        "irm_alerts": _persist_alerts(tenant_id, snapshot_date, irm_alerts, upsert_irm_alert),
        "protection_scopes": _persist_protection_scopes(tenant_id, snapshot_date, protection_scopes),
        "info_barrier_policies": _persist_info_barrier_policies(tenant_id, snapshot_date, info_barrier_policies),
        "secure_scores": _persist_secure_scores(tenant_id, snapshot_date, secure_scores),
        "improvement_actions": _persist_improvement_actions(tenant_id, snapshot_date, improvement_actions),
        "dlp_policies": _persist_dlp_policies(tenant_id, snapshot_date, dlp_policies),
        "irm_policies": _persist_irm_policies(tenant_id, snapshot_date, irm_policies),
        "sensitive_info_types": _persist_sensitive_info_types(tenant_id, snapshot_date, sensitive_info_types),
        "compliance_assessments": _persist_compliance_assessments(tenant_id, snapshot_date, compliance_assessments),
        "threat_assessment_requests": _persist_threat_assessment_requests(
            tenant_id, snapshot_date, threat_assessment_requests
        ),
        "purview_incidents": _persist_purview_incidents(tenant_id, snapshot_date, purview_incidents),
    }

    # User content policies use a bulk-upsert function (different signature)
    ucp_list = list(user_content_policies)
    upsert_user_content_policies(
        tenant_id=tenant_id,
        records=ucp_list,
        snapshot_date=snapshot_date,
    )
    counts["user_content_policies"] = len(ucp_list)

    return counts
