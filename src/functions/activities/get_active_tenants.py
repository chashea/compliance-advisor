"""
Activity: load all active tenant records from the registry.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from shared.sql_client import get_connection, set_admin_context, get_active_tenants


def main(payload: None) -> list[dict]:
    conn = get_connection()
    try:
        # tenants table has no RLS, but set admin context defensively
        set_admin_context(conn)
        return get_active_tenants(conn)
    finally:
        conn.close()
