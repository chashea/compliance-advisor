"""Client-credentials authentication for Microsoft Graph API.

Two credential modes:

- **Client secret** (default; used by the CLI collector): MSAL
  ``ConfidentialClientApplication`` with the app registration's secret.
- **Federated assertion** (production Function App; opt-in via
  ``COLLECTOR_USE_FEDERATED=true``): the runtime obtains a token for
  ``api://AzureADTokenExchange`` from the Function App's managed
  identity, then hands it to MSAL as the ``client_assertion``. The
  multi-tenant app registration must have a federated identity
  credential pointing at the MI (one-time post-deploy step — see
  README "Collector authentication").

The federated path eliminates the long-lived ``CLIENT_SECRET`` for the
in-Azure caller while leaving the CLI flow untouched.
"""

from __future__ import annotations

import logging

import msal

from collector.config import CollectorSettings

log = logging.getLogger(__name__)

_app_cache: dict[str, msal.ConfidentialClientApplication] = {}

_FEDERATED_AUDIENCE = "api://AzureADTokenExchange"


def _get_federated_assertion() -> str:
    """Acquire a federation token from the Function App's managed identity."""
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    return credential.get_token(f"{_FEDERATED_AUDIENCE}/.default").token


def _build_client_credential(settings: CollectorSettings):
    """Build the credential value passed to MSAL.

    For federated mode we return a callable so MSAL re-fetches a fresh
    assertion on every token acquisition (assertions are short-lived).
    """
    if getattr(settings, "USE_FEDERATED", False):
        log.info("MSAL using federated assertion (managed identity → multi-tenant app)")
        return {"client_assertion": _get_federated_assertion()}
    return settings.CLIENT_SECRET


def get_graph_token(settings: CollectorSettings) -> str:
    """Acquire an app-only token for Microsoft Graph.

    Returns:
        The access token string.

    Raises:
        RuntimeError: If MSAL authentication fails.
    """
    cache_key = f"{settings.TENANT_ID}:{settings.CLIENT_ID}"

    # In federated mode we cannot cache the MSAL app across calls because
    # the assertion is short-lived; rebuild on each call so a fresh
    # assertion is obtained.
    use_federated = getattr(settings, "USE_FEDERATED", False)

    if use_federated or cache_key not in _app_cache:
        authority = f"{settings.login_authority}/{settings.TENANT_ID}"
        log.info(
            "Creating MSAL app for tenant=%s authority=%s federated=%s",
            settings.TENANT_ID,
            authority,
            use_federated,
        )

        _app_cache[cache_key] = msal.ConfidentialClientApplication(
            client_id=settings.CLIENT_ID,
            client_credential=_build_client_credential(settings),
            authority=authority,
        )

    app = _app_cache[cache_key]

    result = app.acquire_token_for_client(scopes=settings.graph_scope)

    if "access_token" not in result:
        error_desc = result.get("error_description", result.get("error", "Unknown error"))
        raise RuntimeError(f"MSAL client credentials failed for tenant {settings.TENANT_ID}: {error_desc}")

    log.debug(
        "Token acquired for tenant=%s (expires_in=%s federated=%s)",
        settings.TENANT_ID,
        result.get("expires_in"),
        use_federated,
    )
    return result["access_token"]
