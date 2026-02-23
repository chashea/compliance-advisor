"""
Per-tenant authentication helpers.
Uses Managed Identity to access Key Vault, then exchanges
each tenant's client credentials for a Graph API token.

Provides both:
  - get_graph_token()  : raw bearer token for legacy HTTP calls
  - get_graph_client() : typed msgraph-beta-sdk GraphServiceClient
"""
import os
import requests
from azure.identity import ClientSecretCredential, DefaultAzureCredential
from azure.keyvault.secrets import SecretClient
from msgraph_beta import GraphServiceClient

_kv_client: SecretClient | None = None


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
    """
    client_secret = _get_kv_client().get_secret(tenant["kv_secret_name"]).value
    return ClientSecretCredential(
        tenant_id=tenant["tenant_id"],
        client_id=tenant["app_id"],
        client_secret=client_secret,
    )


def get_graph_client(tenant: dict) -> GraphServiceClient:
    """
    Return a typed Microsoft Graph Beta SDK client for a specific tenant.

    The client provides fluent access to all beta Graph endpoints including
    Compliance Manager, Secure Score, Information Protection, etc. with
    built-in pagination, retry, and typed response models.

    Usage:
        client = get_graph_client(tenant)
        assessments = await client.security.compliance_manager.assessments.get()
    """
    credential = _get_tenant_credential(tenant)
    scopes = ["https://graph.microsoft.com/.default"]
    return GraphServiceClient(credential, scopes)


def get_graph_token(tenant: dict) -> str:
    """
    Fetch a Graph API bearer token for a specific tenant.
    (Legacy — prefer get_graph_client() for new code.)

    tenant dict must contain:
      - tenant_id      : Entra tenant GUID
      - app_id         : App registration client_id in that tenant
      - kv_secret_name : Name of the Key Vault secret holding the client_secret
    """
    client_secret = _get_kv_client().get_secret(tenant["kv_secret_name"]).value

    url = f"https://login.microsoftonline.com/{tenant['tenant_id']}/oauth2/v2.0/token"
    resp = requests.post(url, data={
        "grant_type": "client_credentials",
        "client_id": tenant["app_id"],
        "client_secret": client_secret,
        "scope": "https://graph.microsoft.com/.default",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["access_token"]
