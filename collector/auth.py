"""
ROPC (Resource Owner Password Credential) authentication for
Microsoft Graph API.

Uses MSAL PublicClientApplication with username/password flow to
acquire a delegated token scoped to graph.microsoft.com.

Each GCC tenant has a dedicated service account.
"""

import logging

import msal

from collector.config import CollectorSettings

log = logging.getLogger(__name__)

_app_cache: dict[str, msal.PublicClientApplication] = {}


def get_graph_token(settings: CollectorSettings) -> str:
    """Acquire a delegated token for Microsoft Graph.

    Uses ROPC flow with the configured service account credentials.

    Returns:
        The access token string.

    Raises:
        RuntimeError: If MSAL authentication fails.
    """
    cache_key = f"{settings.TENANT_ID}:{settings.CLIENT_ID}"

    if cache_key not in _app_cache:
        authority = f"{settings.login_authority}/{settings.TENANT_ID}"
        log.info("Creating MSAL app for tenant=%s authority=%s", settings.TENANT_ID, authority)

        _app_cache[cache_key] = msal.PublicClientApplication(
            client_id=settings.CLIENT_ID,
            authority=authority,
        )

    app = _app_cache[cache_key]

    # Try to get token from cache first
    accounts = app.get_accounts(username=settings.SERVICE_ACCOUNT_USERNAME)
    if accounts:
        result = app.acquire_token_silent(
            scopes=settings.graph_scope,
            account=accounts[0],
        )
        if result and "access_token" in result:
            log.debug("Token acquired from cache for tenant=%s", settings.TENANT_ID)
            return result["access_token"]

    # ROPC flow
    result = app.acquire_token_by_username_password(
        username=settings.SERVICE_ACCOUNT_USERNAME,
        password=settings.SERVICE_ACCOUNT_PASSWORD,
        scopes=settings.graph_scope,
    )

    if "access_token" not in result:
        error_desc = result.get("error_description", result.get("error", "Unknown error"))
        raise RuntimeError(
            f"MSAL ROPC authentication failed for tenant {settings.TENANT_ID}: {error_desc}"
        )

    log.debug(
        "Token acquired via ROPC for tenant=%s (expires_in=%s)",
        settings.TENANT_ID,
        result.get("expires_in"),
    )
    return result["access_token"]
