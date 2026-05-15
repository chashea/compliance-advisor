"""Authentication middleware for Azure EasyAuth (Entra ID) and ingest JWTs."""

import base64
import json
import logging
from dataclasses import dataclass

import azure.functions as func

from shared.config import get_settings

log = logging.getLogger(__name__)

# Per-tenant JWKS clients are cached to avoid refetching on every request.
# PyJWKClient itself does in-process key caching with a 1h TTL.
_JWKS_URL_TEMPLATE = "https://login.microsoftonline.com/{tid}/discovery/v2.0/keys"
_jwks_clients: dict = {}


@dataclass
class IngestAuthError(Exception):
    """Raised when an ingest JWT cannot be validated."""

    status_code: int
    message: str

    def __str__(self) -> str:
        return self.message


def require_auth(req: func.HttpRequest) -> dict | None:
    """Validate EasyAuth identity headers.

    Returns the decoded principal dict if authenticated, None when
    authentication is required but missing/invalid.

    When ``AUTH_REQUIRED`` is false (local dev), a missing header is
    treated as authenticated and an empty dict is returned. When true
    (the production default), a missing header rejects the request.
    """
    principal_header = req.headers.get("X-MS-CLIENT-PRINCIPAL")

    if not principal_header:
        if get_settings().AUTH_REQUIRED:
            log.warning("Rejected unauthenticated request: missing X-MS-CLIENT-PRINCIPAL header")
            return None
        return {}

    try:
        decoded = base64.b64decode(principal_header)
        principal = json.loads(decoded)
        return principal
    except Exception as e:
        log.warning("Failed to decode X-MS-CLIENT-PRINCIPAL: %s", e)
        return None


def get_auth_error_response() -> func.HttpResponse:
    """Return a 401 response for unauthenticated requests."""
    return func.HttpResponse(
        json.dumps({"error": "Authentication required"}),
        status_code=401,
        mimetype="application/json",
    )


def _get_jwks_client(tenant_id: str):
    """Return (and cache) a PyJWKClient for the given Entra tenant."""
    import jwt

    if tenant_id not in _jwks_clients:
        _jwks_clients[tenant_id] = jwt.PyJWKClient(_JWKS_URL_TEMPLATE.format(tid=tenant_id))
    return _jwks_clients[tenant_id]


def verify_ingest_token(req: func.HttpRequest, payload_tenant_id: str) -> dict:
    """Validate an ingest JWT against Microsoft Entra ID.

    The token must:
    - Be presented as ``Authorization: Bearer <token>``.
    - Have a ``tid`` claim that is in ``ALLOWED_TENANT_IDS`` (when configured).
    - Have a ``tid`` claim that matches the payload's ``tenant_id``.
    - Have an ``aud`` claim equal to ``INGEST_AUDIENCE``.
    - Be signed by a JWKS key from ``login.microsoftonline.com/{tid}``.
    - When ``INGEST_EXPECTED_APPID`` is set, have an ``appid`` or ``azp``
      claim equal to that value.

    Returns the verified claims dict on success.

    Raises ``IngestAuthError`` with an appropriate HTTP status and message.
    """
    settings = get_settings()
    if not settings.INGEST_REQUIRE_JWT:
        return {}

    if not settings.INGEST_AUDIENCE:
        raise IngestAuthError(500, "Server misconfiguration: INGEST_AUDIENCE is not set")

    auth_header = req.headers.get("Authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise IngestAuthError(401, "Missing or malformed Authorization header")
    token = auth_header.split(" ", 1)[1].strip()

    import jwt

    try:
        unverified = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as exc:
        raise IngestAuthError(401, f"Token is not a valid JWT: {exc}") from exc

    token_tid = unverified.get("tid")
    if not token_tid:
        raise IngestAuthError(401, "Token missing required 'tid' claim")

    if settings.allowed_tenants and token_tid not in settings.allowed_tenants:
        log.warning("Rejected ingest from disallowed tenant: %s", token_tid)
        raise IngestAuthError(403, f"Tenant {token_tid} is not in the allow-list")

    if token_tid != payload_tenant_id:
        log.warning("Token tid (%s) does not match payload tenant_id (%s)", token_tid, payload_tenant_id)
        raise IngestAuthError(403, "Token tenant does not match payload tenant_id")

    try:
        jwks_client = _get_jwks_client(token_tid)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.INGEST_AUDIENCE,
            options={"require": ["exp", "iat", "tid", "aud"]},
        )
    except jwt.InvalidAudienceError as exc:
        raise IngestAuthError(401, f"Token audience mismatch: {exc}") from exc
    except jwt.ExpiredSignatureError as exc:
        raise IngestAuthError(401, f"Token expired: {exc}") from exc
    except jwt.PyJWTError as exc:
        raise IngestAuthError(401, f"Token signature validation failed: {exc}") from exc

    if settings.INGEST_EXPECTED_APPID:
        appid = claims.get("appid") or claims.get("azp")
        if appid != settings.INGEST_EXPECTED_APPID:
            log.warning("Rejected ingest token with appid %s (expected %s)", appid, settings.INGEST_EXPECTED_APPID)
            raise IngestAuthError(403, "Token application ID does not match expected collector app")

    return claims
