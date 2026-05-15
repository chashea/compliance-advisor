"""Dashboard read-only routes (POST advisor/*).

Each route here either:

- Is a one-line ``register_advisor_route(bp, name, get_xxx)`` call when it
  only forwards ``department`` and ``tenant_id`` from the request body.
- Has an explicit handler when it accepts additional parameters (currently
  ``trend`` and ``purview-insights``, both of which take ``days``).
"""

from __future__ import annotations

import logging

import azure.functions as func
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

from routes._decorator import get_body_or_400, json_response, register_advisor_route

log = logging.getLogger(__name__)

bp = func.Blueprint()

# ── Simple read-only routes (registered via decorator) ───────────

# advisor/status takes no body
register_advisor_route(bp, "status", lambda **_kw: get_status(), body_args=())

register_advisor_route(bp, "overview", get_overview)
register_advisor_route(bp, "labels", get_labels)
register_advisor_route(bp, "audit", get_audit)
register_advisor_route(bp, "dlp", get_dlp)
register_advisor_route(bp, "irm", get_irm)
register_advisor_route(bp, "purview-incidents", get_purview_incidents)
register_advisor_route(bp, "info-barriers", get_info_barriers)
register_advisor_route(bp, "governance", get_governance)
register_advisor_route(bp, "actions", get_improvement_actions)
register_advisor_route(bp, "dlp-policies", get_dlp_policies)
register_advisor_route(bp, "irm-policies", get_irm_policies)
register_advisor_route(bp, "assessments", get_compliance_assessments)
register_advisor_route(bp, "threat-assessments", get_threat_assessments)


# ── Routes with extra body params (explicit handlers) ────────────


def _validated_days(body: dict) -> int | func.HttpResponse:
    try:
        days = int(body.get("days", 30))
    except (TypeError, ValueError):
        return json_response({"error": "Invalid 'days' parameter — must be an integer"}, 400)
    if days < 1 or days > 365:
        return json_response({"error": "Invalid 'days' parameter — must be between 1 and 365"}, 400)
    return days


@bp.function_name("advisor_trend")
@bp.route(route="advisor/trend", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_trend(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body, _bad = get_body_or_400(req)
        if _bad is not None:
            return _bad
        days = _validated_days(body)
        if isinstance(days, func.HttpResponse):
            return days
        return json_response(get_trend(department=body.get("department"), days=days, tenant_id=body.get("tenant_id")))
    except Exception as e:
        log.exception("advisor/trend error: %s", e)
        return json_response({"error": str(e)}, 500)


@bp.function_name("advisor_purview_insights")
@bp.route(route="advisor/purview-insights", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_purview_insights(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body, _bad = get_body_or_400(req)
        if _bad is not None:
            return _bad
        days = _validated_days(body)
        if isinstance(days, func.HttpResponse):
            return days
        return json_response(
            get_purview_insights(department=body.get("department"), tenant_id=body.get("tenant_id"), days=days)
        )
    except Exception as e:
        log.exception("advisor/purview-insights error: %s", e)
        return json_response({"error": str(e)}, 500)


@bp.function_name("advisor_hunt_results")
@bp.route(route="advisor/hunt-results", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_hunt_results(req: func.HttpRequest) -> func.HttpResponse:
    try:
        principal = require_auth(req)
        if principal is None:
            return get_auth_error_response()
        body, _bad = get_body_or_400(req)
        if _bad is not None:
            return _bad
        return json_response(
            get_hunt_results(
                department=body.get("department"),
                tenant_id=body.get("tenant_id"),
                severity=body.get("severity"),
                days=body.get("days", 30),
            )
        )
    except Exception as e:
        log.exception("advisor/hunt-results error: %s", e)
        return json_response({"error": str(e)}, 500)
