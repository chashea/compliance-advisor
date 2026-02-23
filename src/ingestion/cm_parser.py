"""
Compliance Manager Excel export parser.
Reads the standard .xlsx produced by:
  Compliance Manager → Improvement actions → Export actions
and writes rows into the cm_actions table.
"""
import io
import re
import pandas as pd
from shared.sql_client import get_connection, set_tenant_context

MAX_FILE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_ROWS       = 10_000
UUID_RE        = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)

EXPECTED_COLUMNS = {
    "Action":          "action_name",
    "Category":        "category",
    "Points achieved": "score",
    "Max points":      "max_score",
    "Status":          "status",
    "Assigned to":     "owner",
    "Regulation":      "framework",
    "Notes":           "notes",
}
REQUIRED_COLUMNS = {"Action", "Points achieved", "Max points", "Regulation"}

# Max lengths matching SQL schema column definitions
_STR_LIMITS = {
    "action_name": 300, "category": 100, "framework": 100,
    "status": 50,       "owner": 200,    "notes": 2000,
}


def parse_and_store(tenant_id: str, xlsx_bytes: bytes) -> int:
    """
    Parse a Compliance Manager export and upsert rows for tenant_id.
    Returns the number of rows processed.
    Raises ValueError for invalid inputs.
    """
    # ── Validate tenant_id ────────────────────────────────────────────────────
    if not isinstance(tenant_id, str) or not UUID_RE.match(tenant_id):
        raise ValueError("tenant_id must be a valid UUID")

    # ── Validate file ─────────────────────────────────────────────────────────
    if not isinstance(xlsx_bytes, (bytes, bytearray)):
        raise TypeError("xlsx_bytes must be bytes")
    if len(xlsx_bytes) > MAX_FILE_BYTES:
        raise ValueError(
            f"File exceeds maximum allowed size of {MAX_FILE_BYTES // (1024 * 1024)} MB"
        )

    # ── Parse Excel ───────────────────────────────────────────────────────────
    try:
        df = pd.read_excel(io.BytesIO(xlsx_bytes), sheet_name=0, engine="openpyxl")
    except Exception as exc:
        raise ValueError(f"Could not parse Excel file: {exc}") from exc

    # ── Validate required columns ─────────────────────────────────────────────
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Excel file is missing required columns: {missing}")

    if len(df) > MAX_ROWS:
        raise ValueError(f"File contains more than {MAX_ROWS} rows")

    # ── Normalize ─────────────────────────────────────────────────────────────
    present = {k: v for k, v in EXPECTED_COLUMNS.items() if k in df.columns}
    df = df[list(present.keys())].rename(columns=present)

    df["score"]     = pd.to_numeric(df.get("score"),     errors="coerce")
    df["max_score"] = pd.to_numeric(df.get("max_score"), errors="coerce")

    for col, max_len in _STR_LIMITS.items():
        if col in df.columns:
            df[col] = df[col].astype(str).str.slice(0, max_len)

    df = df.where(pd.notna(df), None)

    conn = get_connection()
    try:
        # Scope all writes to this tenant — required for RLS predicate
        set_tenant_context(conn, tenant_id)
        cursor = conn.cursor()

        for _, row in df.iterrows():
            cursor.execute("""
            MERGE cm_actions AS t
            USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?)) AS s
                (tenant_id, action_name, category, framework,
                 score, max_score, status, owner)
            ON  t.tenant_id   = s.tenant_id
            AND t.action_name = s.action_name
            AND t.framework   = s.framework
            WHEN MATCHED THEN UPDATE SET
                category    = s.category,
                score       = s.score,
                max_score   = s.max_score,
                status      = s.status,
                owner       = s.owner,
                uploaded_at = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN INSERT
                (tenant_id, action_name, category, framework,
                 score, max_score, status, owner)
                VALUES (s.tenant_id, s.action_name, s.category, s.framework,
                        s.score, s.max_score, s.status, s.owner);
        """,
            tenant_id,
            row.get("action_name"),
            row.get("category"),
            row.get("framework"),
            row.get("score"),
            row.get("max_score"),
            row.get("status"),
            row.get("owner"),
        )

        conn.commit()
        return len(df)
    finally:
        conn.close()
