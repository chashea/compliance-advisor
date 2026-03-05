"""
SQLite helpers — connection factory and upsert utilities.
Replaces the original Azure SQL / pyodbc implementation.
"""

from __future__ import annotations

import json
import os
import sqlite3


def get_connection() -> sqlite3.Connection:
    db_path = os.environ.get("SQLITE_DB_PATH", "data/compliance.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def set_tenant_context(conn: sqlite3.Connection, tenant_id: str) -> None:
    """No-op: SQLite has no RLS; single-tenant by design."""


def set_admin_context(conn: sqlite3.Connection) -> None:
    """No-op: SQLite has no RLS."""


def get_active_tenants(conn: sqlite3.Connection) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tenant_id, display_name, region, department,
               department_head, risk_tier, app_id, kv_secret_name
        FROM tenants
        WHERE is_active = 1
    """
    )
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def upsert_secure_score(conn: sqlite3.Connection, tenant_id: str, score: dict) -> None:
    snapshot_date = score["createdDateTime"][:10]
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO secure_scores
            (tenant_id, snapshot_date, current_score, max_score,
             licensed_users, active_users, raw_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            tenant_id,
            snapshot_date,
            score.get("currentScore"),
            score.get("maxScore"),
            score.get("licensedUserCount"),
            score.get("activeUserCount"),
            json.dumps(score),
        ),
    )
    conn.commit()


def upsert_control_scores(conn: sqlite3.Connection, tenant_id: str, snapshot_date: str, controls: list[dict]) -> None:
    cursor = conn.cursor()
    for ctrl in controls:
        cursor.execute(
            """
            INSERT OR REPLACE INTO control_scores
                (tenant_id, snapshot_date, control_name, control_category,
                 score, max_score, description)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (
                tenant_id,
                snapshot_date,
                ctrl.get("controlName"),
                ctrl.get("controlCategory"),
                ctrl.get("score") or 0.0,
                ctrl.get("maxScore") or 0.0,
                ctrl.get("description"),
            ),
        )
    conn.commit()


def upsert_control_profiles(conn: sqlite3.Connection, tenant_id: str, profiles: list[dict]) -> None:
    cursor = conn.cursor()
    for p in profiles:
        state_updates = p.get("controlStateUpdates") or []
        latest_state = state_updates[-1].get("state") if state_updates else None
        assigned_to = state_updates[-1].get("assignedTo") if state_updates else None

        cursor.execute(
            """
            INSERT OR REPLACE INTO control_profiles
                (tenant_id, control_name, title, control_category, max_score, rank,
                 action_type, service, tier, deprecated, control_state,
                 assigned_to, remediation_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                tenant_id,
                p.get("id"),
                p.get("title"),
                p.get("controlCategory"),
                p.get("maxScore"),
                p.get("rank"),
                p.get("actionType"),
                p.get("service"),
                p.get("tier"),
                1 if p.get("deprecated") else 0,
                latest_state,
                assigned_to,
                p.get("remediationImpact"),
            ),
        )
    conn.commit()


def upsert_benchmarks(conn: sqlite3.Connection, tenant_id: str, snapshot_date: str, benchmarks: list[dict]) -> None:
    cursor = conn.cursor()
    for b in benchmarks:
        cursor.execute(
            """
            INSERT OR REPLACE INTO benchmark_scores
                (tenant_id, snapshot_date, basis, basis_value, average_score)
            VALUES (?, ?, ?, ?, ?)
        """,
            (
                tenant_id,
                snapshot_date,
                b.get("basis"),
                b.get("basisValue"),
                b.get("averageScore"),
            ),
        )
    conn.commit()


def mark_tenant_synced(conn: sqlite3.Connection, tenant_id: str) -> None:
    conn.cursor().execute("UPDATE tenants SET last_synced_at = datetime('now') WHERE tenant_id = ?", (tenant_id,))
    conn.commit()


# ── Compliance Manager upserts ────────────────────────────────────────────────


def upsert_compliance_score(
    conn: sqlite3.Connection,
    tenant_id: str,
    snapshot_date: str,
    current_score: float,
    max_score: float,
    category: str = "overall",
) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO compliance_scores
            (tenant_id, snapshot_date, current_score, max_score, category)
        VALUES (?, ?, ?, ?, ?)
    """,
        (tenant_id, snapshot_date, current_score, max_score, category),
    )
    conn.commit()


def upsert_assessment(
    conn: sqlite3.Connection,
    tenant_id: str,
    assessment: dict,
) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO assessments
            (tenant_id, assessment_id, display_name, description, status,
             regulation, compliance_score, passed_controls, failed_controls,
             total_controls, created_date, last_modified)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            tenant_id,
            assessment.get("id"),
            assessment.get("displayName", ""),
            assessment.get("description"),
            assessment.get("status"),
            _extract_regulation(assessment),
            assessment.get("complianceScore"),
            assessment.get("passedControls"),
            assessment.get("failedControls"),
            assessment.get("totalControls"),
            assessment.get("createdDateTime"),
            assessment.get("lastModifiedDateTime"),
        ),
    )
    conn.commit()


def upsert_assessment_control(
    conn: sqlite3.Connection,
    tenant_id: str,
    assessment_id: str,
    control: dict,
) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO assessment_controls
            (tenant_id, assessment_id, control_id, control_name,
             control_family, control_category, implementation_status,
             test_status, score, max_score, score_impact, owner, action_url,
             implementation_details, test_plan, management_response,
             evidence_of_completion, service)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            tenant_id,
            assessment_id,
            control.get("id"),
            control.get("displayName", control.get("controlName", "")),
            control.get("controlFamily"),
            control.get("controlCategory"),
            control.get("implementationStatus"),
            control.get("testStatus"),
            control.get("score"),
            control.get("maxScore"),
            control.get("scoreImpact"),
            control.get("owner"),
            control.get("actionUrl"),
            control.get("implementationDetails"),
            control.get("testPlan"),
            control.get("managementResponse"),
            control.get("evidenceOfCompletion"),
            control.get("service"),
        ),
    )
    conn.commit()


def _extract_regulation(assessment: dict) -> str | None:
    """Best-effort extraction of the regulation name from assessment data."""
    reg = assessment.get("regulation") or assessment.get("regulationName")
    if reg:
        return reg
    standard = assessment.get("complianceStandard")
    if isinstance(standard, dict):
        return standard.get("name")
    return None
