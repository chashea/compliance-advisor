"""
Compliance workload payload schema for the collector.

Includes data from Microsoft Graph compliance APIs:
- eDiscovery cases
- Sensitivity labels (Information Protection)
- Retention labels and events (Records Management)
- Audit log records
- DLP alerts (Data Security)
- Protection scopes (Data Security & Governance)
- Secure Score and improvement actions (Posture Management)
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class CompliancePayload:
    tenant_id: str
    agency_id: str
    department: str
    display_name: str
    timestamp: str
    ediscovery_cases: list[dict[str, Any]]
    sensitivity_labels: list[dict[str, Any]]
    retention_labels: list[dict[str, Any]]
    retention_events: list[dict[str, Any]]
    audit_records: list[dict[str, Any]]
    dlp_alerts: list[dict[str, Any]]
    irm_alerts: list[dict[str, Any]]
    subject_rights_requests: list[dict[str, Any]]
    comm_compliance_policies: list[dict[str, Any]]
    info_barrier_policies: list[dict[str, Any]]
    protection_scopes: list[dict[str, Any]]
    secure_scores: list[dict[str, Any]]
    improvement_actions: list[dict[str, Any]]
    collector_version: str = "3.0.0"

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)
