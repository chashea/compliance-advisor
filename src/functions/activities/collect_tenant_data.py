"""
Activity: pull Secure Score data for a single tenant and persist it.
One instance of this runs per tenant, all in parallel.
"""
import logging
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from shared.auth import get_graph_token
from shared.graph_client import get_secure_scores, get_control_profiles
from shared.sql_client import (
    get_connection,
    set_tenant_context,
    upsert_secure_score,
    upsert_control_scores,
    upsert_control_profiles,
    upsert_benchmarks,
    mark_tenant_synced,
)


def main(tenant: dict) -> dict:
    tenant_id = tenant["tenant_id"]
    log = logging.getLogger(tenant_id)

    try:
        token = get_graph_token(tenant)
        log.info("Authenticated against tenant %s", tenant_id)

        scores   = get_secure_scores(token, days=90)
        profiles = get_control_profiles(token)
        log.info("Fetched %d snapshots, %d profiles", len(scores), len(profiles))

        conn = get_connection()
        try:
            # Scope all writes to this tenant — required for RLS predicate
            set_tenant_context(conn, tenant_id)

            # Persist each daily snapshot
            for score in scores:
                snapshot_date = score["createdDateTime"][:10]
                upsert_secure_score(conn, tenant_id, score)
                upsert_control_scores(conn, tenant_id, snapshot_date,
                                      score.get("controlScores", []))
                upsert_benchmarks(conn, tenant_id, snapshot_date,
                                  score.get("averageComparativeScores", []))

            # Refresh control profile catalog
            upsert_control_profiles(conn, tenant_id, profiles)
            mark_tenant_synced(conn, tenant_id)
        finally:
            conn.close()

        return {"tenant_id": tenant_id, "success": True, "snapshots": len(scores)}

    except Exception as exc:
        log.error("Failed to sync tenant %s: %s", tenant_id, exc)
        return {"tenant_id": tenant_id, "success": False, "error": str(exc)}
