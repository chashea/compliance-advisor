"""Collection routes + helpers (per-tenant + threat-hunt orchestration).

Owns:

- The fire-and-forget ``ThreadPoolExecutor`` used by tenant registration.
- The hunt concurrency semaphore.
- ``_collect_single_tenant`` (Graph → persist_payload) and
  ``_hunt_single_tenant`` (KQL templates → hunt tables).
- HTTP routes ``POST /collect/{tenant_id}`` and ``POST /hunt/{tenant_id}``.

These are split out of the monolithic ``function_app.py`` so the route
file is testable in isolation and the giant per-workload upsert loop is
collapsed via :mod:`shared.persist`.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import azure.functions as func
from shared.db import (
    insert_hunt_result,
    insert_hunt_run,
    query,
    update_tenant_status,
)
from shared.persist import persist_payload

from routes._decorator import get_body_or_400, json_response

log = logging.getLogger(__name__)

bp = func.Blueprint()

# Background executor for the fire-and-forget collection triggered by
# tenant registration / consent callback.
_COLLECTION_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="collect")

# Cap concurrent Graph-API hunting calls across all tenants.
_HUNT_SEMAPHORE = threading.Semaphore(3)

# Templates that use ``summarize`` (aggregate rows, not individual findings)
_AGGREGATE_TEMPLATES = {"irm-risky-users", "alert-by-user"}

# Default severity by template name; overridden by row-level Severity when present
_TEMPLATE_SEVERITY: dict[str, str] = {
    "usb-exfil": "high",
    "high-severity": "high",
    "label-downgrade": "medium",
    "label-removal": "medium",
    "dlp-violations": "medium",
    "cloud-upload": "medium",
    "external-sharing": "medium",
    "email-dlp": "medium",
    "comm-compliance": "medium",
    "admin-activity": "low",
    "purview-alerts": "info",
    "print-sensitive": "info",
}


# ── Optional collector / hunter imports ──────────────────────────
# These mirror the original ``function_app.py`` import gating so the
# function host can still start even if the collector package fails
# to import. The module-level None sentinel + try/except is the
# pattern that test mocks rely on (e.g. patch _COLLECTOR_IMPORT_ERROR).

_COLLECTOR_IMPORT_ERROR: Exception | None = None
try:
    from collector.auth import get_graph_token
    from collector.compliance_client import (
        get_audit_log_records as collect_audit_log_records,
    )
    from collector.compliance_client import (
        get_compliance_assessments as collect_assessments,
    )
    from collector.compliance_client import (
        get_dlp_alerts as collect_dlp_alerts,
    )
    from collector.compliance_client import (
        get_dlp_policies as collect_dlp_policies,
    )
    from collector.compliance_client import (
        get_improvement_actions as collect_improvement_actions,
    )
    from collector.compliance_client import (
        get_info_barrier_policies as collect_info_barriers,
    )
    from collector.compliance_client import (
        get_irm_alerts as collect_irm_alerts,
    )
    from collector.compliance_client import (
        get_irm_policies as collect_irm_policies,
    )
    from collector.compliance_client import (
        get_protection_scopes as collect_protection_scopes,
    )
    from collector.compliance_client import (
        get_purview_incidents as collect_purview_incidents,
    )
    from collector.compliance_client import (
        get_retention_event_types as collect_retention_event_types,
    )
    from collector.compliance_client import (
        get_retention_events as collect_retention_events,
    )
    from collector.compliance_client import (
        get_retention_labels as collect_retention_labels,
    )
    from collector.compliance_client import (
        get_secure_scores as collect_secure_scores,
    )
    from collector.compliance_client import (
        get_sensitive_info_types as collect_sensitive_info_types,
    )
    from collector.compliance_client import (
        get_sensitivity_labels as collect_sensitivity_labels,
    )
    from collector.compliance_client import (
        get_threat_assessment_requests as collect_threat_assessments,
    )
    from collector.compliance_client import (
        get_user_content_policies as collect_user_content_policies,
    )
except Exception as e:
    _COLLECTOR_IMPORT_ERROR = e
    log.warning("Collector imports unavailable (timer will be disabled): %s", e)

_HUNTER_IMPORT_ERROR: Exception | None = None
try:
    from collector.hunter.graph import HuntingQueryError, run_hunting_query
    from collector.hunter.templates import TEMPLATES, render_template
except Exception as e:
    _HUNTER_IMPORT_ERROR = e
    log.warning("Hunter imports unavailable (threat hunting will be disabled): %s", e)


# ── Per-tenant collection helper ─────────────────────────────────


def _collect_single_tenant(
    tid: str,
    display_name: str,
    department: str,
    client_id: str,
    client_secret: str,
    audit_days: int = 1,
) -> dict:
    """Collect compliance data from a single tenant and upsert via persist_payload.

    Returns a dict with ``status`` (``ok`` | ``error``) and either record
    counts or an error message. Never raises — failures are reported in
    the dict.
    """
    from datetime import date
    from types import SimpleNamespace

    today = date.today().isoformat()
    try:
        from shared.config import get_settings as _get_settings

        use_federated = _get_settings().COLLECTOR_USE_FEDERATED
        auth_settings = SimpleNamespace(
            TENANT_ID=tid,
            CLIENT_ID=client_id,
            CLIENT_SECRET=client_secret,
            USE_FEDERATED=use_federated,
            login_authority="https://login.microsoftonline.com",
            graph_scope=["https://graph.microsoft.com/.default"],
        )
        token = get_graph_token(auth_settings)

        sensitivity = collect_sensitivity_labels(token)
        ret_events = collect_retention_events(token)
        ret_event_types = collect_retention_event_types(token)
        ret_labels = collect_retention_labels(token)
        audit = collect_audit_log_records(token, days=audit_days)
        dlp = collect_dlp_alerts(token)
        irm = collect_irm_alerts(token)
        incidents = collect_purview_incidents(token, [*dlp, *irm])
        scopes = collect_protection_scopes(token)
        scores = collect_secure_scores(token)
        actions = collect_improvement_actions(token)
        ib = collect_info_barriers(token)
        ucp = collect_user_content_policies(token)
        dlp_pol = collect_dlp_policies(token)
        irm_pol = collect_irm_policies(token)
        sit = collect_sensitive_info_types(token)
        assessments = collect_assessments(token)
        threats = collect_threat_assessments(token)

        all_counts = persist_payload(
            tenant_id=tid,
            snapshot_date=today,
            display_name=display_name,
            department=department,
            sensitivity_labels=sensitivity,
            retention_events=ret_events,
            retention_event_types=ret_event_types,
            retention_labels=ret_labels,
            audit_records=audit,
            dlp_alerts=dlp,
            irm_alerts=irm,
            protection_scopes=scopes,
            info_barrier_policies=ib,
            secure_scores=scores,
            improvement_actions=actions,
            user_content_policies=ucp,
            dlp_policies=dlp_pol,
            irm_policies=irm_pol,
            sensitive_info_types=sit,
            compliance_assessments=assessments,
            threat_assessment_requests=threats,
            purview_incidents=incidents,
        )

        # Preserve the legacy counts shape for callers/tests
        counts = {
            "sensitivity_labels": all_counts.get("sensitivity_labels", 0),
            "audit_records": all_counts.get("audit_records", 0),
            "dlp_alerts": all_counts.get("dlp_alerts", 0),
            "irm_alerts": all_counts.get("irm_alerts", 0),
            "secure_scores": all_counts.get("secure_scores", 0),
            "improvement_actions": all_counts.get("improvement_actions", 0),
            "threat_assessments": all_counts.get("threat_assessment_requests", 0),
            "purview_incidents": all_counts.get("purview_incidents", 0),
        }
        log.info("_collect_single_tenant: tenant=%s dept=%s counts=%s", tid, department, counts)
        try:
            update_tenant_status(tid, "active")
        except Exception:
            log.debug("update_tenant_status not available yet (run schema migration)")

        # Run threat hunting templates (failures here don't break collection)
        try:
            hunt_result = _hunt_single_tenant(
                tid=tid,
                client_id=client_id,
                client_secret=client_secret,
                days=1,
            )
            counts["hunt_findings"] = hunt_result.get("total_findings", 0)
            counts["hunt_templates_run"] = hunt_result.get("templates_run", 0)
        except Exception:
            log.exception("_collect_single_tenant: hunting failed for tenant=%s (non-fatal)", tid)
            counts["hunt_findings"] = 0
            counts["hunt_templates_run"] = 0

        return {"status": "ok", "tenant_id": tid, "record_counts": counts}

    except Exception as e:
        log.exception("_collect_single_tenant: failed for tenant=%s: %s", tid, e)
        try:
            update_tenant_status(tid, "error")
        except Exception:
            pass
        return {"status": "error", "tenant_id": tid, "error": str(e)}


def _hunt_single_tenant(
    tid: str,
    client_id: str,
    client_secret: str,
    days: int = 1,
) -> dict:
    """Run all hunt templates against a tenant and persist results."""
    if _HUNTER_IMPORT_ERROR is not None:
        log.info("_hunt_single_tenant: hunter imports unavailable, skipping tenant=%s", tid)
        return {"status": "skipped", "tenant_id": tid, "reason": "hunter_unavailable"}

    import msal

    authority = f"https://login.microsoftonline.com/{tid}"
    msal_app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority,
    )
    result = msal_app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "Unknown"))
        log.warning("_hunt_single_tenant: auth failed for tenant=%s: %s", tid, error)
        return {"status": "error", "tenant_id": tid, "error": f"Auth failed: {error}"}

    token = result["access_token"]

    templates_run = 0
    total_findings = 0
    skipped = 0

    for template in TEMPLATES:
        if template.name in _AGGREGATE_TEMPLATES:
            skipped += 1
            continue

        kql = render_template(template, days=days, limit=50)

        with _HUNT_SEMAPHORE:
            try:
                query_result = run_hunting_query(kql=kql, token=token)
            except HuntingQueryError as exc:
                if exc.status_code == 403:
                    log.warning(
                        "_hunt_single_tenant: ThreatHunting.Read.All not granted for tenant=%s, "
                        "skipping all hunting",
                        tid,
                    )
                    return {
                        "status": "skipped",
                        "tenant_id": tid,
                        "reason": "missing_permission",
                    }
                if exc.status_code == 400:
                    log.warning(
                        "_hunt_single_tenant: bad KQL for template=%s tenant=%s: %s",
                        template.name,
                        tid,
                        exc.kql_error,
                    )
                    skipped += 1
                    continue
                log.warning(
                    "_hunt_single_tenant: error on template=%s tenant=%s: %s",
                    template.name,
                    tid,
                    exc,
                )
                skipped += 1
                continue

        run_id = insert_hunt_run(
            tenant_id=tid,
            template_name=template.name,
            question=template.description,
            kql_query=kql,
            result_count=query_result.row_count,
            ai_narrative=None,
        )
        templates_run += 1

        default_severity = _TEMPLATE_SEVERITY.get(template.name, "info")

        for row in query_result.results:
            row_severity = row.get("Severity", "").lower() if row.get("Severity") else ""
            severity = row_severity if row_severity in ("high", "medium", "low", "info") else default_severity

            insert_hunt_result(
                run_id=run_id,
                tenant_id=tid,
                finding_type=template.name,
                severity=severity,
                account_upn=row.get("AccountUpn") or row.get("AccountDisplayName"),
                object_name=row.get("ObjectName") or row.get("Title"),
                action_type=row.get("ActionType"),
                evidence=row,
                detected_at=row.get("Timestamp"),
            )
            total_findings += 1

    log.info(
        "_hunt_single_tenant: tenant=%s templates_run=%d findings=%d skipped=%d",
        tid,
        templates_run,
        total_findings,
        skipped,
    )
    return {
        "status": "ok",
        "tenant_id": tid,
        "templates_run": templates_run,
        "total_findings": total_findings,
        "skipped_templates": skipped,
    }


def _post_to_service_bus(tid: str, display_name: str, department: str, audit_days: int) -> bool:
    """Post a collection message to the tenant-collect queue.

    Returns True on success, False on any failure (caller falls back to
    the in-process executor). MessageId is set to the tenant_id so the
    queue's duplicate-detection window swallows accidental double-fires
    from the same tenant within 10 minutes.
    """
    from shared.config import get_settings

    settings = get_settings()
    if not settings.SERVICE_BUS_NAMESPACE:
        return False
    try:
        from azure.identity import DefaultAzureCredential
        from azure.servicebus import ServiceBusClient, ServiceBusMessage

        body = {
            "tenant_id": tid,
            "display_name": display_name,
            "department": department,
            "audit_days": audit_days,
        }
        with ServiceBusClient(
            fully_qualified_namespace=settings.SERVICE_BUS_NAMESPACE,
            credential=DefaultAzureCredential(),
        ) as client:
            with client.get_queue_sender(queue_name=settings.SERVICE_BUS_QUEUE_NAME) as sender:
                msg = ServiceBusMessage(json.dumps(body).encode("utf-8"), message_id=tid)
                sender.send_messages(msg)
        log.info("_post_to_service_bus: queued tenant=%s", tid)
        return True
    except Exception:
        log.exception("_post_to_service_bus: failed to enqueue tenant=%s — falling back to thread", tid)
        return False


def _trigger_collection_async(tid: str, display_name: str, department: str) -> None:
    """Hand off a collection job for a tenant.

    Preferred path: post a Service Bus message that the queue trigger
    consumes (durable across instance restarts). Fallback: in-process
    ThreadPoolExecutor (only used when SERVICE_BUS_NAMESPACE is unset
    or the post fails — intended for local dev).
    """
    if _COLLECTOR_IMPORT_ERROR is not None:
        log.warning("_trigger_collection_async: collector imports unavailable, skipping tenant=%s", tid)
        return

    from shared.config import get_settings

    settings = get_settings()
    client_id = settings.COLLECTOR_CLIENT_ID
    client_secret = settings.COLLECTOR_CLIENT_SECRET

    if not client_id or not client_secret:
        log.warning("_trigger_collection_async: COLLECTOR_CLIENT_ID/SECRET not configured, skipping")
        return

    if _post_to_service_bus(tid, display_name, department, settings.COLLECTOR_AUDIT_LOG_DAYS):
        return

    log.warning(
        "_trigger_collection_async: Service Bus unavailable, using in-process executor for tenant=%s",
        tid,
    )

    def _run() -> None:
        result = _collect_single_tenant(
            tid=tid,
            display_name=display_name,
            department=department,
            client_id=client_id,
            client_secret=client_secret,
            audit_days=settings.COLLECTOR_AUDIT_LOG_DAYS,
        )
        log.info("_trigger_collection_async: tenant=%s result=%s", tid, result["status"])

    _COLLECTION_EXECUTOR.submit(_run)


# ── HTTP routes ───────────────────────────────────────────────────


@bp.function_name("collect_single")
@bp.route(route="collect/{tenant_id}", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def collect_single(req: func.HttpRequest) -> func.HttpResponse:
    """On-demand: collect compliance data for a specific tenant."""
    try:
        if _COLLECTOR_IMPORT_ERROR is not None:
            return json_response(
                {"error": "Collector modules unavailable", "detail": str(_COLLECTOR_IMPORT_ERROR)}, 503
            )

        tenant_id = req.route_params.get("tenant_id", "").strip()
        if not tenant_id:
            return json_response({"error": "Missing tenant_id in route"}, 400)

        try:
            uuid.UUID(tenant_id)
        except ValueError:
            return json_response({"error": "Invalid tenant_id: must be a valid UUID"}, 400)

        rows = query("SELECT tenant_id, display_name, department FROM tenants WHERE tenant_id = %s", (tenant_id,))
        if not rows:
            return json_response({"error": f"Tenant {tenant_id} not found"}, 404)

        tenant = rows[0]

        from shared.config import get_settings

        settings = get_settings()
        client_id = settings.COLLECTOR_CLIENT_ID
        client_secret = settings.COLLECTOR_CLIENT_SECRET

        if not client_id or not client_secret:
            return json_response({"error": "COLLECTOR_CLIENT_ID/SECRET not configured"}, 503)

        result = _collect_single_tenant(
            tid=tenant["tenant_id"],
            display_name=tenant.get("display_name", ""),
            department=tenant.get("department", ""),
            client_id=client_id,
            client_secret=client_secret,
            audit_days=settings.COLLECTOR_AUDIT_LOG_DAYS,
        )

        status_code = 200 if result["status"] == "ok" else 502
        return json_response(result, status_code)

    except Exception as e:
        log.exception("collect_single error: %s", e)
        return json_response({"error": "Internal server error"}, 500)


@bp.function_name("hunt_single")
@bp.route(route="hunt/{tenant_id}", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def hunt_single(req: func.HttpRequest) -> func.HttpResponse:
    """On-demand: run threat hunting templates for a specific tenant."""
    try:
        if _HUNTER_IMPORT_ERROR is not None:
            return json_response({"error": "Hunter modules unavailable", "detail": str(_HUNTER_IMPORT_ERROR)}, 503)

        tenant_id = req.route_params.get("tenant_id", "").strip()
        if not tenant_id:
            return json_response({"error": "Missing tenant_id in route"}, 400)

        try:
            uuid.UUID(tenant_id)
        except ValueError:
            return json_response({"error": "Invalid tenant_id: must be a valid UUID"}, 400)

        rows = query("SELECT tenant_id FROM tenants WHERE tenant_id = %s", (tenant_id,))
        if not rows:
            return json_response({"error": f"Tenant {tenant_id} not found"}, 404)

        from shared.config import get_settings

        settings = get_settings()
        client_id = settings.COLLECTOR_CLIENT_ID
        client_secret = settings.COLLECTOR_CLIENT_SECRET

        if not client_id or not client_secret:
            return json_response({"error": "COLLECTOR_CLIENT_ID/SECRET not configured"}, 503)

        body, _bad = get_body_or_400(req)
        if _bad is not None:
            return _bad
        days = body.get("days", 30)

        result = _hunt_single_tenant(
            tid=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
            days=days,
        )

        status_code = 200 if result["status"] == "ok" else 502
        return json_response(result, status_code)

    except Exception as e:
        log.exception("hunt_single error: %s", e)
        return json_response({"error": "Internal server error"}, 500)
