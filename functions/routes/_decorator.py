"""Shared HTTP helpers and the @advisor_route decorator.

The decorator collapses the boilerplate that was duplicated across all 17
dashboard handlers (``_ensure_dependencies_loaded → require_auth →
_get_body → call → _json_response → except``) into a single registration
call.

Two decorator surfaces are exposed:

- :func:`register_advisor_route` — for the simple read-only routes that
  forward only ``department`` and/or ``tenant_id`` from the request body.
- :func:`json_route` — bare wrapper for routes that need custom logic
  (rate limiting, file uploads, route params). Provides the same
  exception handling but no auth or body-arg conventions.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Iterable

import azure.functions as func

log = logging.getLogger(__name__)


def json_response(data: dict, status_code: int = 200) -> func.HttpResponse:
    """Serialise ``data`` to JSON and return an HttpResponse."""
    return func.HttpResponse(
        json.dumps(data, default=str),
        status_code=status_code,
        mimetype="application/json",
    )


def get_body(req: func.HttpRequest) -> dict:
    """Parse the request JSON body, returning an empty dict on failure."""
    try:
        return req.get_json()
    except ValueError:
        log.warning("Failed to parse JSON body — returning empty dict")
        return {}


def _filtered_kwargs(body: dict, allowed: Iterable[str]) -> dict[str, Any]:
    """Return ``{k: body[k] for k in allowed if k in body}`` so handlers don't
    receive None for unsupplied optional fields when their default is meaningful."""
    return {k: body.get(k) for k in allowed}


def register_advisor_route(
    bp: func.Blueprint,
    name: str,
    handler: Callable[..., Any],
    *,
    body_args: tuple[str, ...] = ("department", "tenant_id"),
    route: str | None = None,
    function_name: str | None = None,
) -> None:
    """Register a POST advisor/{name} route on ``bp``.

    Args:
        bp: The blueprint to attach to.
        name: Path suffix under ``advisor/``. Used as the function name
            (``advisor_<name_with_underscores>``) when ``function_name``
            is not supplied.
        handler: A function returning a dict; called with the body kwargs
            in ``body_args`` (only those keys are passed).
        body_args: Names of optional body fields to forward to ``handler``.
        route: Override the route path (defaults to ``advisor/{name}``).
        function_name: Override the Functions runtime name.
    """
    route_path = route if route is not None else f"advisor/{name}"
    fn_name = function_name or f"advisor_{name.replace('-', '_').replace('/', '_')}"

    def _impl(req: func.HttpRequest) -> func.HttpResponse:
        from shared.auth import get_auth_error_response, require_auth

        try:
            principal = require_auth(req)
            if principal is None:
                return get_auth_error_response()
            body = get_body(req)
            kwargs = _filtered_kwargs(body, body_args)
            return json_response(handler(**kwargs))
        except Exception as e:
            log.exception("%s error: %s", route_path, e)
            return json_response({"error": str(e)}, 500)

    _impl.__name__ = fn_name
    decorated = bp.route(route=route_path, methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)(_impl)
    bp.function_name(fn_name)(decorated)
