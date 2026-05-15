"""Structured logging for the Compliance Advisor Function App.

Wraps the Python ``logging`` module with ``structlog`` so log records
emit JSON to stdout. Azure Functions forwards stdout to Application
Insights as ``traces``, where each top-level key becomes a queryable
``customDimensions`` field. Result: KQL queries like::

    traces
    | where customDimensions.route == "advisor/dlp"
    | where customDimensions.tenant_id == "..."

work without parsing the message string.

Usage from a route::

    from shared.logging import bind_request_context, get_logger

    log = get_logger(__name__)

    def handler(req):
        bind_request_context(req, route="advisor/dlp")
        log.info("dispatched", department="DOJ")  # → JSON with route + dept

The bound context is thread-local and clears at the next ``bind_request_context``
call (or via ``unbind_all`` on exception cleanup).
"""

from __future__ import annotations

import logging
import os
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars

_configured = False


def configure() -> None:
    """Idempotently install the structlog pipeline.

    Called once on first ``get_logger`` request. Honours ``LOG_FORMAT``
    (``json`` for prod, ``console`` for local dev — auto-detected from
    presence of ``FUNCTIONS_WORKER_RUNTIME``).
    """
    global _configured
    if _configured:
        return

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    is_prod = bool(os.environ.get("FUNCTIONS_WORKER_RUNTIME"))
    fmt = os.environ.get("LOG_FORMAT") or ("json" if is_prod else "console")

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if fmt == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None) -> Any:
    """Return a structlog logger; auto-configures on first call."""
    if not _configured:
        configure()
    return structlog.get_logger(name) if name else structlog.get_logger()


def bind_request_context(req: Any, *, route: str | None = None, **extra: Any) -> None:
    """Bind per-request context (thread-local) so subsequent log calls in
    the same handler include these fields without repetition.

    Always pulls the ``X-Forwarded-For`` client IP and ``x-ms-request-id``
    when present. ``route`` should be the logical route name (e.g.
    ``"advisor/dlp"``); pass extra fields like ``tenant_id`` as kwargs.
    """
    clear_contextvars()
    headers = getattr(req, "headers", {}) or {}
    forwarded = headers.get("X-Forwarded-For", "") if hasattr(headers, "get") else ""
    client_ip = forwarded.split(",")[0].strip() if forwarded else None
    request_id = headers.get("x-ms-request-id") if hasattr(headers, "get") else None

    fields: dict[str, Any] = {}
    if route:
        fields["route"] = route
    if client_ip:
        fields["client_ip"] = client_ip
    if request_id:
        fields["request_id"] = request_id
    fields.update({k: v for k, v in extra.items() if v is not None})
    if fields:
        bind_contextvars(**fields)


def clear_request_context() -> None:
    """Reset per-request context. Safe to call from handler ``finally`` blocks."""
    clear_contextvars()
