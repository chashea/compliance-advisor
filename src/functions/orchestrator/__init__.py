"""
Durable orchestrator — fan-out across all active tenants in parallel.
Collects both Secure Score and Compliance Manager data.
"""
import logging
import azure.durable_functions as df


def orchestrator_function(context: df.DurableOrchestrationContext):
    # Step 1: Load active tenants from the registry
    tenants = yield context.call_activity("get_active_tenants", None)
    logging.info("Orchestrating sync for %d tenant(s)", len(tenants))

    # Step 2: Fan out — collect Secure Score + Compliance Manager in parallel
    tasks = []
    for tenant in tenants:
        tasks.append(context.call_activity("collect_tenant_data", tenant))
        tasks.append(context.call_activity("collect_compliance_data", tenant))
    results = yield context.task_all(tasks)

    # Step 3: Rebuild the AI Search index with the refreshed data
    yield context.call_activity("reindex_search", None)

    successes = sum(1 for r in results if r.get("success"))
    logging.info("Sync complete: %d/%d tasks succeeded", successes, len(results))
    return results


main = df.Orchestrator.create(orchestrator_function)
