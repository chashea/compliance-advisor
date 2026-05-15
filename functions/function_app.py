"""
Compliance Advisor — Azure Function App entry point.

The handler logic lives in :mod:`routes` (one blueprint per concern).
This module is the thin shell the Functions runtime indexes:

- Constructs the singleton ``FunctionApp`` instance.
- Registers each blueprint.
- Re-exports route handlers and dependencies that the test suite patches
  on the legacy ``function_app.*`` import paths (kept as a stable surface
  so the refactor is non-breaking for tests).
"""

from __future__ import annotations

import logging

import azure.functions as func
from routes import admin, ai, collect, dashboard, ingest, tenants, timers

log = logging.getLogger(__name__)

app = func.FunctionApp()

for _bp in (admin.bp, dashboard.bp, ai.bp, ingest.bp, tenants.bp, collect.bp, timers.bp):
    app.register_blueprint(_bp)


# ── Test-compatibility re-exports ─────────────────────────────────
# Existing tests import these symbols from ``function_app`` directly.
# Re-exporting preserves both the import paths and the patch targets
# (``patch("functions.function_app.upsert_tenant", ...)``).

# Route handlers exposed to tests
from routes.ai import advisor_ask, advisor_briefing  # noqa: E402,F401
from routes.collect import (  # noqa: E402,F401
    _COLLECTOR_IMPORT_ERROR,
    _HUNT_SEMAPHORE,
    _HUNTER_IMPORT_ERROR,
    _collect_single_tenant,
    _hunt_single_tenant,
    _trigger_collection_async,
    collect_assessments,
    collect_audit_log_records,
    collect_dlp_alerts,
    collect_dlp_policies,
    collect_improvement_actions,
    collect_info_barriers,
    collect_irm_alerts,
    collect_irm_policies,
    collect_protection_scopes,
    collect_purview_incidents,
    collect_retention_event_types,
    collect_retention_events,
    collect_retention_labels,
    collect_secure_scores,
    collect_sensitive_info_types,
    collect_sensitivity_labels,
    collect_single,
    collect_threat_assessments,
    collect_user_content_policies,
    get_graph_token,
    hunt_single,
)
from routes.tenants import register_tenant, tenant_consent_callback  # noqa: E402,F401
from routes.timers import collect_tenants, compute_aggregates  # noqa: E402,F401

# DB helpers patched by tests
from shared.db import (  # noqa: E402,F401
    check_ingestion_duplicate,
    insert_hunt_result,
    insert_hunt_run,
    query,
    record_ingestion,
    update_tenant_status,
    upsert_audit_record,
    upsert_compliance_assessment,
    upsert_dlp_alert,
    upsert_dlp_policy,
    upsert_improvement_action,
    upsert_info_barrier_policy,
    upsert_irm_alert,
    upsert_irm_policy,
    upsert_protection_scope,
    upsert_purview_incident,
    upsert_retention_event,
    upsert_retention_event_type,
    upsert_retention_label,
    upsert_secure_score,
    upsert_sensitive_info_type,
    upsert_sensitivity_label,
    upsert_tenant,
    upsert_threat_assessment_request,
    upsert_trend,
    upsert_user_content_policies,
)

# The original ``_DEPENDENCY_IMPORT_ERROR`` sentinel is no longer needed
# (each route module imports its own dependencies) but is preserved so
# tests that ``patch("functions.function_app._DEPENDENCY_IMPORT_ERROR")``
# do not break.
_DEPENDENCY_IMPORT_ERROR: Exception | None = None
