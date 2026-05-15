"""Ingest endpoint — receives the collector's compliance snapshot.

Auth: Entra-issued bearer token (per-tenant), validated against the
payload's ``tenant_id``. The ingest path no longer uses a shared function
key.
"""

from __future__ import annotations

import hashlib
import logging

import azure.functions as func
from shared.auth import IngestAuthError, verify_ingest_token
from shared.db import check_ingestion_duplicate, record_ingestion
from shared.persist import persist_payload
from shared.validation import validate_ingestion_request

from routes._decorator import json_response

log = logging.getLogger(__name__)

bp = func.Blueprint()

_RESPONSE_COUNT_KEYS = (
    "sensitivity_labels",
    "audit_records",
    "dlp_alerts",
    "irm_alerts",
    "info_barrier_policies",
    "protection_scopes",
    "dlp_policies",
    "irm_policies",
    "sensitive_info_types",
    "compliance_assessments",
    "threat_assessment_requests",
    "purview_incidents",
)


@bp.function_name("ingest_compliance")
@bp.route(route="ingest", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def ingest_compliance(req: func.HttpRequest) -> func.HttpResponse:
    try:
        payload = validate_ingestion_request(req)
        snapshot_date = payload["timestamp"][:10]
        tenant_id = payload["tenant_id"]

        try:
            verify_ingest_token(req, tenant_id)
        except IngestAuthError as e:
            log.warning("Ingest auth rejected for tenant=%s: %s", tenant_id, e)
            return json_response({"error": str(e)}, e.status_code)

        # Idempotency: skip re-processing exact duplicate submissions
        payload_hash = hashlib.sha256(req.get_body()).hexdigest()
        if check_ingestion_duplicate(tenant_id, snapshot_date, payload_hash):
            log.info("Duplicate ingest skipped: tenant=%s snapshot=%s", tenant_id, snapshot_date)
            return json_response({"status": "ok", "tenant_id": tenant_id, "duplicate": True})

        all_counts = persist_payload(
            tenant_id=tenant_id,
            snapshot_date=snapshot_date,
            display_name=payload["display_name"],
            department=payload["department"],
            sensitivity_labels=payload.get("sensitivity_labels", []),
            retention_events=payload.get("retention_events", []),
            retention_event_types=payload.get("retention_event_types", []),
            retention_labels=payload.get("retention_labels", []),
            audit_records=payload.get("audit_records", []),
            dlp_alerts=payload.get("dlp_alerts", []),
            irm_alerts=payload.get("irm_alerts", []),
            protection_scopes=payload.get("protection_scopes", []),
            info_barrier_policies=payload.get("info_barrier_policies", []),
            secure_scores=payload.get("secure_scores", []),
            improvement_actions=payload.get("improvement_actions", []),
            user_content_policies=payload.get("user_content_policies", []),
            dlp_policies=payload.get("dlp_policies", []),
            irm_policies=payload.get("irm_policies", []),
            sensitive_info_types=payload.get("sensitive_info_types", []),
            compliance_assessments=payload.get("compliance_assessments", []),
            threat_assessment_requests=payload.get("threat_assessment_requests", []),
            purview_incidents=payload.get("purview_incidents", []),
        )

        # Wire response keeps the same 12-key subset for backward compatibility
        counts = {k: all_counts.get(k, 0) for k in _RESPONSE_COUNT_KEYS}
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
            all_counts.get("secure_scores", 0),
            all_counts.get("improvement_actions", 0),
            counts["dlp_policies"],
            counts["irm_policies"],
            counts["sensitive_info_types"],
            counts["compliance_assessments"],
            counts["threat_assessment_requests"],
            counts["purview_incidents"],
        )
        return json_response({"status": "ok", "tenant_id": tenant_id, **counts})

    except ValueError as e:
        log.warning("Validation failed: %s", e)
        return json_response({"error": str(e)}, 400)
    except Exception as e:
        log.exception("Ingestion error: %s", e)
        return json_response({"error": "Internal server error"}, 500)
