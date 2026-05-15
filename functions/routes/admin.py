"""Operational routes: health check and schema migration."""

from __future__ import annotations

import logging
import os

import azure.functions as func
from shared.db import _get_pool, get_conn

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


# PostgreSQL is private-network-only, so CI cannot reach it directly.
# This endpoint runs sql/schema.sql against the database from inside the
# VNet using the Function App's managed identity. Function-key auth.
@bp.function_name("admin_migrate")
@bp.route(route="admin/migrate", methods=["POST"], auth_level=func.AuthLevel.FUNCTION)
def admin_migrate(req: func.HttpRequest) -> func.HttpResponse:
    try:
        schema_path = os.environ.get("SCHEMA_PATH", "sql/schema.sql")
        candidates = [
            schema_path,
            os.path.join(os.path.dirname(__file__), "..", schema_path),
            os.path.join(os.path.dirname(__file__), "..", "..", schema_path),
        ]
        sql_text = None
        used_path = None
        for path in candidates:
            try:
                with open(path, encoding="utf-8") as f:
                    sql_text = f.read()
                used_path = path
                break
            except FileNotFoundError:
                continue

        if sql_text is None:
            return json_response({"error": f"schema.sql not found; tried {candidates}"}, 500)

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql_text)

        log.info("admin_migrate: applied schema from %s (%d bytes)", used_path, len(sql_text))
        return json_response({"status": "ok", "applied": used_path, "bytes": len(sql_text)})
    except Exception as e:
        log.exception("admin_migrate error: %s", e)
        return json_response({"error": str(e)}, 500)
