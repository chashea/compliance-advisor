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
from shared.db import (
    query,
    upsert_action,
    upsert_assessment,
    upsert_snapshot,
    upsert_tenant,
    upsert_trend,
)
from shared.dashboard_queries import (
    get_actions,
    get_assessments,
    get_compliance,
    get_regulations,
    get_status,
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


@app.function_name("advisor_compliance")
@app.route(route="advisor/compliance", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_compliance(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = _get_body(req)
        return _json_response(
            get_compliance(
                department=body.get("department"),
                days=int(body.get("days", 30)),
            )
        )
    except Exception as e:
        log.exception("advisor/compliance error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_assessments")
@app.route(route="advisor/assessments", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_assessments(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = _get_body(req)
        return _json_response(get_assessments(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/assessments error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_regulations")
@app.route(route="advisor/regulations", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_regulations(req: func.HttpRequest) -> func.HttpResponse:
    try:
        return _json_response(get_regulations())
    except Exception as e:
        log.exception("advisor/regulations error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_actions")
@app.route(route="advisor/actions", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_actions(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = _get_body(req)
        return _json_response(get_actions(department=body.get("department")))
    except Exception as e:
        log.exception("advisor/actions error: %s", e)
        return _json_response({"error": str(e)}, 500)


@app.function_name("advisor_briefing")
@app.route(route="advisor/briefing", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def advisor_briefing(req: func.HttpRequest) -> func.HttpResponse:
    try:
        body = _get_body(req)
        department = body.get("department")
        result = ask_advisor(
            question="Generate a concise executive briefing summarizing the current "
            "compliance posture, key trends, top risks, and recommended actions.",
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

        # Upsert tenant
        upsert_tenant(
            tenant_id=payload["tenant_id"],
            display_name=payload["display_name"],
            department=payload["department"],
        )

        # Upsert posture snapshot
        upsert_snapshot(
            tenant_id=payload["tenant_id"],
            snapshot_date=snapshot_date,
            compliance_score=payload["compliance_score_current"],
            max_score=payload["compliance_score_max"],
            collector_version=payload.get("collector_version", ""),
        )

        # Upsert assessments
        for a in payload.get("assessments", []):
            upsert_assessment(
                tenant_id=payload["tenant_id"],
                assessment_id=a["assessment_id"],
                assessment_name=a.get("assessment_name", ""),
                regulation=a["regulation"],
                compliance_score=a.get("compliance_score", 0),
                passed_controls=a.get("passed_controls", 0),
                failed_controls=a.get("failed_controls", 0),
                total_controls=a.get("total_controls", 0),
                snapshot_date=snapshot_date,
            )

        # Upsert improvement actions
        for ia in payload.get("improvement_actions", []):
            upsert_action(
                tenant_id=payload["tenant_id"],
                action_id=ia["action_id"],
                control_name=ia.get("control_name", ""),
                control_family=ia.get("control_family", ""),
                regulation=ia.get("regulation", ""),
                implementation_status=ia.get("implementation_status", ""),
                test_status=ia.get("test_status", ""),
                action_category=ia.get("action_category", ""),
                is_mandatory=ia.get("is_mandatory", True),
                point_value=ia.get("point_value", 0),
                owner=ia.get("owner", ""),
                service=ia.get("service", ""),
                description=ia.get("description", ""),
                remediation_steps=ia.get("remediation_steps", ""),
                snapshot_date=snapshot_date,
            )

        log.info(
            "Ingested: tenant=%s dept=%s score=%.1f%%",
            payload["tenant_id"],
            payload["department"],
            payload.get("compliance_score_current", 0),
        )
        return _json_response({
            "status": "ok",
            "tenant_id": payload["tenant_id"],
            "compliance_score": payload.get("compliance_score_current", 0),
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
    """Daily at 6:00 AM UTC: compute compliance trend rows."""
    try:
        # Get latest snapshot per tenant
        rows = query(
            """
            SELECT DISTINCT ON (ps.tenant_id)
                t.department, ps.compliance_pct
            FROM posture_snapshots ps
            JOIN tenants t ON t.tenant_id = ps.tenant_id
            ORDER BY ps.tenant_id, ps.snapshot_date DESC
            """
        )
        if not rows:
            log.info("No snapshots found, skipping aggregate computation")
            return

        today = rows[0].get("snapshot_date", None)
        if today is None:
            from datetime import date
            today = date.today().isoformat()

        # Statewide aggregate
        pcts = [r["compliance_pct"] for r in rows if r["compliance_pct"] is not None]
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
            pct = r.get("compliance_pct")
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
