"""
Per-tenant authentication helpers.
Reads credentials directly from environment variables (no Key Vault / Azure Identity).

Set GRAPH_NATIONAL_CLOUD=usgovernment for GCC High/DoD tenants only.
"""

import os
import requests

_GRAPH_CLOUD = os.environ.get("GRAPH_NATIONAL_CLOUD", "").strip().lower()
_IS_USGOV = _GRAPH_CLOUD in ("usgovernment", "usgov", "gcc high", "dod")

LOGIN_URL = "https://login.microsoftonline.us" if _IS_USGOV else "https://login.microsoftonline.com"
GRAPH_SCOPE = "https://graph.microsoft.us/.default" if _IS_USGOV else "https://graph.microsoft.com/.default"


def get_graph_token(tenant: dict) -> str:
    """
    Fetch a Graph API bearer token for the configured tenant.
    Reads AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET from env.
    The `tenant` parameter is accepted for interface compatibility but ignored.
    """
    tenant_id = os.environ["AZURE_TENANT_ID"]
    client_id = os.environ["AZURE_CLIENT_ID"]
    client_secret = os.environ["AZURE_CLIENT_SECRET"]
    url = f"{LOGIN_URL}/{tenant_id}/oauth2/v2.0/token"
    resp = requests.post(
        url,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": GRAPH_SCOPE,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]
