"""
Compliance Advisor — Azure Function App

Functions:
- advisor/* routes:     Dashboard API endpoints
- ingest:               HTTP POST — receive compliance payloads from collector
- compute_aggregates:   Timer     — daily compliance trend computation
"""

import hashlib
import json
import logging
import time
import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

import azure.functions as func

app = func.FunctionApp()
log = logging.getLogger(__name__)

# ── Rate limiting for AI endpoints ───────────────────────────────
_RATE_LIMIT_MAX = 10  # max requests per window
_RATE_LIMIT_WINDOW = 60  # window in seconds
_rate_limit_store: dict[str, list[float]] = defaultdict(list)

# ── Background executor for fire-and-forget collection ────────────
_COLLECTION_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="collect")


def _is_rate_limited(client_ip: str) -> bool:
    """Return True if client_ip has exceeded _RATE_LIMIT_MAX requests in the window."""
    now = time.monotonic()
    timestamps = _rate_limit_store[client_ip]
    # Prune expired entries
    _rate_limit_store[client_ip] = [t for t in timestamps if now - t < _RATE_LIMIT_WINDOW]
    if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT_MAX:
        return True
    _rate_limit_store[client_ip].append(now)
    return False


def _get_client_ip(req: func.HttpRequest) -> str:
    """Extract client IP from X-Forwarded-For header or fall back to 'unknown'."""
    forwarded = req.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return "unknown"


_DEPENDENCY_IMPORT_ERROR: Exception | None = None

try:
    from shared.ai_advisor import AdvisorAIError, ask_advisor, generate_briefing
    from shared.auth import get_auth_error_response, require_auth
    from shared.dashboard_queries import (
        get_audit,
        get_compliance_assessments,
        get_dlp,
        get_dlp_policies,
        get_governance,
        get_hunt_results,
        get_improvement_actions,
        get_info_barriers,
        get_irm,
        get_irm_policies,
        get_labels,
        get_overview,
        get_purview_incidents,
        get_purview_insights,
        get_status,
        get_threat_assessments,
        get_trend,
    )
    from shared.db import (
        check_ingestion_duplicate,
        query,
        record_ingestion,
        update_tenant_status,
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
        upsert_trend,
        upsert_user_content_policies,
    )
    from shared.validation import validate_ingestion_request
except Exception as e:
    _DEPENDENCY_IMPORT_ERROR = e
    log.exception("Function dependency import failed at startup: %s", e)

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


def _ensure_dependencies_loaded() -> None:
    if _DEPENDENCY_IMPORT_ERROR is not None:
        error_detail = f"{type(_DEPENDENCY_IMPORT_ERROR).__name__}: {_DEPENDENCY_IMPORT_ERROR}"
        raise RuntimeError(f"Function dependencies failed to load: {error_detail}")


def _json_response(data: dict, status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps(data, default=str),
        status_code=status_code,
        mimetype="application/json",
    )


def _get_body(req: func.HttpRequest) -> dict:
    try:
        return req.get_json()
    except ValueError:
        log.warning("Failed to parse JSON body — returning empty dict")
        return {}


# ── Health Check ──────────────────────────────────────────────────


@app.function_name("health")
@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        from shared.db import _get_pool

        pool = _get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            pool.putconn(conn)
        return _json_response({"status": "healthy"})
    except Exception as e:
        log.exception("health check failed: %s", e)
        return _json_response({"status": "unhealthy", "error": str(e)}, 503)


# ── Dashboard API Routes ──────────────────────────────────────────


@app.function_name("advisor_status")
@app.route(route="advisor/status", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_status(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        return _json_response(get_status())
    except Exception as e:
        log.exception("advisor/status error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_overview")
@app.route(route="advisor/overview", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_overview(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        return _json_response(get_overview(department=body.get("department"), tenant_id=body.get("tenant_id")))
    except Exception as e:
        log.exception("advisor/overview error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_labels")
@app.route(route="advisor/labels", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_labels(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        return _json_response(get_labels(department=body.get("department"), tenant_id=body.get("tenant_id")))
    except Exception as e:
        log.exception("advisor/labels error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_audit")
@app.route(route="advisor/audit", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_audit(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        return _json_response(get_audit(department=body.get("department"), tenant_id=body.get("tenant_id")))
    except Exception as e:
        log.exception("advisor/audit error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_dlp")
@app.route(route="advisor/dlp", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_dlp(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        return _json_response(get_dlp(department=body.get("department"), tenant_id=body.get("tenant_id")))
    except Exception as e:
        log.exception("advisor/dlp error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_irm")
@app.route(route="advisor/irm", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_irm(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        return _json_response(get_irm(department=body.get("department"), tenant_id=body.get("tenant_id")))
    except Exception as e:
        log.exception("advisor/irm error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_purview_incidents")
@app.route(route="advisor/purview-incidents", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_purview_incidents(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        return _json_response(get_purview_incidents(department=body.get("department"), tenant_id=body.get("tenant_id")))
    except Exception as e:
        log.exception("advisor/purview-incidents error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_info_barriers")
@app.route(route="advisor/info-barriers", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_info_barriers(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        return _json_response(get_info_barriers(department=body.get("department"), tenant_id=body.get("tenant_id")))
    except Exception as e:
        log.exception("advisor/info-barriers error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_governance")
@app.route(route="advisor/governance", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_governance(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        return _json_response(get_governance(department=body.get("department"), tenant_id=body.get("tenant_id")))
    except Exception as e:
        log.exception("advisor/governance error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_trend")
@app.route(route="advisor/trend", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_trend(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        try:
            days = int(body.get("days", 30))
        except (TypeError, ValueError):
            return _json_response({"error": "Invalid 'days' parameter — must be an integer"}, 400)
        if days < 1 or days > 365:
            return _json_response({"error": "Invalid 'days' parameter — must be between 1 and 365"}, 400)
        return _json_response(
            get_trend(
                department=body.get("department"),
                days=days,
                tenant_id=body.get("tenant_id"),
            )
        )
    except Exception as e:
        log.exception("advisor/trend error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_purview_insights")
@app.route(route="advisor/purview-insights", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_purview_insights(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        try:
            days = int(body.get("days", 30))
        except (TypeError, ValueError):
            return _json_response({"error": "Invalid 'days' parameter — must be an integer"}, 400)
        if days < 1 or days > 365:
            return _json_response({"error": "Invalid 'days' parameter — must be between 1 and 365"}, 400)
        return _json_response(
            get_purview_insights(
                department=body.get("department"),
                tenant_id=body.get("tenant_id"),
                days=days,
            )
        )
    except Exception as e:
        log.exception("advisor/purview-insights error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_actions")
@app.route(route="advisor/actions", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_actions(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        result = get_improvement_actions(department=body.get("department"), tenant_id=body.get("tenant_id"))
        return _json_response(result)
    except Exception as e:
        log.exception("advisor/actions error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_dlp_policies")
@app.route(route="advisor/dlp-policies", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_dlp_policies(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        return _json_response(get_dlp_policies(department=body.get("department"), tenant_id=body.get("tenant_id")))
    except Exception as e:
        log.exception("advisor/dlp-policies error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_irm_policies")
@app.route(route="advisor/irm-policies", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_irm_policies(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        return _json_response(get_irm_policies(department=body.get("department"), tenant_id=body.get("tenant_id")))
    except Exception as e:
        log.exception("advisor/irm-policies error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_assessments")
@app.route(route="advisor/assessments", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_assessments(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        result = get_compliance_assessments(department=body.get("department"), tenant_id=body.get("tenant_id"))
        return _json_response(result)
    except Exception as e:
        log.exception("advisor/assessments error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_threat_assessments")
@app.route(route="advisor/threat-assessments", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_threat_assessments(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        result = get_threat_assessments(department=body.get("department"), tenant_id=body.get("tenant_id"))
        return _json_response(result)
    except Exception as e:
        log.exception("advisor/threat-assessments error: %s", e)
        return _json_response({"error": str(e)}, 500)


# ── Threat Hunting ────────────────────────────────────────────────


@app.function_name("advisor_hunt_results")
@app.route(route="advisor/hunt-results", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_hunt_results(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body = _get_body(req)
        result = get_hunt_results(
            department=body.get("department"),
            tenant_id=body.get("tenant_id"),
            severity=body.get("severity"),
            days=body.get("days", 30),
        )
        return _json_response(result)
    except Exception as e:
        log.exception("advisor/hunt-results error: %s", e)
        return _json_response({"error": str(e)}, 500)


# ── AI Advisor ────────────────────────────────────────────────────


@app.function_name("advisor_briefing")
@app.route(route="advisor/briefing", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_briefing(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        if _is_rate_limited(_get_client_ip(req)):
            return _json_response({"error": "Rate limit exceeded. Max 10 requests per minute."}, 429)
        body = _get_body(req)
        briefing = generate_briefing(department=body.get("department"), tenant_id=body.get("tenant_id"))
        return _json_response({"briefing": briefing})
    except AdvisorAIError as e:
        log.exception("advisor/briefing AI error: %s", e)
        return _json_response({"error": str(e)}, 502)
    except Exception as e:
        log.exception("advisor/briefing error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_ask")
@app.route(route="advisor/ask", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_ask(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        if _is_rate_limited(_get_client_ip(req)):
            return _json_response({"error": "Rate limit exceeded. Max 10 requests per minute."}, 429)
        body = _get_body(req)
        question = body.get("question", "").strip()
        if not question:
            return _json_response({"error": "Missing required field: question"}, 400)
        answer = ask_advisor(question=question, department=body.get("department"), tenant_id=body.get("tenant_id"))
        return _json_response({"answer": answer})
    except AdvisorAIError as e:
        log.exception("advisor/ask AI error: %s", e)
        return _json_response({"error": str(e)}, 502)
    except Exception as e:
        log.exception("advisor/ask error: %s", e)
        return _json_response({"error": str(e)}, 500)


# ── Tenant Registration ───────────────────────────────────────────


@app.function_name("register_tenant")
@app.route(route="tenants", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def register_tenant(req: func.HttpRequest) -> func.HttpResponse:
    """Register or update a tenant."""
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)

        tenant_id = body.get("tenant_id", "").strip()
        if not tenant_id:
            return _json_response({"error": "Missing required field: tenant_id"}, 400)
        try:
            uuid.UUID(tenant_id)
        except ValueError:
            return _json_response({"error": "Invalid tenant_id: must be a valid UUID"}, 400)

        display_name = body.get("display_name", "").strip()
        if not display_name:
            return _json_response({"error": "Missing required field: display_name"}, 400)

        department = body.get("department", "").strip()
        if not department:
            return _json_response({"error": "Missing required field: department"}, 400)

        risk_tier = body.get("risk_tier", "Medium")

        upsert_tenant(
            tenant_id=tenant_id,
            display_name=display_name,
            department=department,
            risk_tier=risk_tier,
        )

        _trigger_collection_async(tenant_id, display_name, department)

        log.info("Registered tenant: %s (%s, %s)", tenant_id, display_name, department)
        return _json_response({"status": "ok", "tenant_id": tenant_id, "collection": "triggered"})

    except Exception as e:
        log.exception("register_tenant error: %s", e)
        return _json_response({"error": "Internal server error"}, 500)


@app.function_name("tenant_consent_callback")
@app.route(route="tenants/callback", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def tenant_consent_callback(req: func.HttpRequest) -> func.HttpResponse:
    """Handle Azure AD admin consent redirect — auto-register the tenant."""
    try:
        _ensure_dependencies_loaded()

        error = req.params.get("error")
        if error:
            error_desc = req.params.get("error_description", "Unknown error")
            log.warning("Admin consent failed: %s — %s", error, error_desc)
            return func.HttpResponse(
                _CONSENT_ERROR_HTML.replace("{{error}}", error_desc),
                status_code=400,
                mimetype="text/html",
            )

        tenant_id = req.params.get("tenant", "").strip()
        admin_consent = req.params.get("admin_consent", "").lower()

        if admin_consent != "true" or not tenant_id:
            return func.HttpResponse(
                _CONSENT_ERROR_HTML.replace("{{error}}", "Admin consent was not granted."),
                status_code=400,
                mimetype="text/html",
            )

        try:
            uuid.UUID(tenant_id)
        except ValueError:
            return func.HttpResponse(
                _CONSENT_ERROR_HTML.replace("{{error}}", "Invalid tenant ID returned."),
                status_code=400,
                mimetype="text/html",
            )

        upsert_tenant(
            tenant_id=tenant_id,
            display_name=f"Tenant {tenant_id[:8]}",
            department="Pending",
            status="pending",
        )

        _trigger_collection_async(tenant_id, f"Tenant {tenant_id[:8]}", "Pending")

        log.info("Tenant registered via admin consent: %s", tenant_id)
        return func.HttpResponse(
            _CONSENT_SUCCESS_HTML.replace("{{tenant_id}}", tenant_id),
            status_code=200,
            mimetype="text/html",
        )

    except Exception as e:
        log.exception("tenant_consent_callback error: %s", e)
        return func.HttpResponse(
            _CONSENT_ERROR_HTML.replace("{{error}}", "Internal server error."),
            status_code=500,
            mimetype="text/html",
        )


_CONSENT_SUCCESS_HTML = """<!DOCTYPE html>
<html><head><title>Tenant Registered</title>
<style>body{font-family:system-ui,sans-serif;max-width:600px;margin:80px auto;text-align:center}
.ok{color:#16a34a;font-size:48px}h1{margin:8px 0}code{background:#f1f5f9;padding:2px 8px;border-radius:4px}</style>
</head><body>
<div class="ok">&#10003;</div>
<h1>Tenant Registered</h1>
<p>Tenant <code>{{tenant_id}}</code> has been registered with Compliance Advisor.</p>
<p>Data collection has been triggered and will complete shortly.</p>
<p><small>The Compliance Advisor admin can update your display name and department.</small></p>
</body></html>"""

_CONSENT_ERROR_HTML = """<!DOCTYPE html>
<html><head><title>Consent Failed</title>
<style>body{font-family:system-ui,sans-serif;max-width:600px;margin:80px auto;text-align:center}
.err{color:#dc2626;font-size:48px}h1{margin:8px 0}</style>
</head><body>
<div class="err">&#10007;</div>
<h1>Consent Failed</h1>
<p>{{error}}</p>
<p>Please contact the Compliance Advisor administrator.</p>
</body></html>"""


# ── Ingestion ─────────────────────────────────────────────────────


@app.function_name("ingest_compliance")
@app.route(route="ingest", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def ingest_compliance(req: func.HttpRequest) -> func.HttpResponse:
    """Receive JSON payload from per-tenant collector."""
    try:
        _ensure_dependencies_loaded()
        payload = validate_ingestion_request(req)
        snapshot_date = payload["timestamp"][:10]
        tenant_id = payload["tenant_id"]

        # Idempotency: skip re-processing exact duplicate submissions
        payload_hash = hashlib.sha256(req.get_body()).hexdigest()
        if check_ingestion_duplicate(tenant_id, snapshot_date, payload_hash):
            log.info("Duplicate ingest skipped: tenant=%s snapshot=%s", tenant_id, snapshot_date)
            return _json_response({"status": "ok", "tenant_id": tenant_id, "duplicate": True})

        # Upsert tenant
        upsert_tenant(
            tenant_id=tenant_id,
            display_name=payload["display_name"],
            department=payload["department"],
        )

        # Upsert sensitivity labels
        for sl in payload.get("sensitivity_labels", []):
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

        # Upsert retention events
        for re_ in payload.get("retention_events", []):
            upsert_retention_event(
                tenant_id=tenant_id,
                event_id=re_.get("event_id", ""),
                display_name=re_.get("display_name", ""),
                event_type=re_.get("event_type", ""),
                created=re_.get("created", ""),
                event_status=re_.get("event_status", ""),
                snapshot_date=snapshot_date,
            )

        # Upsert retention event types
        for ret in payload.get("retention_event_types", []):
            upsert_retention_event_type(
                tenant_id=tenant_id,
                event_type_id=ret.get("event_type_id", ""),
                display_name=ret.get("display_name", ""),
                description=ret.get("description", ""),
                created=ret.get("created", ""),
                modified=ret.get("modified", ""),
                snapshot_date=snapshot_date,
            )

        # Upsert retention labels
        for rl in payload.get("retention_labels", []):
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

        # Upsert audit records
        for ar in payload.get("audit_records", []):
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

        # Upsert DLP alerts
        for da in payload.get("dlp_alerts", []):
            upsert_dlp_alert(
                tenant_id=tenant_id,
                alert_id=da.get("alert_id", ""),
                title=da.get("title", ""),
                severity=da.get("severity", ""),
                status=da.get("status", ""),
                category=da.get("category", ""),
                policy_name=da.get("policy_name", ""),
                created=da.get("created", ""),
                resolved=da.get("resolved", ""),
                snapshot_date=snapshot_date,
                description=da.get("description", ""),
                assigned_to=da.get("assigned_to", ""),
                classification=da.get("classification", ""),
                determination=da.get("determination", ""),
                recommended_actions=da.get("recommended_actions", ""),
                incident_id=da.get("incident_id", ""),
                mitre_techniques=da.get("mitre_techniques", ""),
                evidence=da.get("evidence", []),
            )

        # Upsert protection scopes
        for ps in payload.get("protection_scopes", []):
            upsert_protection_scope(
                tenant_id=tenant_id,
                scope_type=ps.get("scope_type", ""),
                execution_mode=ps.get("execution_mode", ""),
                locations=ps.get("locations", ""),
                activity_types=ps.get("activity_types", ""),
                snapshot_date=snapshot_date,
            )

        # Upsert IRM alerts
        for ia in payload.get("irm_alerts", []):
            upsert_irm_alert(
                tenant_id=tenant_id,
                alert_id=ia.get("alert_id", ""),
                title=ia.get("title", ""),
                severity=ia.get("severity", ""),
                status=ia.get("status", ""),
                category=ia.get("category", ""),
                policy_name=ia.get("policy_name", ""),
                created=ia.get("created", ""),
                resolved=ia.get("resolved", ""),
                snapshot_date=snapshot_date,
                description=ia.get("description", ""),
                assigned_to=ia.get("assigned_to", ""),
                classification=ia.get("classification", ""),
                determination=ia.get("determination", ""),
                recommended_actions=ia.get("recommended_actions", ""),
                incident_id=ia.get("incident_id", ""),
                mitre_techniques=ia.get("mitre_techniques", ""),
                evidence=ia.get("evidence", []),
            )

        # Upsert information barrier policies
        for ib in payload.get("info_barrier_policies", []):
            upsert_info_barrier_policy(
                tenant_id=tenant_id,
                policy_id=ib.get("policy_id", ""),
                display_name=ib.get("display_name", ""),
                state=ib.get("state", ""),
                segments_applied=ib.get("segments_applied", ""),
                snapshot_date=snapshot_date,
            )

        # Upsert secure scores
        for ss in payload.get("secure_scores", []):
            upsert_secure_score(
                tenant_id=tenant_id,
                current_score=ss.get("current_score", 0),
                max_score=ss.get("max_score", 0),
                score_date=ss.get("score_date", snapshot_date),
                snapshot_date=snapshot_date,
                data_current_score=ss.get("data_current_score", 0),
                data_max_score=ss.get("data_max_score", 0),
            )

        # Upsert improvement actions
        for ia in payload.get("improvement_actions", []):
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

        # Upsert user content policies
        upsert_user_content_policies(
            tenant_id=tenant_id,
            records=payload.get("user_content_policies", []),
            snapshot_date=snapshot_date,
        )

        # Upsert DLP policies
        for dp in payload.get("dlp_policies", []):
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

        # Upsert IRM policies
        for ip in payload.get("irm_policies", []):
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

        # Upsert sensitive info types
        for si in payload.get("sensitive_info_types", []):
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

        # Upsert compliance assessments
        for ca in payload.get("compliance_assessments", []):
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

        # Upsert threat assessment requests
        for ta in payload.get("threat_assessment_requests", []):
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

        # Upsert Purview-prioritized incidents
        for pi in payload.get("purview_incidents", []):
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

        counts = {
            "sensitivity_labels": len(payload.get("sensitivity_labels", [])),
            "audit_records": len(payload.get("audit_records", [])),
            "dlp_alerts": len(payload.get("dlp_alerts", [])),
            "irm_alerts": len(payload.get("irm_alerts", [])),
            "info_barrier_policies": len(payload.get("info_barrier_policies", [])),
            "protection_scopes": len(payload.get("protection_scopes", [])),
            "dlp_policies": len(payload.get("dlp_policies", [])),
            "irm_policies": len(payload.get("irm_policies", [])),
            "sensitive_info_types": len(payload.get("sensitive_info_types", [])),
            "compliance_assessments": len(payload.get("compliance_assessments", [])),
            "threat_assessment_requests": len(payload.get("threat_assessment_requests", [])),
            "purview_incidents": len(payload.get("purview_incidents", [])),
        }
        record_ingestion(tenant_id, snapshot_date, payload_hash, counts)

        log.info(
            "Ingested: tenant=%s dept=%s labels=%d audit=%d dlp=%d "
            "irm=%d info_barriers=%d scopes=%d scores=%d actions=%d "
            "dlp_policies=%d irm_policies=%d sit=%d assessments=%d threats=%d incidents=%d",
            tenant_id,
            payload["department"],
            counts["sensitivity_labels"],
            counts["audit_records"],
            counts["dlp_alerts"],
            counts["irm_alerts"],
            counts["info_barrier_policies"],
            counts["protection_scopes"],
            len(payload.get("secure_scores", [])),
            len(payload.get("improvement_actions", [])),
            counts["dlp_policies"],
            counts["irm_policies"],
            counts["sensitive_info_types"],
            counts["compliance_assessments"],
            counts["threat_assessment_requests"],
            counts["purview_incidents"],
        )
        return _json_response({"status": "ok", "tenant_id": tenant_id, **counts})

    except ValueError as e:
        log.warning("Validation failed: %s", e)
        return _json_response({"error": str(e)}, 400)
    except Exception as e:
        log.exception("Ingestion error: %s", e)
        return _json_response({"error": "Internal server error"}, 500)


# ── Per-tenant collection helper ──────────────────────────────────


def _collect_single_tenant(
    tid: str,
    display_name: str,
    department: str,
    client_id: str,
    client_secret: str,
    audit_days: int = 1,
) -> dict:
    """Collect compliance data from a single tenant and upsert to the database.

    Returns a dict with 'status' ('ok' or 'error') and record counts or error message.
    Raises nothing — all errors are caught and returned in the dict.
    """
    from datetime import date
    from types import SimpleNamespace

    today = date.today().isoformat()
    try:
        auth_settings = SimpleNamespace(
            TENANT_ID=tid,
            CLIENT_ID=client_id,
            CLIENT_SECRET=client_secret,
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

        upsert_tenant(tenant_id=tid, display_name=display_name, department=department)

        for sl in sensitivity:
            upsert_sensitivity_label(
                tenant_id=tid,
                label_id=sl.get("label_id", ""),
                name=sl.get("name", ""),
                description=sl.get("description", ""),
                color=sl.get("color", ""),
                is_active=sl.get("is_active", True),
                parent_id=sl.get("parent_id", ""),
                priority=sl.get("priority", 0),
                tooltip=sl.get("tooltip", ""),
                snapshot_date=today,
                has_protection=sl.get("has_protection", False),
                applicable_to=sl.get("applicable_to", ""),
                application_mode=sl.get("application_mode", ""),
                is_endpoint_protection_enabled=sl.get("is_endpoint_protection_enabled", False),
            )
        for re_ in ret_events:
            upsert_retention_event(
                tenant_id=tid,
                event_id=re_.get("event_id", ""),
                display_name=re_.get("display_name", ""),
                event_type=re_.get("event_type", ""),
                created=re_.get("created", ""),
                event_status=re_.get("event_status", ""),
                snapshot_date=today,
            )
        for ret in ret_event_types:
            upsert_retention_event_type(
                tenant_id=tid,
                event_type_id=ret.get("event_type_id", ""),
                display_name=ret.get("display_name", ""),
                description=ret.get("description", ""),
                created=ret.get("created", ""),
                modified=ret.get("modified", ""),
                snapshot_date=today,
            )
        for rl in ret_labels:
            upsert_retention_label(
                tenant_id=tid,
                label_id=rl.get("label_id", ""),
                name=rl.get("name", ""),
                description=rl.get("description", ""),
                is_in_use=rl.get("is_in_use", False),
                retention_duration=rl.get("retention_duration", ""),
                action_after=rl.get("action_after", ""),
                default_record_behavior=rl.get("default_record_behavior", ""),
                created=rl.get("created", ""),
                modified=rl.get("modified", ""),
                snapshot_date=today,
            )
        for ar in audit:
            upsert_audit_record(
                tenant_id=tid,
                record_id=ar.get("record_id", ""),
                record_type=ar.get("record_type", ""),
                operation=ar.get("operation", ""),
                service=ar.get("service", ""),
                user_id=ar.get("user_id", ""),
                created=ar.get("created", ""),
                snapshot_date=today,
                ip_address=ar.get("ip_address", ""),
                client_app=ar.get("client_app", ""),
                result_status=ar.get("result_status", ""),
            )
        for da in dlp:
            upsert_dlp_alert(
                tenant_id=tid,
                alert_id=da.get("alert_id", ""),
                title=da.get("title", ""),
                severity=da.get("severity", ""),
                status=da.get("status", ""),
                category=da.get("category", ""),
                policy_name=da.get("policy_name", ""),
                created=da.get("created", ""),
                resolved=da.get("resolved", ""),
                snapshot_date=today,
                description=da.get("description", ""),
                assigned_to=da.get("assigned_to", ""),
                classification=da.get("classification", ""),
                determination=da.get("determination", ""),
                recommended_actions=da.get("recommended_actions", ""),
                incident_id=da.get("incident_id", ""),
                mitre_techniques=da.get("mitre_techniques", ""),
                evidence=da.get("evidence", []),
            )
        for ps in scopes:
            upsert_protection_scope(
                tenant_id=tid,
                scope_type=ps.get("scope_type", ""),
                execution_mode=ps.get("execution_mode", ""),
                locations=ps.get("locations", ""),
                activity_types=ps.get("activity_types", ""),
                snapshot_date=today,
            )
        for ia in irm:
            upsert_irm_alert(
                tenant_id=tid,
                alert_id=ia.get("alert_id", ""),
                title=ia.get("title", ""),
                severity=ia.get("severity", ""),
                status=ia.get("status", ""),
                category=ia.get("category", ""),
                policy_name=ia.get("policy_name", ""),
                created=ia.get("created", ""),
                resolved=ia.get("resolved", ""),
                snapshot_date=today,
                description=ia.get("description", ""),
                assigned_to=ia.get("assigned_to", ""),
                classification=ia.get("classification", ""),
                determination=ia.get("determination", ""),
                recommended_actions=ia.get("recommended_actions", ""),
                incident_id=ia.get("incident_id", ""),
                mitre_techniques=ia.get("mitre_techniques", ""),
                evidence=ia.get("evidence", []),
            )
        for pi in incidents:
            upsert_purview_incident(
                tenant_id=tid,
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
                snapshot_date=today,
            )
        for b in ib:
            upsert_info_barrier_policy(
                tenant_id=tid,
                policy_id=b.get("policy_id", ""),
                display_name=b.get("display_name", ""),
                state=b.get("state", ""),
                segments_applied=b.get("segments_applied", ""),
                snapshot_date=today,
            )
        for ss in scores:
            upsert_secure_score(
                tenant_id=tid,
                current_score=ss.get("current_score", 0),
                max_score=ss.get("max_score", 0),
                score_date=ss.get("score_date", today),
                snapshot_date=today,
                data_current_score=ss.get("data_current_score", 0),
                data_max_score=ss.get("data_max_score", 0),
            )
        for ia in actions:
            upsert_improvement_action(
                tenant_id=tid,
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
                snapshot_date=today,
            )
        upsert_user_content_policies(tenant_id=tid, records=ucp, snapshot_date=today)
        for dp in dlp_pol:
            upsert_dlp_policy(
                tenant_id=tid,
                policy_id=dp.get("policy_id", ""),
                display_name=dp.get("display_name", ""),
                status=dp.get("status", ""),
                policy_type=dp.get("policy_type", ""),
                rules_count=dp.get("rules_count", 0),
                created=dp.get("created", ""),
                modified=dp.get("modified", ""),
                mode=dp.get("mode", ""),
                snapshot_date=today,
            )
        for ip in irm_pol:
            upsert_irm_policy(
                tenant_id=tid,
                policy_id=ip.get("policy_id", ""),
                display_name=ip.get("display_name", ""),
                status=ip.get("status", ""),
                policy_type=ip.get("policy_type", ""),
                created=ip.get("created", ""),
                triggers=ip.get("triggers", ""),
                snapshot_date=today,
            )
        for si in sit:
            upsert_sensitive_info_type(
                tenant_id=tid,
                type_id=si.get("type_id", ""),
                name=si.get("name", ""),
                description=si.get("description", ""),
                is_custom=si.get("is_custom", False),
                category=si.get("category", ""),
                scope=si.get("scope", ""),
                state=si.get("state", ""),
                snapshot_date=today,
            )
        for ca in assessments:
            upsert_compliance_assessment(
                tenant_id=tid,
                assessment_id=ca.get("assessment_id", ""),
                display_name=ca.get("display_name", ""),
                status=ca.get("status", ""),
                framework=ca.get("framework", ""),
                completion_percentage=ca.get("completion_percentage", 0),
                created=ca.get("created", ""),
                category=ca.get("category", ""),
                snapshot_date=today,
            )

        for ta in threats:
            upsert_threat_assessment_request(
                tenant_id=tid,
                request_id=ta.get("request_id", ""),
                category=ta.get("category", ""),
                content_type=ta.get("content_type", ""),
                status=ta.get("status", ""),
                created=ta.get("created", ""),
                result_type=ta.get("result_type", ""),
                result_message=ta.get("result_message", ""),
                snapshot_date=today,
            )

        counts = {
            "sensitivity_labels": len(sensitivity),
            "audit_records": len(audit),
            "dlp_alerts": len(dlp),
            "irm_alerts": len(irm),
            "secure_scores": len(scores),
            "improvement_actions": len(actions),
            "threat_assessments": len(threats),
            "purview_incidents": len(incidents),
        }
        log.info("_collect_single_tenant: tenant=%s dept=%s counts=%s", tid, department, counts)
        try:
            update_tenant_status(tid, "active")
        except Exception:
            log.debug("update_tenant_status not available yet (run schema migration)")
        return {"status": "ok", "tenant_id": tid, "record_counts": counts}

    except Exception as e:
        log.exception("_collect_single_tenant: failed for tenant=%s: %s", tid, e)
        try:
            update_tenant_status(tid, "error")
        except Exception:
            pass
        return {"status": "error", "tenant_id": tid, "error": str(e)}


# ── Timer: Auto-collect from all tenants ──────────────────────────


@app.function_name("collect_tenants")
@app.timer_trigger(schedule="0 0 2 * * *", arg_name="timer", run_on_startup=False)
def collect_tenants(timer: func.TimerRequest) -> None:
    """Daily at 2:00 AM UTC: collect compliance data from all registered tenants."""
    try:
        _ensure_dependencies_loaded()

        from shared.config import get_settings

        settings = get_settings()
        client_id = settings.COLLECTOR_CLIENT_ID
        client_secret = settings.COLLECTOR_CLIENT_SECRET

        if not client_id or not client_secret:
            log.warning("collect_tenants: COLLECTOR_CLIENT_ID/SECRET not configured, skipping")
            return

        if _COLLECTOR_IMPORT_ERROR is not None:
            log.error("collect_tenants: collector imports failed at startup: %s", _COLLECTOR_IMPORT_ERROR)
            return

        audit_days = settings.COLLECTOR_AUDIT_LOG_DAYS

        tenants = query("SELECT tenant_id, display_name, department FROM tenants")
        if not tenants:
            log.info("collect_tenants: no tenants registered, skipping")
            return

        successes = 0
        failures = 0

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(
                    _collect_single_tenant,
                    tid=tenant["tenant_id"],
                    display_name=tenant.get("display_name", ""),
                    department=tenant.get("department", ""),
                    client_id=client_id,
                    client_secret=client_secret,
                    audit_days=audit_days,
                ): tenant["tenant_id"]
                for tenant in tenants
            }

            for future in as_completed(futures):
                tid = futures[future]
                try:
                    result = future.result()
                    if result["status"] == "ok":
                        successes += 1
                    else:
                        failures += 1
                except Exception:
                    log.exception("collect_tenants: unhandled error for tenant=%s", tid)
                    failures += 1

        log.info("collect_tenants: completed — %d succeeded, %d failed", successes, failures)

    except Exception as e:
        log.exception("collect_tenants: fatal error: %s", e)


# ── On-demand collection ──────────────────────────────────────────


def _trigger_collection_async(tid: str, display_name: str, department: str) -> None:
    """Fire-and-forget collection for a single tenant in a daemon thread."""
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


@app.function_name("collect_single")
@app.route(route="collect/{tenant_id}", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def collect_single(req: func.HttpRequest) -> func.HttpResponse:
    """On-demand: collect compliance data for a specific tenant."""
    try:
        _ensure_dependencies_loaded()

        if _COLLECTOR_IMPORT_ERROR is not None:
            return _json_response(
                {"error": "Collector modules unavailable", "detail": str(_COLLECTOR_IMPORT_ERROR)}, 503
            )

        tenant_id = req.route_params.get("tenant_id", "").strip()
        if not tenant_id:
            return _json_response({"error": "Missing tenant_id in route"}, 400)

        try:
            uuid.UUID(tenant_id)
        except ValueError:
            return _json_response({"error": "Invalid tenant_id: must be a valid UUID"}, 400)

        rows = query("SELECT tenant_id, display_name, department FROM tenants WHERE tenant_id = %s", (tenant_id,))
        if not rows:
            return _json_response({"error": f"Tenant {tenant_id} not found"}, 404)

        tenant = rows[0]

        from shared.config import get_settings

        settings = get_settings()
        client_id = settings.COLLECTOR_CLIENT_ID
        client_secret = settings.COLLECTOR_CLIENT_SECRET

        if not client_id or not client_secret:
            return _json_response({"error": "COLLECTOR_CLIENT_ID/SECRET not configured"}, 503)

        result = _collect_single_tenant(
            tid=tenant["tenant_id"],
            display_name=tenant.get("display_name", ""),
            department=tenant.get("department", ""),
            client_id=client_id,
            client_secret=client_secret,
            audit_days=settings.COLLECTOR_AUDIT_LOG_DAYS,
        )

        status_code = 200 if result["status"] == "ok" else 502
        return _json_response(result, status_code)

    except Exception as e:
        log.exception("collect_single error: %s", e)
        return _json_response({"error": "Internal server error"}, 500)


# ── Timer: Compute daily trend ────────────────────────────────────


@app.function_name("compute_aggregates")
@app.timer_trigger(schedule="0 0 6 * * *", arg_name="timer", run_on_startup=False)
def compute_aggregates(timer: func.TimerRequest) -> None:
    """Daily at 6:00 AM UTC: compute compliance workload trend rows."""
    try:
        _ensure_dependencies_loaded()
        from datetime import date

        today = date.today().isoformat()

        # Get per-tenant counts for each workload
        tenant_counts = query("""
            SELECT t.tenant_id, t.department,
                (SELECT COUNT(*) FROM sensitivity_labels sl
                 WHERE sl.tenant_id = t.tenant_id
                   AND sl.snapshot_date = (
                     SELECT MAX(snapshot_date) FROM sensitivity_labels
                     WHERE tenant_id = t.tenant_id)
                )::int AS sensitivity,
                (SELECT COUNT(*) FROM dlp_alerts da
                 WHERE da.tenant_id = t.tenant_id
                   AND da.snapshot_date = (
                     SELECT MAX(snapshot_date) FROM dlp_alerts
                     WHERE tenant_id = t.tenant_id)
                )::int AS dlp,
                (SELECT COUNT(*) FROM audit_records ar
                 WHERE ar.tenant_id = t.tenant_id
                   AND ar.snapshot_date = (
                     SELECT MAX(snapshot_date) FROM audit_records
                     WHERE tenant_id = t.tenant_id)
                )::int AS audit
            FROM tenants t
            """)

        if not tenant_counts:
            log.info("No tenants found, skipping aggregate computation")
            return

        # Statewide aggregate
        upsert_trend(
            snapshot_date=today,
            department=None,
            sensitivity_labels=sum(r["sensitivity"] for r in tenant_counts),
            dlp_alerts=sum(r["dlp"] for r in tenant_counts),
            audit_records=sum(r["audit"] for r in tenant_counts),
            tenant_count=len(tenant_counts),
        )

        # Per-department aggregates
        depts: dict[str, list] = {}
        for r in tenant_counts:
            dept = r.get("department")
            if dept:
                depts.setdefault(dept, []).append(r)

        for dept, rows in depts.items():
            upsert_trend(
                snapshot_date=today,
                department=dept,
                sensitivity_labels=sum(r["sensitivity"] for r in rows),
                dlp_alerts=sum(r["dlp"] for r in rows),
                audit_records=sum(r["audit"] for r in rows),
                tenant_count=len(rows),
            )

        log.info("Computed trend aggregates: %d tenants, %d departments", len(tenant_counts), len(depts))

    except Exception as e:
        log.exception("Aggregate computation failed: %s", e)
