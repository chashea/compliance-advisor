"""
Purview posture payload schema for the collector.

Includes data from Microsoft Graph security/compliance APIs:
- Secure Score (daily snapshots + per-control scores)
- Security alerts and incidents
- Risky users (Identity Protection)
- Service health
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


@dataclass
class PurviewPayload:
    tenant_id: str
    agency_id: str
    department: str
    display_name: str
    timestamp: str
    secure_score_current: float
    secure_score_max: float
    secure_scores: list[dict[str, Any]]
    control_scores: list[dict[str, Any]]
    control_profiles: list[dict[str, Any]]
    security_alerts: list[dict[str, Any]]
    security_incidents: list[dict[str, Any]]
    risky_users: list[dict[str, Any]]
    service_health: list[dict[str, Any]]
    collector_version: str = "2.0.0"

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return asdict(self)
