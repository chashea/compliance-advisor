"""
Minimal Application Insights telemetry for the collector CLI.

Sends custom events to App Insights via direct HTTP — no SDK dependency required.
Only emits when APPINSIGHTS_CONNECTION_STRING is configured.
"""

import logging
from datetime import datetime, timezone

import requests

log = logging.getLogger(__name__)


def _parse_connection_string(conn_str: str) -> tuple[str, str]:
    parts = {k: v for k, v in (p.split("=", 1) for p in conn_str.split(";") if "=" in p)}
    ikey = parts.get("InstrumentationKey", "")
    endpoint = parts.get("IngestionEndpoint", "https://dc.services.visualstudio.com").rstrip("/")
    return ikey, endpoint


def track_event(conn_str: str, name: str, properties: dict) -> None:
    if not conn_str:
        return
    try:
        ikey, endpoint = _parse_connection_string(conn_str)
        payload = [
            {
                "name": f"Microsoft.ApplicationInsights.{ikey}.Event",
                "time": datetime.now(timezone.utc).isoformat(),
                "iKey": ikey,
                "data": {
                    "baseType": "EventData",
                    "baseData": {
                        "ver": 2,
                        "name": name,
                        "properties": {k: str(v) for k, v in properties.items()},
                    },
                },
            }
        ]
        requests.post(f"{endpoint}/v2/track", json=payload, timeout=5)
    except Exception as e:
        log.debug("App Insights telemetry failed (non-fatal): %s", e)
