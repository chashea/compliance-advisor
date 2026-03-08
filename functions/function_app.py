"""
Compliance Advisor — Azure Function App

Functions:
- 7x advisor/* routes:  Dashboard API endpoints
- ingest:               HTTP POST — receive posture payloads from collector
- compute_aggregates:   Timer     — daily compliance trend computation
"""

import json
import logging

import azure.functions as func
from shared.ai_agent import ask_advisor
from shared.dashboard_queries import (
    get_alerts,
    get_controls,
    get_overview,
    get_score_trend,
    get_security,
    get_service_health,
    get_status,
)
from shared.db import (
    query,
    upsert_control_profile,
    upsert_control_score,
    upsert_risky_user,
    upsert_security_alert,
    upsert_security_incident,
    upsert_service_health,
    upsert_snapshot,
    upsert_tenant,
    upsert_trend,
)
from shared.validation import validate_ingestion_request

app = func.FunctionApp()
log = logging.getLogger(__name__)


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
        return {}


# ── Dashboard API Routes ──────────────────────────────────────────


@app.function_name("advisor_status")
@app.route(route="advisor/status", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_status(req: func.HttpRequest) -> func.HttpResponse:
    try:
        return _json_response(get_status())
    except Exception as e:
        log.exception("advisor/status error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_overview")
@app.route(route="advisor/overview", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_overview(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = _get_body(req)
        return _json_response(get_overview(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/overview error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_score_trend")
@app.route(route="advisor/score-trend", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_score_trend(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = _get_body(req)
        return _json_response(
            get_score_trend(
                department=body.get("department"),
                days=int(body.get("days", 30)),
            )
        )
    except Exception as e:
        log.exception("advisor/score-trend error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_controls")
@app.route(route="advisor/controls", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_controls(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = _get_body(req)
        return _json_response(get_controls(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/controls error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_alerts")
@app.route(route="advisor/alerts", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_alerts(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = _get_body(req)
        return _json_response(get_alerts(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/alerts error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_security")
@app.route(route="advisor/security", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_security(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = _get_body(req)
        return _json_response(get_security(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/security error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_service_health")
@app.route(route="advisor/service-health", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_service_health_route(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = _get_body(req)
        return _json_response(get_service_health(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/service-health error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_briefing")
@app.route(route="advisor/briefing", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_briefing(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = _get_body(req)
        department = body.get("department")
        result = ask_advisor(
            question="Generate a concise executive briefing summarizing the current "
            "security posture, Secure Score trends, top risks, and recommended actions.",
            department=department,
        )
        return _json_response({"briefing": result["answer"]})
    except Exception as e:
        log.exception("advisor/briefing error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_ask")
@app.route(route="advisor/ask", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_ask(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = _get_body(req)
        question = body.get("question", "")
        if not question:
            return _json_response({"error": "Missing 'question' field"}, 400)
        result = ask_advisor(question=question, department=body.get("department"))
        return _json_response({"answer": result["answer"]})
    except Exception as e:
        log.exception("advisor/ask error: %s", e)
        return _json_response({"error": str(e)}, 500)


# ── Ingestion ─────────────────────────────────────────────────────


@app.function_name("ingest_posture")
@app.route(route="ingest", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def ingest_posture(req: func.HttpRequest) -> func.HttpResponse:
    """Receive JSON payload from per-tenant collector."""
    try:
        payload = validate_ingestion_request(req)
        snapshot_date = payload["timestamp"][:10]
        tenant_id = payload["tenant_id"]

        # Upsert tenant
        upsert_tenant(
            tenant_id=tenant_id,
            display_name=payload["display_name"],
            department=payload["department"],
        )

        # Upsert posture snapshot from latest secure score
        scores = payload.get("secure_scores", [])
        latest = scores[0] if scores else {}
        upsert_snapshot(
            tenant_id=tenant_id,
            snapshot_date=snapshot_date,
            secure_score=payload["secure_score_current"],
            max_score=payload["secure_score_max"],
            active_user_count=latest.get("active_user_count", 0),
            licensed_user_count=latest.get("licensed_user_count", 0),
            controls_total=latest.get("control_scores_count", 0),
            controls_implemented=latest.get("controls_implemented", 0),
            collector_version=payload.get("collector_version", ""),
        )

        # Upsert control scores
        for cs in payload.get("control_scores", []):
            upsert_control_score(
                tenant_id=tenant_id,
                control_name=cs.get("control_name", ""),
                category=cs.get("category", ""),
                score=cs.get("score", 0),
                score_pct=cs.get("score_pct", 0),
                implementation_status=cs.get("implementation_status", ""),
                last_synced=cs.get("last_synced", ""),
                description=cs.get("description", ""),
                snapshot_date=snapshot_date,
            )

        # Upsert control profiles
        for cp in payload.get("control_profiles", []):
            upsert_control_profile(
                tenant_id=tenant_id,
                control_id=cp.get("control_id", ""),
                title=cp.get("title", ""),
                max_score=cp.get("max_score", 0),
                service=cp.get("service", ""),
                category=cp.get("category", ""),
                action_type=cp.get("action_type", ""),
                tier=cp.get("tier", ""),
                implementation_cost=cp.get("implementation_cost", ""),
                user_impact=cp.get("user_impact", ""),
                snapshot_date=snapshot_date,
            )

        # Upsert security alerts
        for a in payload.get("security_alerts", []):
            upsert_security_alert(
                tenant_id=tenant_id,
                alert_id=a.get("alert_id", ""),
                title=a.get("title", ""),
                severity=a.get("severity", ""),
                status=a.get("status", ""),
                category=a.get("category", ""),
                service_source=a.get("service_source", ""),
                created=a.get("created", ""),
                resolved=a.get("resolved", ""),
                snapshot_date=snapshot_date,
            )

        # Upsert security incidents
        for inc in payload.get("security_incidents", []):
            upsert_security_incident(
                tenant_id=tenant_id,
                incident_id=inc.get("incident_id", ""),
                display_name=inc.get("display_name", ""),
                severity=inc.get("severity", ""),
                status=inc.get("status", ""),
                classification=inc.get("classification", ""),
                created=inc.get("created", ""),
                last_update=inc.get("last_update", ""),
                assigned_to=inc.get("assigned_to", ""),
                snapshot_date=snapshot_date,
            )

        # Upsert risky users
        for ru in payload.get("risky_users", []):
            upsert_risky_user(
                tenant_id=tenant_id,
                user_id=ru.get("user_id", ""),
                user_display_name=ru.get("user_display_name", ""),
                user_principal_name=ru.get("user_principal_name", ""),
                risk_level=ru.get("risk_level", ""),
                risk_state=ru.get("risk_state", ""),
                risk_detail=ru.get("risk_detail", ""),
                risk_last_updated=ru.get("risk_last_updated", ""),
                snapshot_date=snapshot_date,
            )

        # Upsert service health
        for sh in payload.get("service_health", []):
            upsert_service_health(
                tenant_id=tenant_id,
                service_name=sh.get("service_name", ""),
                status=sh.get("status", ""),
                snapshot_date=snapshot_date,
            )

        log.info(
            "Ingested: tenant=%s dept=%s score=%.1f/%.1f controls=%d alerts=%d incidents=%d",
            tenant_id,
            payload["department"],
            payload["secure_score_current"],
            payload["secure_score_max"],
            len(payload.get("control_scores", [])),
            len(payload.get("security_alerts", [])),
            len(payload.get("security_incidents", [])),
        )
        return _json_response({
            "status": "ok",
            "tenant_id": tenant_id,
            "secure_score": payload["secure_score_current"],
            "max_score": payload["secure_score_max"],
        })

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
    """Daily at 6:00 AM UTC: compute score trend rows."""
    try:
        rows = query(
            """
            SELECT DISTINCT ON (ps.tenant_id)
                t.department, ps.score_pct
            FROM posture_snapshots ps
            JOIN tenants t ON t.tenant_id = ps.tenant_id
            ORDER BY ps.tenant_id, ps.snapshot_date DESC
            """
        )
        if not rows:
            log.info("No snapshots found, skipping aggregate computation")
            return

        from datetime import date
        today = date.today().isoformat()

        # Statewide aggregate
        pcts = [r["score_pct"] for r in rows if r["score_pct"] is not None]
        if pcts:
            upsert_trend(
                snapshot_date=today,
                department=None,
                avg_pct=round(sum(pcts) / len(pcts), 2),
                min_pct=min(pcts),
                max_pct=max(pcts),
                tenant_count=len(pcts),
            )

        # Per-department aggregates
        depts: dict[str, list[float]] = {}
        for r in rows:
            dept = r.get("department")
            pct = r.get("score_pct")
            if dept and pct is not None:
                depts.setdefault(dept, []).append(pct)

        for dept, dept_pcts in depts.items():
            upsert_trend(
                snapshot_date=today,
                department=dept,
                avg_pct=round(sum(dept_pcts) / len(dept_pcts), 2),
                min_pct=min(dept_pcts),
                max_pct=max(dept_pcts),
                tenant_count=len(dept_pcts),
            )

        log.info("Computed trend aggregates: %d agencies, %d departments", len(pcts), len(depts))

    except Exception as e:
        log.exception("Aggregate computation failed: %s", e)
