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
        "retention_events",
        "retention_event_types",
        "audit_records",
        "dlp_alerts",
        "irm_alerts",
        "comm_compliance_policies",
        "info_barrier_policies",
        "protection_scopes",
        "secure_scores",
        "improvement_actions",
        "user_content_policies",
        "dlp_policies",
        "irm_policies",
        "sensitive_info_types",
        "compliance_assessments",
        "threat_assessment_requests",
        "collector_version",
    ],
    "properties": {
        "tenant_id": {"type": "string", "pattern": "^[0-9a-fA-F-]{36}$"},
        "agency_id": {"type": "string", "minLength": 1, "maxLength": 64},
        "department": {"type": "string", "minLength": 1},
        "display_name": {"type": "string", "minLength": 1},
        "timestamp": {"type": "string"},
        "ediscovery_cases": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["case_id"],
                "properties": {"case_id": {"type": "string", "minLength": 1}},
            },
        },
        "sensitivity_labels": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["label_id"],
                "properties": {"label_id": {"type": "string", "minLength": 1}},
            },
        },
        "retention_events": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["event_id"],
                "properties": {"event_id": {"type": "string", "minLength": 1}},
            },
        },
        "retention_event_types": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["event_type_id"],
                "properties": {"event_type_id": {"type": "string", "minLength": 1}},
            },
        },
        "audit_records": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["record_id"],
                "properties": {"record_id": {"type": "string", "minLength": 1}},
            },
        },
        "dlp_alerts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["alert_id", "severity"],
                "properties": {
                    "alert_id": {"type": "string", "minLength": 1},
                    "severity": {"type": "string", "minLength": 1},
                    "classification": {"type": "string"},
                    "determination": {"type": "string"},
                    "recommended_actions": {"type": "string"},
                    "incident_id": {"type": "string"},
                    "mitre_techniques": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "object"}},
                },
            },
        },
        "irm_alerts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["alert_id", "severity"],
                "properties": {
                    "alert_id": {"type": "string", "minLength": 1},
                    "severity": {"type": "string", "minLength": 1},
                    "classification": {"type": "string"},
                    "determination": {"type": "string"},
                    "recommended_actions": {"type": "string"},
                    "incident_id": {"type": "string"},
                    "mitre_techniques": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "object"}},
                },
            },
        },
        "comm_compliance_policies": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["policy_id"],
                "properties": {"policy_id": {"type": "string", "minLength": 1}},
            },
        },
        "info_barrier_policies": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["policy_id"],
                "properties": {"policy_id": {"type": "string", "minLength": 1}},
            },
        },
        "protection_scopes": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["scope_type"],
                "properties": {"scope_type": {"type": "string", "minLength": 1}},
            },
        },
        "secure_scores": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["current_score", "max_score"],
                "properties": {
                    "current_score": {"type": "number"},
                    "max_score": {"type": "number"},
                },
            },
        },
        "improvement_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["control_id"],
                "properties": {"control_id": {"type": "string", "minLength": 1}},
            },
        },
        "user_content_policies": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["user_id", "user_upn"],
                "properties": {
                    "user_id": {"type": "string", "minLength": 1},
                    "user_upn": {"type": "string", "minLength": 1},
                },
            },
        },
        "dlp_policies": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["policy_id"],
                "properties": {"policy_id": {"type": "string", "minLength": 1}},
            },
        },
        "irm_policies": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["policy_id"],
                "properties": {"policy_id": {"type": "string", "minLength": 1}},
            },
        },
        "sensitive_info_types": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["type_id"],
                "properties": {"type_id": {"type": "string", "minLength": 1}},
            },
        },
        "compliance_assessments": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["assessment_id"],
                "properties": {"assessment_id": {"type": "string", "minLength": 1}},
            },
        },
        "threat_assessment_requests": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["request_id"],
                "properties": {"request_id": {"type": "string", "minLength": 1}},
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
