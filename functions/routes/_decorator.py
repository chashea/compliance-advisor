"""Shared HTTP helpers and the @advisor_route decorator.

The decorator collapses the boilerplate that was duplicated across all 17
dashboard handlers (``require_auth → get_body → call → json_response →
except``) into a single registration call.

Failure-mode contract (as of #18 fix):

- Body parse failure       → 400 ``{"error": "Invalid JSON body"}``
- Missing/invalid auth     → 401 (via :func:`shared.auth.get_auth_error_response`)
- Handler raises ValueError → 400 (e.g. validation failures)
- Handler raises any other → 500 (with exception class name in the log)

Two decorator surfaces are exposed:

- :func:`register_advisor_route` — for the simple read-only routes that
  forward only ``department`` and/or ``tenant_id`` from the request body.
- :func:`get_body` — bare body parser; raises :class:`BadJSONBodyError`
  when the body is non-empty but unparseable. Routes that need custom
  logic (rate limiting, route params) call it directly.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Iterable

import azure.functions as func

log = logging.getLogger(__name__)


class BadJSONBodyError(ValueError):
    """Raised when the request body is present but not valid JSON."""


def json_response(data: dict, status_code: int = 200) -> func.HttpResponse:
    """Serialise ``data`` to JSON and return an HttpResponse."""
    return func.HttpResponse(
        json.dumps(data, default=str),
        status_code=status_code,
        mimetype="application/json",
    )


def get_body(req: func.HttpRequest) -> dict:
    """Parse the request JSON body.

    Empty body → empty dict. Non-empty but malformed body → raises
    :class:`BadJSONBodyError` (the decorator turns it into a 400). This
    distinguishes "I sent nothing" from "I sent garbage" — the previous
    silent ``return {}`` masked the latter.
    """
    raw = req.get_body()
    if not raw or not raw.strip():
        return {}
    try:
        return req.get_json()
    except ValueError as exc:
        raise BadJSONBodyError(f"Invalid JSON body: {exc}") from exc


def get_body_or_400(req: func.HttpRequest) -> tuple[dict, func.HttpResponse | None]:
    """Convenience for handlers that don't use @register_advisor_route.

    Returns ``(body, None)`` on success or ``({}, error_response)`` when
    the body is malformed. Caller short-circuits via::

        body, err = get_body_or_400(req)
        if err is not None:
            return err
    """
    try:
        return get_body(req), None
    except BadJSONBodyError as exc:
        log.warning("Rejected malformed JSON body: %s", exc)
        return {}, json_response({"error": str(exc)}, 400)


def _filtered_kwargs(body: dict, allowed: Iterable[str]) -> dict[str, Any]:
    """Return ``{k: body.get(k) for k in allowed}`` so handlers always see
    the same kwarg surface (with ``None`` for unsupplied optional fields)."""
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
        from shared.logging import bind_request_context, clear_request_context

        bind_request_context(req, route=route_path)
        try:
            principal = require_auth(req)
            if principal is None:
                return get_auth_error_response()
            body = get_body(req)
            kwargs = _filtered_kwargs(body, body_args)
            return json_response(_impl._handler(**kwargs))
        except BadJSONBodyError as e:
            log.warning("%s rejected: %s", route_path, e)
            return json_response({"error": str(e)}, 400)
        except ValueError as e:
            # Handler-raised validation failure — client error, not server error.
            log.warning("%s validation error: %s", route_path, e)
            return json_response({"error": str(e)}, 400)
        except Exception as e:
            log.exception("%s error (%s): %s", route_path, type(e).__name__, e)
            return json_response({"error": str(e)}, 500)
        finally:
            clear_request_context()

    _impl.__name__ = fn_name
    # Expose the handler as a mutable attribute so tests can swap it
    # without recreating the closure. Production code should never write
    # to this — re-register the route instead.
    _impl._handler = handler  # type: ignore[attr-defined]
    decorated = bp.route(route=route_path, methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)(_impl)
    bp.function_name(fn_name)(decorated)
