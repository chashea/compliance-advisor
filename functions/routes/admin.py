"""Operational routes: health check and schema migrations (yoyo)."""

from __future__ import annotations

import logging
import os

import azure.functions as func
from shared.db import _build_dsn, _get_pool

from routes._decorator import json_response

log = logging.getLogger(__name__)

bp = func.Blueprint()


@bp.function_name("health")
@bp.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    try:
        pool = _get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            pool.putconn(conn)
        return json_response({"status": "healthy"})
    except Exception as e:
        log.exception("health check failed: %s", e)
        return json_response({"status": "unhealthy", "error": str(e)}, 503)


def _check_db() -> dict:
    import time

    start = time.monotonic()
    try:
        pool = _get_pool()
        conn = pool.getconn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        finally:
            pool.putconn(conn)
        return {"status": "ok", "latency_ms": int((time.monotonic() - start) * 1000)}
    except Exception as e:
        log.exception("deep health: db probe failed")
        return {"status": "error", "error": str(e), "latency_ms": int((time.monotonic() - start) * 1000)}


def _check_keyvault() -> dict:
    import time

    from shared.config import get_settings

    settings = get_settings()
    if not settings.KEY_VAULT_URL:
        return {"status": "skipped", "reason": "KEY_VAULT_URL not configured"}
    start = time.monotonic()
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        client = SecretClient(vault_url=settings.KEY_VAULT_URL, credential=DefaultAzureCredential())
        # list_properties_of_secrets is a lightweight metadata-only call.
        next(client.list_properties_of_secrets(), None)
        return {"status": "ok", "latency_ms": int((time.monotonic() - start) * 1000)}
    except Exception as e:
        log.exception("deep health: key vault probe failed")
        return {"status": "error", "error": str(e), "latency_ms": int((time.monotonic() - start) * 1000)}


def _check_openai() -> dict:
    import time

    from shared.config import get_settings

    settings = get_settings()
    if not settings.AZURE_OPENAI_ENDPOINT:
        return {"status": "skipped", "reason": "AZURE_OPENAI_ENDPOINT not configured"}
    start = time.monotonic()
    try:
        from azure.identity import DefaultAzureCredential, get_bearer_token_provider

        # Acquiring a token verifies the MI has the right RBAC and the
        # endpoint is reachable from the VNet. We don't issue a chat call
        # because that would burn quota.
        provider = get_bearer_token_provider(
            DefaultAzureCredential(),
            "https://cognitiveservices.azure.com/.default",
        )
        token = provider()
        ok = bool(token)
        return {
            "status": "ok" if ok else "error",
            "latency_ms": int((time.monotonic() - start) * 1000),
        }
    except Exception as e:
        log.exception("deep health: openai probe failed")
        return {"status": "error", "error": str(e), "latency_ms": int((time.monotonic() - start) * 1000)}


@bp.function_name("health_deep")
@bp.route(route="health/deep", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health_deep(req: func.HttpRequest) -> func.HttpResponse:
    """Deeper probe: verifies DB, Key Vault, and Azure OpenAI reachability.

    Per-component status with latency. Returns 200 when all non-skipped
    components are ``ok``; 503 when any component is in ``error``.

    Honours the configured rate limiter (same backend as AI endpoints) so
    this endpoint cannot be used as a free reconnaissance oracle.
    """
    try:
        from shared.rate_limit import get_rate_limiter

        forwarded = req.headers.get("X-Forwarded-For", "")
        client_ip = forwarded.split(",")[0].strip() if forwarded else "unknown"
        if get_rate_limiter().is_rate_limited(f"health_deep:{client_ip}"):
            return json_response({"error": "Rate limit exceeded"}, 429)

        components = {
            "db": _check_db(),
            "keyvault": _check_keyvault(),
            "openai": _check_openai(),
        }
        any_error = any(c.get("status") == "error" for c in components.values())
        return json_response(
            {"status": "unhealthy" if any_error else "healthy", "components": components},
            503 if any_error else 200,
        )
    except Exception as e:
        log.exception("health_deep error: %s", e)
        return json_response({"error": str(e)}, 500)


def _migrations_dir() -> str:
    """Locate sql/migrations/, supporting bundled (functions/sql/) and repo layouts."""
    candidates = [
        os.environ.get("MIGRATIONS_DIR"),
        os.path.join(os.path.dirname(__file__), "..", "sql", "migrations"),
        os.path.join(os.path.dirname(__file__), "..", "..", "sql", "migrations"),
    ]
    for path in candidates:
        if path and os.path.isdir(path):
            return os.path.abspath(path)
    raise FileNotFoundError(f"sql/migrations/ not found; tried {candidates}")


def _to_yoyo_dsn(dsn: str) -> str:
    """yoyo expects a URL-style DSN; libpq keyword strings need translation."""
    if dsn.startswith("postgresql://") or dsn.startswith("postgres://"):
        return dsn
    kv = dict(part.split("=", 1) for part in dsn.split() if "=" in part)
    return (
        f"postgresql://{kv.get('user', '')}:{kv.get('password', '')}"
        f"@{kv.get('host', '')}/{kv.get('dbname', '')}"
        f"?sslmode={kv.get('sslmode', 'require')}"
    )


# PostgreSQL is private-network-only, so CI cannot reach it directly.
# This endpoint applies pending yoyo migrations from inside the VNet using
# the Function App's managed identity. Function-key auth.
@bp.function_name("admin_migrate")
@bp.route(route="admin/migrate", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def admin_migrate(req: func.HttpRequest) -> func.HttpResponse:
    try:
        from yoyo import get_backend, read_migrations

        migrations_dir = _migrations_dir()
        dsn, _expires = _build_dsn()
        backend = get_backend(_to_yoyo_dsn(dsn))
        migrations = read_migrations(migrations_dir)

        with backend.lock():
            to_apply = backend.to_apply(migrations)
            applied_ids = [m.id for m in to_apply]
            backend.apply_migrations(to_apply)

        log.info("admin_migrate: applied %d migrations from %s: %s", len(applied_ids), migrations_dir, applied_ids)
        return json_response({
            "status": "ok",
            "migrations_dir": migrations_dir,
            "applied": applied_ids,
            "applied_count": len(applied_ids),
        })
    except Exception as e:
        log.exception("admin_migrate error: %s", e)
        return json_response({"error": str(e)}, 500)
