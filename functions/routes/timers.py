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

        # Single-roundtrip CTE per workload: pre-compute the latest snapshot
        # per tenant, then LEFT JOIN counts back into the tenants base set.
        # Replaces 4 correlated subqueries that scanned each table O(N) times.
        tenant_counts = query("""
            WITH latest_sens AS (
                SELECT tenant_id, MAX(snapshot_date) AS d
                FROM sensitivity_labels GROUP BY tenant_id
            ),
            sens_counts AS (
                SELECT sl.tenant_id, COUNT(*)::int AS n
                FROM sensitivity_labels sl
                JOIN latest_sens ls
                  ON ls.tenant_id = sl.tenant_id AND ls.d = sl.snapshot_date
                GROUP BY sl.tenant_id
            ),
            latest_dlp AS (
                SELECT tenant_id, MAX(snapshot_date) AS d
                FROM dlp_alerts GROUP BY tenant_id
            ),
            dlp_counts AS (
                SELECT da.tenant_id, COUNT(*)::int AS n
                FROM dlp_alerts da
                JOIN latest_dlp ld
                  ON ld.tenant_id = da.tenant_id AND ld.d = da.snapshot_date
                GROUP BY da.tenant_id
            ),
            latest_audit AS (
                SELECT tenant_id, MAX(snapshot_date) AS d
                FROM audit_records GROUP BY tenant_id
            ),
            audit_counts AS (
                SELECT ar.tenant_id, COUNT(*)::int AS n
                FROM audit_records ar
                JOIN latest_audit la
                  ON la.tenant_id = ar.tenant_id AND la.d = ar.snapshot_date
                GROUP BY ar.tenant_id
            )
            SELECT t.tenant_id, t.department,
                COALESCE(sc.n, 0) AS sensitivity,
                COALESCE(dc.n, 0) AS dlp,
                COALESCE(ac.n, 0) AS audit
            FROM tenants t
            LEFT JOIN sens_counts  sc ON sc.tenant_id = t.tenant_id
            LEFT JOIN dlp_counts   dc ON dc.tenant_id = t.tenant_id
            LEFT JOIN audit_counts ac ON ac.tenant_id = t.tenant_id
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
