"""Authentication middleware for Azure EasyAuth (Entra ID)."""

import base64
import json
import logging

import azure.functions as func

log = logging.getLogger(__name__)


def require_auth(req: func.HttpRequest) -> dict | None:
    """Validate EasyAuth identity headers.

    Returns the decoded principal dict if authenticated, None otherwise.
    When EasyAuth is not enabled (no header present), returns an empty dict
    to allow pass-through (auth is opt-in via ENTRA_CLIENT_ID).
    """
    principal_header = req.headers.get("X-MS-CLIENT-PRINCIPAL")

    if not principal_header:
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
