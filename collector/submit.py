"""
Submit the compliance payload to the Azure Function App ingestion endpoint.

Supports function key authentication (x-functions-key header).
"""

import json
import logging

import requests

from collector.config import CollectorSettings

log = logging.getLogger(__name__)


def submit_payload(payload: dict, settings: CollectorSettings) -> dict:
    """POST the payload to the Function App ingestion endpoint.

    Args:
        payload: The compliance posture dictionary.
        settings: Collector configuration with endpoint and auth details.

    Returns:
        The response JSON from the Function App.

    Raises:
        requests.HTTPError: If the submission fails.
    """
    headers = {"Content-Type": "application/json"}

    if settings.FUNCTION_APP_KEY:
        headers["x-functions-key"] = settings.FUNCTION_APP_KEY

    log.info(
        "Submitting payload for tenant=%s agency=%s to %s",
        payload.get("tenant_id"),
        payload.get("agency_id"),
        settings.FUNCTION_APP_URL,
    )

    resp = requests.post(
        settings.FUNCTION_APP_URL,
        data=json.dumps(payload),
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()

    result = resp.json()
    log.info("Submission successful: %s", result)
    return result
