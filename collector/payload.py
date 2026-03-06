"""
Compliance-only payload schema for the collector.

Simplified from the full Purview posture payload — only includes
Compliance Manager fields (scores, assessments, improvement actions).
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class CompliancePayload:
    tenant_id: str
    agency_id: str
    department: str
    display_name: str
    timestamp: str
    compliance_score_current: float
    compliance_score_max: float
    assessments: list[dict[str, Any]]
    improvement_actions: list[dict[str, Any]]
    collector_version: str = "1.0.0"

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)
