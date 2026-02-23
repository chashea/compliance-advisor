#!/usr/bin/env bash
# =============================================================================
# onboard_tenant.sh — Register a new M365 tenant with the Compliance Advisor
#
# Usage:
#   ./scripts/onboard_tenant.sh \
#     --tenant-id       "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" \
#     --display-name    "Contoso Europe" \
#     --region          "EU" \
#     --department      "Finance"             # Agency / Department / BU \
#     --department-head  "Jane Smith"         # Head of department \
#     --risk-tier       "High"                # Critical, High, Medium, Low \
#     --app-id          "yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy" \
#     --key-vault       "kv-compliance-advisor-prod" \
#     --sql-server      "sql-compliance-advisor-prod.database.windows.net" \
#     --sql-db          "ComplianceAdvisor"
#
# The client secret is read from stdin to avoid it appearing in shell history,
# process listings, or CI/CD logs.
#
# Prerequisites:
#   - az CLI logged in with access to the central Azure subscription
#   - sqlcmd available
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
TENANT_ID="" DISPLAY_NAME="" REGION="" APP_ID=""
DEPARTMENT="" DEPARTMENT_HEAD="" RISK_TIER=""
KEY_VAULT="" SQL_SERVER="" SQL_DB=""

while [[ $# -gt 0 ]]; do
  case $1 in
    --tenant-id)       TENANT_ID="$2";       shift 2 ;;
    --display-name)    DISPLAY_NAME="$2";    shift 2 ;;
    --region)          REGION="$2";          shift 2 ;;
    --department)      DEPARTMENT="$2";      shift 2 ;;
    --department-head)  DEPARTMENT_HEAD="$2"; shift 2 ;;
    --risk-tier)       RISK_TIER="$2";       shift 2 ;;
    --app-id)          APP_ID="$2";          shift 2 ;;
    --key-vault)       KEY_VAULT="$2";       shift 2 ;;
    --sql-server)      SQL_SERVER="$2";      shift 2 ;;
    --sql-db)          SQL_DB="$2";          shift 2 ;;
    *) echo "Unknown argument: $1"; exit 1 ;;
  esac
done

# ── Validate required arguments ───────────────────────────────────────────────
for var in TENANT_ID DISPLAY_NAME APP_ID KEY_VAULT SQL_SERVER SQL_DB; do
  [[ -z "${!var}" ]] && { echo "ERROR: --${var,,} is required (use underscores as hyphens)"; exit 1; }
done

validate_uuid "tenant-id" "${TENANT_ID}"
validate_uuid "app-id"    "${APP_ID}"

# ── Read client secret securely from stdin ────────────────────────────────────
# Never pass secrets as command-line arguments — they appear in ps, history, and logs.
if [ -t 0 ]; then
  read -r -s -p "Enter the client secret for app ${APP_ID}: " CLIENT_SECRET
  echo ""
else
  # Non-interactive (e.g., piped input in automation)
  read -r CLIENT_SECRET
fi

[[ -z "${CLIENT_SECRET}" ]] && { echo "ERROR: client secret cannot be empty"; exit 1; }

KV_SECRET_NAME="tenant-${TENANT_ID}-secret"

echo ""
echo "Onboarding tenant: ${DISPLAY_NAME} (${TENANT_ID})"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Step 1: Store client secret in Key Vault ──────────────────────────────────
echo "[1/3] Storing client secret in Key Vault..."
printf '%s' "${CLIENT_SECRET}" | az keyvault secret set \
  --vault-name "${KEY_VAULT}" \
  --name       "${KV_SECRET_NAME}" \
  --file       /dev/stdin \
  --output none

# Clear the secret from memory as soon as possible
CLIENT_SECRET=""
unset CLIENT_SECRET

echo "      Secret stored as: ${KV_SECRET_NAME}"

# ── Step 2: Register tenant in SQL registry (parameterized via Python) ────────
echo "[2/3] Registering tenant in database..."

python3 - <<PYEOF
import sys, pyodbc, os

conn_str = os.environ.get("MSSQL_CONNECTION")
if not conn_str:
    # Fall back to interactive az token
    import subprocess, json
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

cursor.execute("""
    MERGE tenants AS t
    USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?)) AS s
        (tenant_id, display_name, region, department, department_head,
         risk_tier, app_id, kv_secret_name)
    ON t.tenant_id = s.tenant_id
    WHEN MATCHED THEN UPDATE SET
        display_name    = s.display_name,
        region          = s.region,
        department      = COALESCE(s.department, t.department),
        department_head = COALESCE(s.department_head, t.department_head),
        risk_tier       = COALESCE(s.risk_tier, t.risk_tier),
        app_id          = s.app_id,
        kv_secret_name  = s.kv_secret_name,
        is_active       = 1
    WHEN NOT MATCHED THEN INSERT
        (tenant_id, display_name, region, department, department_head,
         risk_tier, app_id, kv_secret_name)
        VALUES (s.tenant_id, s.display_name, s.region, s.department,
                s.department_head, s.risk_tier, s.app_id, s.kv_secret_name);
""",
    "${TENANT_ID}", "${DISPLAY_NAME}", "${REGION}",
    "${DEPARTMENT}" or None, "${DEPARTMENT_HEAD}" or None,
    "${RISK_TIER}" or None, "${APP_ID}", "${KV_SECRET_NAME}"
)
conn.commit()
conn.close()
print("      Tenant registered in database.")
PYEOF

# ── Step 3: Trigger an immediate sync ────────────────────────────────────────
echo "[3/3] Triggering initial data sync..."
FUNCTION_APP=$(az functionapp list \
  --query "[?contains(name, 'compliance-advisor')].name" -o tsv | head -1)

az functionapp function invoke \
  --name          "${FUNCTION_APP}" \
  --function-name "timer_trigger" \
  --resource-group "$(az functionapp show --name "${FUNCTION_APP}" --query resourceGroup -o tsv)" \
  --output none 2>/dev/null || true

echo ""
echo "Onboarding complete."
echo "  Tenant:      ${DISPLAY_NAME}"
echo "  Tenant ID:   ${TENANT_ID}"
echo "  KV Secret:   ${KV_SECRET_NAME}"
echo ""
echo "Data will appear in the dashboard within the next daily sync (02:00 UTC)."
echo "To trigger a manual sync now, run the orchestrator from the Azure Portal."
