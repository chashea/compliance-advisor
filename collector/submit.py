"""
Submit the compliance payload to the Azure Function App ingestion endpoint.

Authentication, in order of preference:
1. Entra-ID-issued bearer token, when ``INGEST_AUDIENCE`` is configured.
2. Function key (``x-functions-key``) — legacy, intended for local dev only.
"""

import json
import logging

import msal
import requests

from collector.config import CollectorSettings

log = logging.getLogger(__name__)

_ingest_token_cache: dict[str, tuple[str, float]] = {}


def _get_ingest_token(settings: CollectorSettings) -> str:
    """Acquire an app-only token for the ingest API audience."""
    import time

    cache_key = f"{settings.TENANT_ID}:{settings.CLIENT_ID}:{settings.INGEST_AUDIENCE}"
    cached = _ingest_token_cache.get(cache_key)
    if cached and cached[1] - time.time() > 300:
        return cached[0]

    authority = f"{settings.login_authority}/{settings.TENANT_ID}"
    app = msal.ConfidentialClientApplication(
        client_id=settings.CLIENT_ID,
        client_credential=settings.CLIENT_SECRET,
        authority=authority,
    )
    result = app.acquire_token_for_client(scopes=settings.ingest_scope)
    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "Unknown error"))
        raise RuntimeError(f"Failed to acquire ingest token for tenant {settings.TENANT_ID}: {error}")

    expires_on = time.time() + int(result.get("expires_in", 3600))
    _ingest_token_cache[cache_key] = (result["access_token"], expires_on)
    return result["access_token"]


def submit_payload(payload: dict, settings: CollectorSettings) -> dict:
    """POST the payload to the Function App ingestion endpoint.

    Args:
        payload: The compliance posture dictionary.
        settings: Collector configuration with endpoint and auth details.

    Returns:
        The response JSON from the Function App.

    Raises:
        requests.HTTPError: If the submission fails.
        RuntimeError: If token acquisition fails.
    """
    headers = {"Content-Type": "application/json"}

    if settings.INGEST_AUDIENCE:
        token = _get_ingest_token(settings)
        headers["Authorization"] = f"Bearer {token}"
    elif settings.FUNCTION_APP_KEY:
        log.warning("Using legacy function-key auth for ingest; set INGEST_AUDIENCE for per-tenant Entra auth.")
        headers["x-functions-key"] = settings.FUNCTION_APP_KEY
    else:
        raise RuntimeError("Either INGEST_AUDIENCE (recommended) or FUNCTION_APP_KEY must be configured.")

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
