"""
Compliance workload payload schema for the collector.

Includes data from Microsoft Graph compliance APIs:
- Sensitivity labels (Information Protection)
- Retention events (Records Management)
- Audit log records
- DLP alerts (Data Security)
- Protection scopes (Data Security & Governance)
- Secure Score and improvement actions (Posture Management)
- User content policies (userDataSecurityAndGovernance)
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from typing import Any


def _collector_version() -> str:
    try:
        return _pkg_version("compliance-advisor")
    except PackageNotFoundError:
        return "unknown"


@dataclass
class CompliancePayload:
    tenant_id: str
    agency_id: str
    department: str
    display_name: str
    timestamp: str
    sensitivity_labels: list[dict[str, Any]]
    retention_events: list[dict[str, Any]]
    retention_event_types: list[dict[str, Any]]
    retention_labels: list[dict[str, Any]]
    audit_records: list[dict[str, Any]]
    dlp_alerts: list[dict[str, Any]]
    irm_alerts: list[dict[str, Any]]
    info_barrier_policies: list[dict[str, Any]]
    protection_scopes: list[dict[str, Any]]
    secure_scores: list[dict[str, Any]]
    improvement_actions: list[dict[str, Any]]
    user_content_policies: list[dict[str, Any]]
    dlp_policies: list[dict[str, Any]]
    irm_policies: list[dict[str, Any]]
    sensitive_info_types: list[dict[str, Any]]
    compliance_assessments: list[dict[str, Any]]
    threat_assessment_requests: list[dict[str, Any]]
    purview_incidents: list[dict[str, Any]]
    collector_version: str = field(default_factory=_collector_version)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)
