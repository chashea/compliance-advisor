"""
Client credentials authentication for Microsoft Graph API.

Uses MSAL ConfidentialClientApplication with client_credentials flow
to acquire an app-only token scoped to graph.microsoft.com.
"""

import logging

import msal

from collector.config import CollectorSettings

log = logging.getLogger(__name__)

_app_cache: dict[str, msal.ConfidentialClientApplication] = {}


def get_graph_token(settings: CollectorSettings) -> str:
    """Acquire an app-only token for Microsoft Graph via client credentials.

    Returns:
        The access token string.

    Raises:
        RuntimeError: If MSAL authentication fails.
    """
    cache_key = f"{settings.TENANT_ID}:{settings.CLIENT_ID}"

    if cache_key not in _app_cache:
        authority = f"{settings.login_authority}/{settings.TENANT_ID}"
        log.info("Creating MSAL app for tenant=%s authority=%s", settings.TENANT_ID, authority)

        _app_cache[cache_key] = msal.ConfidentialClientApplication(
            client_id=settings.CLIENT_ID,
            client_credential=settings.CLIENT_SECRET,
            authority=authority,
        )

    app = _app_cache[cache_key]

    result = app.acquire_token_for_client(scopes=settings.graph_scope)

    if "access_token" not in result:
        error_desc = result.get("error_description", result.get("error", "Unknown error"))
        raise RuntimeError(f"MSAL client credentials failed for tenant {settings.TENANT_ID}: {error_desc}")

    log.debug(
        "Token acquired via client credentials for tenant=%s (expires_in=%s)",
        settings.TENANT_ID,
        result.get("expires_in"),
    )
    return result["access_token"]
