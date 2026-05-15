"""Scheduled timer triggers: nightly tenant collection + daily aggregates."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

import azure.functions as func
from shared.db import query, upsert_trend

from routes.collect import _COLLECTOR_IMPORT_ERROR, _collect_single_tenant

log = logging.getLogger(__name__)

bp = func.Blueprint()


@bp.function_name("collect_tenants")
@bp.timer_trigger(schedule="0 0 14 * * 1-5", arg_name="timer", run_on_startup=False)
def collect_tenants(timer: func.TimerRequest) -> None:
    """Weekdays at 2:00 PM UTC: collect compliance data from all registered tenants."""
    try:
        from shared.config import get_settings

        settings = get_settings()
        client_id = settings.COLLECTOR_CLIENT_ID
        client_secret = settings.COLLECTOR_CLIENT_SECRET

        if not client_id or not client_secret:
            log.warning("collect_tenants: COLLECTOR_CLIENT_ID/SECRET not configured, skipping")
            return

        if _COLLECTOR_IMPORT_ERROR is not None:
            log.error("collect_tenants: collector imports failed at startup: %s", _COLLECTOR_IMPORT_ERROR)
            return

        audit_days = settings.COLLECTOR_AUDIT_LOG_DAYS

        tenants = query("SELECT tenant_id, display_name, department FROM tenants")
        if not tenants:
            log.info("collect_tenants: no tenants registered, skipping")
            return

        successes = 0
        failures = 0

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(
                    _collect_single_tenant,
                    tid=tenant["tenant_id"],
                    display_name=tenant.get("display_name", ""),
                    department=tenant.get("department", ""),
                    client_id=client_id,
                    client_secret=client_secret,
                    audit_days=audit_days,
                ): tenant["tenant_id"]
                for tenant in tenants
            }

            for future in as_completed(futures):
                tid = futures[future]
                try:
                    result = future.result()
                    if result["status"] == "ok":
                        successes += 1
                    else:
                        failures += 1
                except Exception:
                    log.exception("collect_tenants: unhandled error for tenant=%s", tid)
                    failures += 1

        log.info("collect_tenants: completed — %d succeeded, %d failed", successes, failures)

    except Exception as e:
        log.exception("collect_tenants: fatal error: %s", e)


@bp.function_name("compute_aggregates")
@bp.timer_trigger(schedule="0 0 16 * * 1-5", arg_name="timer", run_on_startup=False)
def compute_aggregates(timer: func.TimerRequest) -> None:
    """Weekdays at 4:00 PM UTC: compute compliance workload trend rows."""
    try:
        from datetime import date

        today = date.today().isoformat()

        tenant_counts = query("""
            SELECT t.tenant_id, t.department,
                (SELECT COUNT(*) FROM sensitivity_labels sl
                 WHERE sl.tenant_id = t.tenant_id
                   AND sl.snapshot_date = (
                     SELECT MAX(snapshot_date) FROM sensitivity_labels
                     WHERE tenant_id = t.tenant_id)
                )::int AS sensitivity,
                (SELECT COUNT(*) FROM dlp_alerts da
                 WHERE da.tenant_id = t.tenant_id
                   AND da.snapshot_date = (
                     SELECT MAX(snapshot_date) FROM dlp_alerts
                     WHERE tenant_id = t.tenant_id)
                )::int AS dlp,
                (SELECT COUNT(*) FROM audit_records ar
                 WHERE ar.tenant_id = t.tenant_id
                   AND ar.snapshot_date = (
                     SELECT MAX(snapshot_date) FROM audit_records
                     WHERE tenant_id = t.tenant_id)
                )::int AS audit
            FROM tenants t
            """)

        if not tenant_counts:
            log.info("No tenants found, skipping aggregate computation")
            return

        # Statewide aggregate
        upsert_trend(
            snapshot_date=today,
            department=None,
            sensitivity_labels=sum(r["sensitivity"] for r in tenant_counts),
            dlp_alerts=sum(r["dlp"] for r in tenant_counts),
            audit_records=sum(r["audit"] for r in tenant_counts),
            tenant_count=len(tenant_counts),
        )

        # Per-department aggregates
        depts: dict[str, list] = {}
        for r in tenant_counts:
            dept = r.get("department")
            if dept:
                depts.setdefault(dept, []).append(r)

        for dept, rows in depts.items():
            upsert_trend(
                snapshot_date=today,
                department=dept,
                sensitivity_labels=sum(r["sensitivity"] for r in rows),
                dlp_alerts=sum(r["dlp"] for r in rows),
                audit_records=sum(r["audit"] for r in rows),
                tenant_count=len(rows),
            )

        log.info("Computed trend aggregates: %d tenants, %d departments", len(tenant_counts), len(depts))

    except Exception as e:
        log.exception("Aggregate computation failed: %s", e)
