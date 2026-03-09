"""
Compliance Advisor — Azure Function App

Functions:
- 8x advisor/* routes:  Dashboard API endpoints
- ingest:               HTTP POST — receive compliance payloads from collector
- compute_aggregates:   Timer     — daily compliance trend computation
"""

import json
import logging

import azure.functions as func

app = func.FunctionApp()
log = logging.getLogger(__name__)
_DEPENDENCY_IMPORT_ERROR: Exception | None = None

try:
    from shared.ai_agent import AdvisorAIError, ask_advisor
    from shared.dashboard_queries import (
        get_audit,
        get_comm_compliance,
        get_dlp,
        get_ediscovery,
        get_governance,
        get_improvement_actions,
        get_info_barriers,
        get_irm,
        get_labels,
        get_overview,
        get_status,
        get_subject_rights,
        get_trend,
    )
    from shared.db import (
        query,
        upsert_audit_record,
        upsert_comm_compliance_policy,
        upsert_dlp_alert,
        upsert_ediscovery_case,
        upsert_improvement_action,
        upsert_info_barrier_policy,
        upsert_irm_alert,
        upsert_protection_scope,
        upsert_retention_event,
        upsert_retention_label,
        upsert_secure_score,
        upsert_sensitivity_label,
        upsert_subject_rights_request,
        upsert_tenant,
        upsert_trend,
        upsert_user_content_policies,
    )
    from shared.validation import validate_ingestion_request
except Exception as e:
    _DEPENDENCY_IMPORT_ERROR = e
    log.exception("Function dependency import failed at startup: %s", e)

    class AdvisorAIError(RuntimeError):
        code = "ai_service_error"
        status_code = 500


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


# ── Dashboard API Routes ──────────────────────────────────────────


@app.function_name("advisor_status")
@app.route(route="advisor/status", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_status(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        return _json_response(get_status())
    except Exception as e:
        log.exception("advisor/status error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_overview")
@app.route(route="advisor/overview", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_overview(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)
        return _json_response(get_overview(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/overview error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_ediscovery")
@app.route(route="advisor/ediscovery", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_ediscovery(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)
        return _json_response(get_ediscovery(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/ediscovery error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_labels")
@app.route(route="advisor/labels", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_labels(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)
        return _json_response(get_labels(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/labels error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_audit")
@app.route(route="advisor/audit", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_audit(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)
        return _json_response(get_audit(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/audit error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_dlp")
@app.route(route="advisor/dlp", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_dlp(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)
        return _json_response(get_dlp(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/dlp error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_irm")
@app.route(route="advisor/irm", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_irm(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)
        return _json_response(get_irm(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/irm error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_subject_rights")
@app.route(route="advisor/subject-rights", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_subject_rights(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)
        return _json_response(get_subject_rights(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/subject-rights error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_comm_compliance")
@app.route(route="advisor/comm-compliance", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_comm_compliance(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)
        return _json_response(get_comm_compliance(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/comm-compliance error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_info_barriers")
@app.route(route="advisor/info-barriers", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_info_barriers(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)
        return _json_response(get_info_barriers(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/info-barriers error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_governance")
@app.route(route="advisor/governance", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_governance(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)
        return _json_response(get_governance(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/governance error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_trend")
@app.route(route="advisor/trend", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_trend(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
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
            )
        )
    except Exception as e:
        log.exception("advisor/trend error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_actions")
@app.route(route="advisor/actions", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_actions(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)
        return _json_response(get_improvement_actions(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/actions error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_briefing")
@app.route(route="advisor/briefing", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_briefing(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)
        department = body.get("department")
        result = ask_advisor(
            question="Generate a concise executive briefing summarizing the current "
            "compliance posture across all workloads: eDiscovery cases, information "
            "protection labels, records management, audit activity, DLP alerts, and "
            "data governance scopes. Highlight key risks and recommended actions.",
            department=department,
        )
        return _json_response({"briefing": result["answer"]})
    except AdvisorAIError as e:
        log.warning("advisor/briefing AI error [%s]: %s", e.code, e)
        return _json_response({"error": str(e), "code": e.code}, e.status_code)
    except Exception as e:
        log.exception("advisor/briefing error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_ask")
@app.route(route="advisor/ask", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_ask(req: func.HttpRequest) -> func.HttpResponse:
    try:
        _ensure_dependencies_loaded()
        body = _get_body(req)
        question = body.get("question", "")
        if not question:
            return _json_response({"error": "Missing 'question' field"}, 400)
        result = ask_advisor(question=question, department=body.get("department"))
        return _json_response({"answer": result["answer"]})
    except AdvisorAIError as e:
        log.warning("advisor/ask AI error [%s]: %s", e.code, e)
        return _json_response({"error": str(e), "code": e.code}, e.status_code)
    except Exception as e:
        log.exception("advisor/ask error: %s", e)
        return _json_response({"error": str(e)}, 500)


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

        # Upsert tenant
        upsert_tenant(
            tenant_id=tenant_id,
            display_name=payload["display_name"],
            department=payload["department"],
        )

        # Upsert eDiscovery cases
        for ec in payload.get("ediscovery_cases", []):
            upsert_ediscovery_case(
                tenant_id=tenant_id,
                case_id=ec.get("case_id", ""),
                display_name=ec.get("display_name", ""),
                status=ec.get("status", ""),
                created=ec.get("created", ""),
                closed=ec.get("closed", ""),
                external_id=ec.get("external_id", ""),
                custodian_count=ec.get("custodian_count", 0),
                snapshot_date=snapshot_date,
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
            )

        # Upsert retention labels
        for rl in payload.get("retention_labels", []):
            upsert_retention_label(
                tenant_id=tenant_id,
                label_id=rl.get("label_id", ""),
                display_name=rl.get("display_name", ""),
                retention_duration=rl.get("retention_duration", ""),
                retention_trigger=rl.get("retention_trigger", ""),
                action_after_retention=rl.get("action_after_retention", ""),
                is_in_use=rl.get("is_in_use", False),
                status=rl.get("status", ""),
                snapshot_date=snapshot_date,
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
            )

        # Upsert subject rights requests
        for sr in payload.get("subject_rights_requests", []):
            upsert_subject_rights_request(
                tenant_id=tenant_id,
                request_id=sr.get("request_id", ""),
                display_name=sr.get("display_name", ""),
                request_type=sr.get("request_type", ""),
                status=sr.get("status", ""),
                created=sr.get("created", ""),
                closed=sr.get("closed", ""),
                data_subject_type=sr.get("data_subject_type", ""),
                snapshot_date=snapshot_date,
            )

        # Upsert communication compliance policies
        for cc in payload.get("comm_compliance_policies", []):
            upsert_comm_compliance_policy(
                tenant_id=tenant_id,
                policy_id=cc.get("policy_id", ""),
                display_name=cc.get("display_name", ""),
                status=cc.get("status", ""),
                policy_type=cc.get("policy_type", ""),
                review_pending_count=cc.get("review_pending_count", 0),
                snapshot_date=snapshot_date,
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

        log.info(
            "Ingested: tenant=%s dept=%s ediscovery=%d labels=%d retention=%d audit=%d dlp=%d "
            "irm=%d srr=%d comm_compliance=%d info_barriers=%d scopes=%d scores=%d actions=%d",
            tenant_id,
            payload["department"],
            len(payload.get("ediscovery_cases", [])),
            len(payload.get("sensitivity_labels", [])),
            len(payload.get("retention_labels", [])),
            len(payload.get("audit_records", [])),
            len(payload.get("dlp_alerts", [])),
            len(payload.get("irm_alerts", [])),
            len(payload.get("subject_rights_requests", [])),
            len(payload.get("comm_compliance_policies", [])),
            len(payload.get("info_barrier_policies", [])),
            len(payload.get("protection_scopes", [])),
            len(payload.get("secure_scores", [])),
            len(payload.get("improvement_actions", [])),
        )
        return _json_response(
            {
                "status": "ok",
                "tenant_id": tenant_id,
                "ediscovery_cases": len(payload.get("ediscovery_cases", [])),
                "sensitivity_labels": len(payload.get("sensitivity_labels", [])),
                "retention_labels": len(payload.get("retention_labels", [])),
                "audit_records": len(payload.get("audit_records", [])),
                "dlp_alerts": len(payload.get("dlp_alerts", [])),
                "irm_alerts": len(payload.get("irm_alerts", [])),
                "subject_rights_requests": len(payload.get("subject_rights_requests", [])),
                "comm_compliance_policies": len(payload.get("comm_compliance_policies", [])),
                "info_barrier_policies": len(payload.get("info_barrier_policies", [])),
                "protection_scopes": len(payload.get("protection_scopes", [])),
            }
        )

    except ValueError as e:
        log.warning("Validation failed: %s", e)
        return _json_response({"error": str(e)}, 400)
    except Exception as e:
        log.exception("Ingestion error: %s", e)
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
                (SELECT COUNT(*) FROM ediscovery_cases ec
                 WHERE ec.tenant_id = t.tenant_id
                   AND ec.snapshot_date = (
                     SELECT MAX(snapshot_date) FROM ediscovery_cases
                     WHERE tenant_id = t.tenant_id)
                )::int AS ediscovery,
                (SELECT COUNT(*) FROM sensitivity_labels sl
                 WHERE sl.tenant_id = t.tenant_id
                   AND sl.snapshot_date = (
                     SELECT MAX(snapshot_date) FROM sensitivity_labels
                     WHERE tenant_id = t.tenant_id)
                )::int AS sensitivity,
                (SELECT COUNT(*) FROM retention_labels rl
                 WHERE rl.tenant_id = t.tenant_id
                   AND rl.snapshot_date = (
                     SELECT MAX(snapshot_date) FROM retention_labels
                     WHERE tenant_id = t.tenant_id)
                )::int AS retention,
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
            ediscovery_cases=sum(r["ediscovery"] for r in tenant_counts),
            sensitivity_labels=sum(r["sensitivity"] for r in tenant_counts),
            retention_labels=sum(r["retention"] for r in tenant_counts),
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
                ediscovery_cases=sum(r["ediscovery"] for r in rows),
                sensitivity_labels=sum(r["sensitivity"] for r in rows),
                retention_labels=sum(r["retention"] for r in rows),
                dlp_alerts=sum(r["dlp"] for r in rows),
                audit_records=sum(r["audit"] for r in rows),
                tenant_count=len(rows),
            )

        log.info("Computed trend aggregates: %d tenants, %d departments", len(tenant_counts), len(depts))

    except Exception as e:
        log.exception("Aggregate computation failed: %s", e)
