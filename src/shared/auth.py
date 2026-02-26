"""
Per-tenant authentication helpers.
Uses Managed Identity to access Key Vault, then exchanges
each tenant's client credentials for a Graph API token.

M365 GCC uses global endpoints (no change needed). Set GRAPH_NATIONAL_CLOUD=usgovernment
only for GCC High/DoD (uses login.microsoftonline.us and graph.microsoft.us).

Provides get_graph_token() to obtain a bearer token for raw HTTP calls
to Microsoft Graph.
"""
import os
import requests
from azure.identity import AzureAuthorityHosts, ClientSecretCredential, DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

_kv_client: SecretClient | None = None

# National cloud: commercial (default) or usgovernment (GCC / GCC High / DoD)
_GRAPH_CLOUD = os.environ.get("GRAPH_NATIONAL_CLOUD", "").strip().lower()
_IS_USGOV = _GRAPH_CLOUD in ("usgovernment", "usgov", "gcc", "gcc high", "dod")

LOGIN_URL = "https://login.microsoftonline.us" if _IS_USGOV else "https://login.microsoftonline.com"
GRAPH_SCOPE = "https://graph.microsoft.us/.default" if _IS_USGOV else "https://graph.microsoft.com/.default"
GRAPH_AUTHORITY = AzureAuthorityHosts.AZURE_PUBLIC_CLOUD if not _IS_USGOV else AzureAuthorityHosts.AZURE_GOVERNMENT


def _get_kv_client() -> SecretClient:
    global _kv_client
    if _kv_client is None:
        vault_url = os.environ["KEY_VAULT_URL"]
        _kv_client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
    return _kv_client


def _get_tenant_credential(tenant: dict) -> ClientSecretCredential:
    """
    Build an Azure Identity credential for a specific tenant using
    client_id + client_secret stored in Key Vault.
    Uses government authority when GRAPH_NATIONAL_CLOUD=usgovernment.
    """
    client_secret = _get_kv_client().get_secret(tenant["kv_secret_name"]).value
    return ClientSecretCredential(
        tenant_id=tenant["tenant_id"],
        client_id=tenant["app_id"],
        client_secret=client_secret,
        authority=GRAPH_AUTHORITY,
    )


def get_graph_token(tenant: dict) -> str:
    """
    Fetch a Graph API bearer token for a specific tenant.

    When GRAPH_NATIONAL_CLOUD=usgovernment (GCC High/DoD), uses login.microsoftonline.us
    and scope https://graph.microsoft.us/.default.

    tenant dict must contain:
      - tenant_id      : Entra tenant GUID
      - app_id         : App registration client_id in that tenant
      - kv_secret_name : Name of the Key Vault secret holding the client_secret
    """
    client_secret = _get_kv_client().get_secret(tenant["kv_secret_name"]).value

    url = f"{LOGIN_URL}/{tenant['tenant_id']}/oauth2/v2.0/token"
    resp = requests.post(url, data={
        "grant_type": "client_credentials",
        "client_id": tenant["app_id"],
        "client_secret": client_secret,
        "scope": GRAPH_SCOPE,
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]
