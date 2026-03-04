#!/usr/bin/env python3
"""Pull Secure Score + Compliance Manager data for one M365 tenant → SQLite."""
import sys
import os
import logging
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent / "src"))

from shared.sql_client import get_connection

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("sync")


def get_local_tenant() -> dict:
    return {
        "tenant_id":      os.environ["AZURE_TENANT_ID"],
        "display_name":   os.environ.get("TENANT_DISPLAY_NAME", "My Tenant"),
        "app_id":         os.environ["AZURE_CLIENT_ID"],
        "kv_secret_name": "",
        "department":     os.environ.get("TENANT_DEPARTMENT"),
        "risk_tier":      os.environ.get("TENANT_RISK_TIER", "High"),
    }


def ensure_tenant_row(tenant: dict) -> None:
    conn = get_connection()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO tenants
                (tenant_id, display_name, department, risk_tier, app_id, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (
            tenant["tenant_id"], tenant["display_name"],
            tenant.get("department"), tenant.get("risk_tier"), tenant["app_id"],
        ))
        conn.commit()
    finally:
        conn.close()


def main():
    from functions.activities.collect_tenant_data import main as sync_ss
    from functions.activities.collect_compliance_data import main as sync_cm

    tenant = get_local_tenant()
    ensure_tenant_row(tenant)

    log.info("Syncing Secure Score...")
    log.info(sync_ss(tenant))

    log.info("Syncing Compliance Manager...")
    log.info(sync_cm(tenant))

    log.info("Sync complete.")


if __name__ == "__main__":
    main()
