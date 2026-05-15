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
