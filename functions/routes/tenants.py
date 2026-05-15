"""Tenant registration + Entra admin-consent callback."""

from __future__ import annotations

import logging
import uuid

import azure.functions as func
from shared.db import upsert_tenant

from routes._decorator import get_body, json_response
from routes.collect import _trigger_collection_async

log = logging.getLogger(__name__)

bp = func.Blueprint()


@bp.function_name("register_tenant")
@bp.route(route="tenants", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def register_tenant(req: func.HttpRequest) -> func.HttpResponse:
    """Register or update a tenant."""
    try:
        body = get_body(req)

        tenant_id = body.get("tenant_id", "").strip()
        if not tenant_id:
            return json_response({"error": "Missing required field: tenant_id"}, 400)
        try:
            uuid.UUID(tenant_id)
        except ValueError:
            return json_response({"error": "Invalid tenant_id: must be a valid UUID"}, 400)

        display_name = body.get("display_name", "").strip()
        if not display_name:
            return json_response({"error": "Missing required field: display_name"}, 400)

        department = body.get("department", "").strip()
        if not department:
            return json_response({"error": "Missing required field: department"}, 400)

        risk_tier = body.get("risk_tier", "Medium")

        upsert_tenant(
            tenant_id=tenant_id,
            display_name=display_name,
            department=department,
            risk_tier=risk_tier,
        )

        _trigger_collection_async(tenant_id, display_name, department)

        log.info("Registered tenant: %s (%s, %s)", tenant_id, display_name, department)
        return json_response({"status": "ok", "tenant_id": tenant_id, "collection": "triggered"})

    except Exception as e:
        log.exception("register_tenant error: %s", e)
        return json_response({"error": "Internal server error"}, 500)


@bp.function_name("tenant_consent_callback")
@bp.route(route="tenants/callback", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def tenant_consent_callback(req: func.HttpRequest) -> func.HttpResponse:
    """Handle Azure AD admin-consent redirect — auto-register the tenant."""
    try:
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
