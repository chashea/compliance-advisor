"""
Durable orchestrator — fan-out across all active tenants in parallel.
Collects both Secure Score and Compliance Manager data.
"""
import logging
import azure.durable_functions as df

# ── Retry policies ────────────────────────────────────────────────────────────
#
# SQL activity (get_active_tenants, reindex_search):
#   3 attempts, 5 s → 10 s → 20 s (capped at 30 s).
#
# Graph API activities (collect_tenant_data, collect_compliance_data):
#   3 attempts, 15 s → 30 s → 60 s (capped at 60 s).
#   Microsoft Graph can return 429 / 503 under load; longer back-off avoids
#   hammering the throttle window.
#
# Retries only fire on unhandled exceptions from the activity function itself.
# Application-level errors (auth failures, missing data) are returned as
# {"success": False, "error": "..."} and are NOT retried.

_SQL_RETRY = df.RetryOptions(
    first_retry_interval_in_milliseconds=5_000,
    max_number_of_attempts=3,
    back_off_coefficient=2.0,
    max_retry_interval_in_milliseconds=30_000,
)

_GRAPH_RETRY = df.RetryOptions(
    first_retry_interval_in_milliseconds=15_000,
    max_number_of_attempts=3,
    back_off_coefficient=2.0,
    max_retry_interval_in_milliseconds=60_000,
)


def orchestrator_function(context: df.DurableOrchestrationContext):
    # Step 1: Load active tenants from the registry
    tenants = yield context.call_activity_with_retry(
        "get_active_tenants", _SQL_RETRY, None
    )
    logging.info("Orchestrating sync for %d tenant(s)", len(tenants))

    # Step 2: Fan out — collect Secure Score + Compliance Manager in parallel.
    # Each call retries independently so a single flaky tenant doesn't block others.
    tasks = []
    for tenant in tenants:
        tasks.append(
            context.call_activity_with_retry("collect_tenant_data", _GRAPH_RETRY, tenant)
        )
        tasks.append(
            context.call_activity_with_retry("collect_compliance_data", _GRAPH_RETRY, tenant)
        )
    results = yield context.task_all(tasks)

    # Step 3: Rebuild the AI Search index with the refreshed data.
    # Runs even on partial failure so the index reflects whatever was collected.
    yield context.call_activity_with_retry("reindex_search", _SQL_RETRY, None)

    successes = sum(1 for r in results if r.get("success"))
    logging.info("Sync complete: %d/%d tasks succeeded", successes, len(results))
    return results


main = df.Orchestrator.create(orchestrator_function)
