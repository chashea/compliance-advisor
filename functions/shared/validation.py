"""
Request validation for the ingestion endpoint.

Validates:
1. Tenant ID against allow-list
2. JSON body against the compliance-only payload schema
"""

import logging

import azure.functions as func
import jsonschema

from shared.config import get_settings

log = logging.getLogger(__name__)

PAYLOAD_SCHEMA: dict = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "CompliancePosturePayload",
    "type": "object",
    "required": [
        "tenant_id",
        "agency_id",
        "department",
        "display_name",
        "timestamp",
        "compliance_score_current",
        "compliance_score_max",
        "assessments",
        "improvement_actions",
        "collector_version",
    ],
    "properties": {
        "tenant_id": {"type": "string", "pattern": "^[0-9a-fA-F-]{36}$"},
        "agency_id": {"type": "string", "minLength": 1, "maxLength": 64},
        "department": {"type": "string", "minLength": 1},
        "display_name": {"type": "string", "minLength": 1},
        "timestamp": {"type": "string"},
        "compliance_score_current": {"type": "number", "minimum": 0},
        "compliance_score_max": {"type": "number", "minimum": 0},
        "assessments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["assessment_id", "regulation"],
                "properties": {
                    "assessment_id": {"type": "string"},
                    "assessment_name": {"type": "string"},
                    "regulation": {"type": "string"},
                    "compliance_score": {"type": "number"},
                    "passed_controls": {"type": "integer", "minimum": 0},
                    "failed_controls": {"type": "integer", "minimum": 0},
                    "total_controls": {"type": "integer", "minimum": 0},
                },
            },
        },
        "improvement_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["action_id"],
                "properties": {
                    "action_id": {"type": "string"},
                    "control_name": {"type": "string"},
                    "control_family": {"type": "string"},
                    "regulation": {"type": "string"},
                    "implementation_status": {"type": "string"},
                    "test_status": {"type": "string"},
                    "action_category": {"type": "string"},
                    "is_mandatory": {"type": "boolean"},
                    "point_value": {"type": "integer", "minimum": 0},
                    "owner": {"type": "string"},
                    "service": {"type": "string"},
                    "description": {"type": "string"},
                    "remediation_steps": {"type": "string"},
                },
            },
        },
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
