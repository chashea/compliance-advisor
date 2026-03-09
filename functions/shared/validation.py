"""
Request validation for the ingestion endpoint.

Validates:
1. Tenant ID against allow-list
2. JSON body against the CompliancePayload schema
"""

import logging

import azure.functions as func
import jsonschema

from shared.config import get_settings

log = logging.getLogger(__name__)

PAYLOAD_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CompliancePayload",
    "type": "object",
    "required": [
        "tenant_id",
        "agency_id",
        "department",
        "display_name",
        "timestamp",
        "ediscovery_cases",
        "sensitivity_labels",
        "retention_labels",
        "retention_events",
        "audit_records",
        "dlp_alerts",
        "irm_alerts",
        "protection_scopes",
        "secure_scores",
        "improvement_actions",
        "collector_version",
    ],
    "properties": {
        "tenant_id": {"type": "string", "pattern": "^[0-9a-fA-F-]{36}$"},
        "agency_id": {"type": "string", "minLength": 1, "maxLength": 64},
        "department": {"type": "string", "minLength": 1},
        "display_name": {"type": "string", "minLength": 1},
        "timestamp": {"type": "string"},
        "ediscovery_cases": {"type": "array"},
        "sensitivity_labels": {"type": "array"},
        "retention_labels": {"type": "array"},
        "retention_events": {"type": "array"},
        "audit_records": {"type": "array"},
        "dlp_alerts": {"type": "array"},
        "irm_alerts": {"type": "array"},
        "protection_scopes": {"type": "array"},
        "secure_scores": {"type": "array"},
        "improvement_actions": {"type": "array"},
        "collector_version": {"type": "string"},
    },
    "additionalProperties": False,
}


def validate_ingestion_request(req: func.HttpRequest) -> dict:
    """Validate the inbound ingestion request.

    Returns:
        Parsed and validated payload dictionary.

    Raises:
        ValueError: If any validation check fails.
    """
    settings = get_settings()

    # Parse JSON body
    try:
        payload = req.get_json()
    except ValueError:
        raise ValueError("Invalid JSON body")

    # JSON schema validation
    try:
        jsonschema.validate(instance=payload, schema=PAYLOAD_SCHEMA)
    except jsonschema.ValidationError as e:
        raise ValueError(f"Schema validation failed: {e.message}")

    # Tenant allow-list (skip if not configured — dev mode)
    if settings.allowed_tenants:
        tenant_id = payload["tenant_id"]
        if tenant_id not in settings.allowed_tenants:
            log.warning("Rejected tenant not in allow-list: %s", tenant_id)
            raise ValueError(f"Tenant {tenant_id} not in allow-list")

    return payload
