"""
Azure SQL helpers — connection factory and upsert utilities.
"""
import json
import os
from datetime import date
import pyodbc


def get_connection() -> pyodbc.Connection:
    conn_str = os.environ["MSSQL_CONNECTION"]
    return pyodbc.connect(conn_str, autocommit=False)


def set_tenant_context(conn: pyodbc.Connection, tenant_id: str) -> None:
    """
    Set SESSION_CONTEXT so the RLS predicate allows only this tenant's rows.
    Must be called once immediately after get_connection() for all tenant-scoped writes.
    @read_only=1 prevents any subsequent code from overwriting the context.
    """
    cursor = conn.cursor()
    cursor.execute(
        "EXEC sp_set_session_context @key = N'tenant_id', @value = ?, @read_only = 1",
        tenant_id,
    )
    cursor.execute(
        "EXEC sp_set_session_context @key = N'is_admin', @value = 0, @read_only = 1"
    )


def set_admin_context(conn: pyodbc.Connection) -> None:
    """
    Set SESSION_CONTEXT for cross-tenant orchestrator operations (fan-out writes,
    reindex, weekly digest).  Bypasses the tenant_id RLS filter.
    @read_only=1 prevents any subsequent code from escalating privileges.
    """
    cursor = conn.cursor()
    cursor.execute(
        "EXEC sp_set_session_context @key = N'is_admin', @value = 1, @read_only = 1"
    )


def get_active_tenants(conn: pyodbc.Connection) -> list[dict]:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT tenant_id, display_name, region, department,
               department_head, risk_tier, app_id, kv_secret_name
        FROM tenants
        WHERE is_active = 1
    """)
    cols = [col[0] for col in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def upsert_secure_score(conn: pyodbc.Connection, tenant_id: str, score: dict) -> None:
    snapshot_date = score["createdDateTime"][:10]
    cursor = conn.cursor()
    cursor.execute("""
        MERGE secure_scores AS t
        USING (VALUES (?, ?, ?, ?, ?, ?, ?)) AS s
            (tenant_id, snapshot_date, current_score, max_score,
             licensed_users, active_users, raw_json)
        ON t.tenant_id = s.tenant_id AND t.snapshot_date = s.snapshot_date
        WHEN MATCHED THEN UPDATE SET
            current_score  = s.current_score,
            max_score      = s.max_score,
            licensed_users = s.licensed_users,
            active_users   = s.active_users,
            raw_json       = s.raw_json
        WHEN NOT MATCHED THEN INSERT
            (tenant_id, snapshot_date, current_score, max_score,
             licensed_users, active_users, raw_json)
            VALUES (s.tenant_id, s.snapshot_date, s.current_score, s.max_score,
                    s.licensed_users, s.active_users, s.raw_json);
    """,
        tenant_id, snapshot_date,
        score.get("currentScore"), score.get("maxScore"),
        score.get("licensedUserCount"), score.get("activeUserCount"),
        json.dumps(score),
    )
    conn.commit()


def upsert_control_scores(
    conn: pyodbc.Connection, tenant_id: str, snapshot_date: str, controls: list[dict]
) -> None:
    cursor = conn.cursor()
    for ctrl in controls:
        cursor.execute("""
            MERGE control_scores AS t
            USING (VALUES (?, ?, ?, ?, ?, ?, ?)) AS s
                (tenant_id, snapshot_date, control_name, control_category,
                 score, max_score, description)
            ON  t.tenant_id     = s.tenant_id
            AND t.snapshot_date = s.snapshot_date
            AND t.control_name  = s.control_name
            WHEN MATCHED THEN UPDATE SET
                score            = s.score,
                max_score        = s.max_score,
                description      = s.description
            WHEN NOT MATCHED THEN INSERT
                (tenant_id, snapshot_date, control_name, control_category,
                 score, max_score, description)
                VALUES (s.tenant_id, s.snapshot_date, s.control_name,
                        s.control_category, s.score, s.max_score, s.description);
        """,
            tenant_id, snapshot_date,
            ctrl.get("controlName"), ctrl.get("controlCategory"),
            ctrl.get("score"), ctrl.get("maxScore"),
            ctrl.get("description"),
        )
    conn.commit()


def upsert_control_profiles(
    conn: pyodbc.Connection, tenant_id: str, profiles: list[dict]
) -> None:
    cursor = conn.cursor()
    for p in profiles:
        state_updates = p.get("controlStateUpdates") or []
        latest_state = state_updates[-1].get("state") if state_updates else None
        assigned_to  = state_updates[-1].get("assignedTo") if state_updates else None

        cursor.execute("""
            MERGE control_profiles AS t
            USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)) AS s
                (tenant_id, control_name, title, control_category, max_score, rank,
                 action_type, service, tier, deprecated, control_state,
                 assigned_to, remediation_url)
            ON t.tenant_id = s.tenant_id AND t.control_name = s.control_name
            WHEN MATCHED THEN UPDATE SET
                title           = s.title,
                control_category= s.control_category,
                max_score       = s.max_score,
                rank            = s.rank,
                action_type     = s.action_type,
                service         = s.service,
                tier            = s.tier,
                deprecated      = s.deprecated,
                control_state   = s.control_state,
                assigned_to     = s.assigned_to,
                remediation_url = s.remediation_url,
                updated_at      = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN INSERT
                (tenant_id, control_name, title, control_category, max_score, rank,
                 action_type, service, tier, deprecated, control_state,
                 assigned_to, remediation_url)
                VALUES (s.tenant_id, s.control_name, s.title, s.control_category,
                        s.max_score, s.rank, s.action_type, s.service, s.tier,
                        s.deprecated, s.control_state, s.assigned_to, s.remediation_url);
        """,
            tenant_id, p.get("id"), p.get("title"), p.get("controlCategory"),
            p.get("maxScore"), p.get("rank"), p.get("actionType"),
            p.get("service"), p.get("tier"),
            1 if p.get("deprecated") else 0,
            latest_state, assigned_to,
            p.get("remediationImpact"),
        )
    conn.commit()


def upsert_benchmarks(
    conn: pyodbc.Connection, tenant_id: str, snapshot_date: str,
    benchmarks: list[dict]
) -> None:
    cursor = conn.cursor()
    for b in benchmarks:
        cursor.execute("""
            MERGE benchmark_scores AS t
            USING (VALUES (?, ?, ?, ?, ?)) AS s
                (tenant_id, snapshot_date, basis, basis_value, average_score)
            ON  t.tenant_id     = s.tenant_id
            AND t.snapshot_date = s.snapshot_date
            AND t.basis         = s.basis
            AND t.basis_value   = s.basis_value
            WHEN MATCHED THEN UPDATE SET average_score = s.average_score
            WHEN NOT MATCHED THEN INSERT
                (tenant_id, snapshot_date, basis, basis_value, average_score)
                VALUES (s.tenant_id, s.snapshot_date, s.basis,
                        s.basis_value, s.average_score);
        """,
            tenant_id, snapshot_date,
            b.get("basis"), b.get("basisValue"), b.get("averageScore"),
        )
    conn.commit()


def mark_tenant_synced(conn: pyodbc.Connection, tenant_id: str) -> None:
    conn.cursor().execute(
        "UPDATE tenants SET last_synced_at = SYSUTCDATETIME() WHERE tenant_id = ?",
        tenant_id
    )
    conn.commit()


# ── Compliance Manager upserts ────────────────────────────────────────────────

def upsert_compliance_score(
    conn: pyodbc.Connection, tenant_id: str, snapshot_date: str,
    current_score: float, max_score: float, category: str = "overall",
) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        MERGE compliance_scores AS t
        USING (VALUES (?, ?, ?, ?, ?)) AS s
            (tenant_id, snapshot_date, current_score, max_score, category)
        ON  t.tenant_id     = s.tenant_id
        AND t.snapshot_date  = s.snapshot_date
        AND t.category       = s.category
        WHEN MATCHED THEN UPDATE SET
            current_score = s.current_score,
            max_score     = s.max_score
        WHEN NOT MATCHED THEN INSERT
            (tenant_id, snapshot_date, current_score, max_score, category)
            VALUES (s.tenant_id, s.snapshot_date, s.current_score,
                    s.max_score, s.category);
    """, tenant_id, snapshot_date, current_score, max_score, category)
    conn.commit()


def upsert_assessment(
    conn: pyodbc.Connection, tenant_id: str, assessment: dict,
) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        MERGE assessments AS t
        USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)) AS s
            (tenant_id, assessment_id, display_name, description, status,
             regulation, compliance_score, passed_controls, failed_controls,
             total_controls, created_date, last_modified)
        ON t.tenant_id = s.tenant_id AND t.assessment_id = s.assessment_id
        WHEN MATCHED THEN UPDATE SET
            display_name     = s.display_name,
            description      = s.description,
            status           = s.status,
            regulation       = s.regulation,
            compliance_score = s.compliance_score,
            passed_controls  = s.passed_controls,
            failed_controls  = s.failed_controls,
            total_controls   = s.total_controls,
            last_modified    = s.last_modified,
            synced_at        = SYSUTCDATETIME()
        WHEN NOT MATCHED THEN INSERT
            (tenant_id, assessment_id, display_name, description, status,
             regulation, compliance_score, passed_controls, failed_controls,
             total_controls, created_date, last_modified)
            VALUES (s.tenant_id, s.assessment_id, s.display_name, s.description,
                    s.status, s.regulation, s.compliance_score, s.passed_controls,
                    s.failed_controls, s.total_controls, s.created_date,
                    s.last_modified);
    """,
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
    )
    conn.commit()


def upsert_assessment_control(
    conn: pyodbc.Connection, tenant_id: str, assessment_id: str, control: dict,
) -> None:
    cursor = conn.cursor()
    cursor.execute("""
        MERGE assessment_controls AS t
        USING (VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)) AS s
            (tenant_id, assessment_id, control_id, control_name,
             control_family, control_category, implementation_status,
             test_status, score, max_score, score_impact, owner, action_url,
             implementation_details, test_plan, management_response,
             evidence_of_completion, service)
        ON  t.tenant_id     = s.tenant_id
        AND t.assessment_id = s.assessment_id
        AND t.control_id    = s.control_id
        WHEN MATCHED THEN UPDATE SET
            control_name            = s.control_name,
            control_family          = s.control_family,
            control_category        = s.control_category,
            implementation_status   = s.implementation_status,
            test_status             = s.test_status,
            score                   = s.score,
            max_score               = s.max_score,
            score_impact            = s.score_impact,
            owner                   = s.owner,
            action_url              = s.action_url,
            implementation_details  = s.implementation_details,
            test_plan               = s.test_plan,
            management_response     = s.management_response,
            evidence_of_completion  = s.evidence_of_completion,
            service                 = s.service,
            synced_at               = SYSUTCDATETIME()
        WHEN NOT MATCHED THEN INSERT
            (tenant_id, assessment_id, control_id, control_name,
             control_family, control_category, implementation_status,
             test_status, score, max_score, score_impact, owner, action_url,
             implementation_details, test_plan, management_response,
             evidence_of_completion, service)
            VALUES (s.tenant_id, s.assessment_id, s.control_id, s.control_name,
                    s.control_family, s.control_category, s.implementation_status,
                    s.test_status, s.score, s.max_score, s.score_impact,
                    s.owner, s.action_url,
                    s.implementation_details, s.test_plan, s.management_response,
                    s.evidence_of_completion, s.service);
    """,
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
    )
    conn.commit()


def _extract_regulation(assessment: dict) -> str | None:
    """Best-effort extraction of the regulation name from assessment data."""
    reg = assessment.get("regulation") or assessment.get("regulationName")
    if reg:
        return reg
    # Some responses nest it under complianceStandard
    standard = assessment.get("complianceStandard")
    if isinstance(standard, dict):
        return standard.get("name")
    return None
