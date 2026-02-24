#!/usr/bin/env bash
# =============================================================================
# offboard_tenant.sh — Deactivate an M365 tenant from the Compliance Advisor
#
# Usage:
#   ./scripts/offboard_tenant.sh \
#     --tenant-id   "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" \
#     --key-vault   "kv-compliance-advisor-prod" \
#     --sql-server  "sql-compliance-advisor-prod.database.windows.net" \
#     --sql-db      "ComplianceAdvisor"
#
# What this does:
#   1. Sets is_active = 0 in the tenants table (stops data sync)
#   2. Writes a TENANT_OFFBOARDED event to audit_log
#   3. Disables (but does not delete) the Key Vault secret so the credential
#      can be recovered if needed — run 'az keyvault secret delete' separately
#      for a hard delete, or 'az keyvault secret set-attributes --enabled true'
#      to re-enable.
#
# The tenant's historical data is preserved in SQL and AI Search.
# It will be excluded from all views and syncs immediately.
#
# Prerequisites:
#   - az CLI logged in with access to the central Azure subscription
#   - sqlcmd / pyodbc available (same as onboard_tenant.sh)
# =============================================================================
set -euo pipefail

# ── UUID validation helper ────────────────────────────────────────────────────
validate_uuid() {
  local name="$1" value="$2"
  if ! [[ "${value}" =~ ^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$ ]]; then
    echo "ERROR: ${name} is not a valid UUID: ${value}"
    exit 1
  fi
}

# ── Parse arguments ───────────────────────────────────────────────────────────
TENANT_ID="" KEY_VAULT="" SQL_SERVER="" SQL_DB=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --tenant-id)  TENANT_ID="$2";  shift 2 ;;
    --key-vault)  KEY_VAULT="$2";  shift 2 ;;
    --sql-server) SQL_SERVER="$2"; shift 2 ;;
    --sql-db)     SQL_DB="$2";     shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# ── Validate required arguments ───────────────────────────────────────────────
for var in TENANT_ID KEY_VAULT SQL_SERVER SQL_DB; do
  [[ -z "${!var}" ]] && { echo "ERROR: --${var,,} is required"; exit 1; }
done

validate_uuid "tenant-id" "${TENANT_ID}"

KV_SECRET_NAME="tenant-${TENANT_ID}-secret"

# ── Resolve caller identity for audit log ─────────────────────────────────────
PERFORMED_BY=$(az account show --query "user.name" -o tsv 2>/dev/null || echo "unknown")

echo ""
echo "Offboarding tenant: ${TENANT_ID}"
echo "Performed by:       ${PERFORMED_BY}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Step 1: Deactivate tenant in SQL + write audit log ────────────────────────
echo "[1/2] Deactivating tenant in database..."

python3 - <<PYEOF
import sys, pyodbc, os, json

conn_str = os.environ.get("MSSQL_CONNECTION")
if not conn_str:
    import subprocess
    token_json = subprocess.check_output([
        "az", "account", "get-access-token",
        "--resource", "https://database.windows.net/",
        "--output", "json"
    ])
    token = json.loads(token_json)["accessToken"]
    conn_str = (
        "Driver={ODBC Driver 18 for SQL Server};"
        f"Server=tcp:${SQL_SERVER},1433;"
        f"Database=${SQL_DB};"
        "Authentication=ActiveDirectoryAccessToken;"
        f"AccessToken={token};"
    )

conn   = pyodbc.connect(conn_str, autocommit=False)
cursor = conn.cursor()

# Verify the tenant exists before touching anything
cursor.execute(
    "SELECT display_name, is_active FROM tenants WHERE tenant_id = ?",
    "${TENANT_ID}"
)
row = cursor.fetchone()
if not row:
    print(f"ERROR: Tenant ${TENANT_ID} not found in the database.", file=sys.stderr)
    conn.close()
    sys.exit(1)

display_name, is_active = row

if not is_active:
    print(f"      Tenant '{display_name}' is already inactive — nothing to do.")
    conn.close()
    sys.exit(0)

# Deactivate the tenant
cursor.execute(
    "UPDATE tenants SET is_active = 0 WHERE tenant_id = ?",
    "${TENANT_ID}"
)

# Write immutable audit record
details = json.dumps({
    "display_name": display_name,
    "kv_secret_name": "${KV_SECRET_NAME}",
    "action": "set is_active = 0",
})
cursor.execute(
    """
    INSERT INTO audit_log (event_type, tenant_id, performed_by, details)
    VALUES ('TENANT_OFFBOARDED', ?, ?, ?)
    """,
    "${TENANT_ID}", "${PERFORMED_BY}", details,
)

conn.commit()
conn.close()
print(f"      Tenant '{display_name}' deactivated and audit record written.")
PYEOF

# ── Step 2: Disable Key Vault secret ─────────────────────────────────────────
# Disabling (not deleting) preserves the secret for recovery.
# To hard-delete: az keyvault secret delete --vault-name ... --name ...
echo "[2/2] Disabling Key Vault secret (recoverable)..."

if az keyvault secret show \
     --vault-name "${KEY_VAULT}" \
     --name       "${KV_SECRET_NAME}" \
     --output none 2>/dev/null; then

  az keyvault secret set-attributes \
    --vault-name "${KEY_VAULT}" \
    --name       "${KV_SECRET_NAME}" \
    --enabled    false \
    --output none

  echo "      Secret '${KV_SECRET_NAME}' disabled."
  echo "      To re-enable: az keyvault secret set-attributes --vault-name ${KEY_VAULT} --name ${KV_SECRET_NAME} --enabled true"
  echo "      To hard-delete: az keyvault secret delete --vault-name ${KEY_VAULT} --name ${KV_SECRET_NAME}"
else
  echo "      Secret '${KV_SECRET_NAME}' not found in Key Vault — skipping."
fi

echo ""
echo "Offboarding complete."
echo "  Tenant ID:  ${TENANT_ID}"
echo "  KV Secret:  ${KV_SECRET_NAME} (disabled)"
echo ""
echo "Historical data is preserved in SQL. The tenant will be excluded from"
echo "all dashboard views, AI Search indexes, and scheduled syncs immediately."
echo "The AI Search index will reflect this on the next reindex (daily at 02:00 UTC)."
echo "To trigger an immediate reindex, run the orchestrator from the Azure Portal."
