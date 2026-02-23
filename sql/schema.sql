-- ============================================================
-- Compliance Advisor - Central Database Schema
-- ============================================================

-- ── Audit log (append-only — tracks all privileged operations) ────────────────
CREATE TABLE audit_log (
    id            INT           NOT NULL IDENTITY PRIMARY KEY,
    event_type    NVARCHAR(50)  NOT NULL,   -- TENANT_ONBOARDED, TENANT_DISABLED, SECRET_ROTATED, etc.
    tenant_id     NVARCHAR(36)  NULL,
    performed_by  NVARCHAR(256) NULL,       -- UPN or service identity
    details       NVARCHAR(MAX) NULL,       -- JSON blob of relevant context
    created_at    DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME()
);

-- Prevent any UPDATE or DELETE on audit_log — it is append-only
CREATE TRIGGER trg_audit_log_immutable
ON audit_log
AFTER UPDATE, DELETE
AS
BEGIN
    RAISERROR('audit_log is append-only and cannot be modified or deleted.', 16, 1);
    ROLLBACK TRANSACTION;
END;
GO

-- Tenant registry: one row per monitored M365 tenant
CREATE TABLE tenants (
    tenant_id       NVARCHAR(36)  NOT NULL PRIMARY KEY,
    display_name    NVARCHAR(100) NOT NULL,
    region          NVARCHAR(50)  NULL,
    department      NVARCHAR(100) NULL,       -- Agency / Department / Business Unit
    department_head NVARCHAR(200) NULL,       -- Name of the department/agency head
    risk_tier       NVARCHAR(20)  NULL,       -- Critical, High, Medium, Low
    app_id          NVARCHAR(36)  NOT NULL,
    kv_secret_name  NVARCHAR(100) NOT NULL,   -- Key Vault secret name for client_secret
    is_active       BIT           NOT NULL DEFAULT 1,
    onboarded_at    DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    last_synced_at  DATETIME2     NULL
);

-- Daily Secure Score snapshots (90 days retained by Graph API)
CREATE TABLE secure_scores (
    id              INT           NOT NULL IDENTITY PRIMARY KEY,
    tenant_id       NVARCHAR(36)  NOT NULL REFERENCES tenants(tenant_id),
    snapshot_date   DATE          NOT NULL,
    current_score   FLOAT         NOT NULL,
    max_score       FLOAT         NOT NULL,
    licensed_users  INT           NULL,
    active_users    INT           NULL,
    enabled_services NVARCHAR(MAX) NULL,       -- JSON array
    raw_json        NVARCHAR(MAX) NULL,
    created_at      DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_secure_scores UNIQUE (tenant_id, snapshot_date)
);

-- Per-control score breakdown from each snapshot
CREATE TABLE control_scores (
    id                  INT           NOT NULL IDENTITY PRIMARY KEY,
    tenant_id           NVARCHAR(36)  NOT NULL REFERENCES tenants(tenant_id),
    snapshot_date       DATE          NOT NULL,
    control_name        NVARCHAR(100) NOT NULL,
    control_category    NVARCHAR(50)  NULL,     -- Identity, Data, Device, Apps, Infrastructure
    score               FLOAT         NOT NULL,
    max_score           FLOAT         NOT NULL,
    description         NVARCHAR(MAX) NULL,
    CONSTRAINT uq_control_scores UNIQUE (tenant_id, snapshot_date, control_name)
);

-- Secure Score control profiles (catalog — refreshed weekly)
CREATE TABLE control_profiles (
    id                  INT           NOT NULL IDENTITY PRIMARY KEY,
    tenant_id           NVARCHAR(36)  NOT NULL REFERENCES tenants(tenant_id),
    control_name        NVARCHAR(100) NOT NULL,
    title               NVARCHAR(200) NULL,
    control_category    NVARCHAR(50)  NULL,
    max_score           FLOAT         NULL,
    rank                INT           NULL,
    action_type         NVARCHAR(50)  NULL,     -- Config, Review, Behavior
    service             NVARCHAR(50)  NULL,
    tier                NVARCHAR(50)  NULL,
    deprecated          BIT           NOT NULL DEFAULT 0,
    control_state       NVARCHAR(50)  NULL,     -- Default, Ignored, ThirdParty, Reviewed
    assigned_to         NVARCHAR(200) NULL,
    remediation_url     NVARCHAR(500) NULL,
    updated_at          DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_control_profiles UNIQUE (tenant_id, control_name)
);

-- Compliance Manager improvement actions (loaded from Excel export)
CREATE TABLE cm_actions (
    id              INT           NOT NULL IDENTITY PRIMARY KEY,
    tenant_id       NVARCHAR(36)  NOT NULL REFERENCES tenants(tenant_id),
    action_name     NVARCHAR(300) NOT NULL,
    category        NVARCHAR(100) NULL,
    framework       NVARCHAR(100) NULL,
    score           FLOAT         NULL,
    max_score       FLOAT         NULL,
    status          NVARCHAR(50)  NULL,
    owner           NVARCHAR(200) NULL,
    notes           NVARCHAR(MAX) NULL,
    uploaded_at     DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_cm_actions UNIQUE (tenant_id, action_name, framework)
);

-- Comparative benchmarks per snapshot
CREATE TABLE benchmark_scores (
    id              INT           NOT NULL IDENTITY PRIMARY KEY,
    tenant_id       NVARCHAR(36)  NOT NULL REFERENCES tenants(tenant_id),
    snapshot_date   DATE          NOT NULL,
    basis           NVARCHAR(50)  NOT NULL,    -- AllTenants, TotalSeats, IndustryTypes
    basis_value     NVARCHAR(100) NULL,        -- e.g. seat range or industry name
    average_score   FLOAT         NOT NULL,
    CONSTRAINT uq_benchmark_scores UNIQUE (tenant_id, snapshot_date, basis, basis_value)
);

-- ============================================================
-- Compliance Manager — Assessments & Compliance Score
-- ============================================================

-- Daily Compliance Score snapshots (pulled from Graph API)
CREATE TABLE compliance_scores (
    id              INT           NOT NULL IDENTITY PRIMARY KEY,
    tenant_id       NVARCHAR(36)  NOT NULL REFERENCES tenants(tenant_id),
    snapshot_date   DATE          NOT NULL,
    current_score   FLOAT         NOT NULL,     -- points achieved
    max_score       FLOAT         NOT NULL,     -- total points possible
    category        NVARCHAR(100) NULL,          -- overall, Data Protection, Governance, etc.
    created_at      DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_compliance_scores UNIQUE (tenant_id, snapshot_date, category)
);

-- Compliance Manager assessments
CREATE TABLE assessments (
    id              INT           NOT NULL IDENTITY PRIMARY KEY,
    tenant_id       NVARCHAR(36)  NOT NULL REFERENCES tenants(tenant_id),
    assessment_id   NVARCHAR(100) NOT NULL,     -- Graph API id
    display_name    NVARCHAR(300) NOT NULL,
    description     NVARCHAR(MAX) NULL,
    status          NVARCHAR(50)  NULL,          -- active, expired, draft
    regulation      NVARCHAR(200) NULL,          -- e.g. "NIST 800-53 Rev 5", "ISO 27001"
    compliance_score FLOAT        NULL,          -- assessment-level score percentage
    passed_controls INT           NULL,
    failed_controls INT           NULL,
    total_controls  INT           NULL,
    created_date    DATETIME2     NULL,
    last_modified   DATETIME2     NULL,
    synced_at       DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_assessments UNIQUE (tenant_id, assessment_id)
);

-- Individual improvement actions within an assessment
CREATE TABLE assessment_controls (
    id                    INT           NOT NULL IDENTITY PRIMARY KEY,
    tenant_id             NVARCHAR(36)  NOT NULL REFERENCES tenants(tenant_id),
    assessment_id         NVARCHAR(100) NOT NULL,
    control_id            NVARCHAR(100) NOT NULL,     -- Graph API control id
    control_name          NVARCHAR(300) NOT NULL,
    control_family        NVARCHAR(200) NULL,          -- e.g. "Access Control", "Audit & Accountability"
    control_category      NVARCHAR(100) NULL,
    implementation_status NVARCHAR(50)  NULL,          -- implemented, notImplemented, alternative, planned
    test_status           NVARCHAR(50)  NULL,           -- passed, failed, notAssessed, inProgress
    score                 FLOAT         NULL,
    max_score             FLOAT         NULL,
    score_impact          NVARCHAR(20)  NULL,           -- high, medium, low — how much this affects compliance score
    owner                 NVARCHAR(200) NULL,
    action_url            NVARCHAR(500) NULL,           -- direct link to Compliance Manager remediation
    -- Solution / remediation fields from Compliance Manager
    implementation_details NVARCHAR(MAX) NULL,          -- what to do: step-by-step technical remediation
    test_plan             NVARCHAR(MAX) NULL,           -- how to test: validation steps / evidence needed
    management_response   NVARCHAR(MAX) NULL,           -- risk acceptance or compensating control notes
    evidence_of_completion NVARCHAR(MAX) NULL,          -- description of evidence uploaded when complete
    service               NVARCHAR(100) NULL,           -- M365 service: Exchange Online, SharePoint, etc.
    notes                 NVARCHAR(MAX) NULL,
    synced_at             DATETIME2     NOT NULL DEFAULT SYSUTCDATETIME(),
    CONSTRAINT uq_assessment_controls UNIQUE (tenant_id, assessment_id, control_id)
);

-- ============================================================
-- Views for the AI agent and Power BI
-- ============================================================

-- Latest score per tenant
CREATE VIEW v_latest_scores AS
SELECT
    t.tenant_id,
    t.display_name,
    t.region,
    t.department,
    t.department_head,
    t.risk_tier,
    ss.snapshot_date,
    ss.current_score,
    ss.max_score,
    CAST(ss.current_score / NULLIF(ss.max_score, 0) * 100 AS DECIMAL(5,1)) AS score_pct,
    ss.licensed_users
FROM tenants t
JOIN secure_scores ss
    ON ss.tenant_id = t.tenant_id
    AND ss.snapshot_date = (
        SELECT MAX(snapshot_date)
        FROM secure_scores
        WHERE tenant_id = t.tenant_id
    )
WHERE t.is_active = 1;

-- Top control gaps per tenant (controls with most room for improvement)
CREATE VIEW v_top_gaps AS
SELECT
    cs.tenant_id,
    t.display_name,
    cs.control_name,
    cp.title,
    cp.control_category,
    cs.snapshot_date,
    cs.score,
    cs.max_score,
    cs.max_score - cs.score AS points_gap,
    cp.rank,
    cp.action_type,
    cp.remediation_url
FROM control_scores cs
JOIN tenants t ON t.tenant_id = cs.tenant_id
LEFT JOIN control_profiles cp
    ON cp.tenant_id = cs.tenant_id
    AND cp.control_name = cs.control_name
WHERE cs.snapshot_date = (
    SELECT MAX(snapshot_date)
    FROM control_scores
    WHERE tenant_id = cs.tenant_id
)
AND (cp.deprecated IS NULL OR cp.deprecated = 0)
AND (cp.control_state IS NULL OR cp.control_state = 'Default');

-- Enterprise rollup across all tenants
CREATE VIEW v_enterprise_rollup AS
SELECT
    snapshot_date,
    COUNT(DISTINCT tenant_id)               AS tenant_count,
    AVG(score_pct)                          AS avg_score_pct,
    MIN(score_pct)                          AS min_score_pct,
    MAX(score_pct)                          AS max_score_pct,
    SUM(current_score)                      AS total_current_score,
    SUM(max_score)                          AS total_max_score
FROM v_latest_scores
GROUP BY snapshot_date;

-- ============================================================
-- Trend & Department Views — for CISO / Leadership reporting
-- ============================================================

-- Score trend per tenant over time (daily granularity)
CREATE VIEW v_score_trend AS
SELECT
    t.tenant_id,
    t.display_name,
    t.department,
    t.risk_tier,
    ss.snapshot_date,
    ss.current_score,
    ss.max_score,
    CAST(ss.current_score / NULLIF(ss.max_score, 0) * 100 AS DECIMAL(5,1)) AS score_pct
FROM tenants t
JOIN secure_scores ss ON ss.tenant_id = t.tenant_id
WHERE t.is_active = 1;

-- Week-over-week score change per tenant
CREATE VIEW v_weekly_change AS
WITH weekly AS (
    SELECT
        tenant_id,
        snapshot_date,
        current_score,
        max_score,
        CAST(current_score / NULLIF(max_score, 0) * 100 AS DECIMAL(5,1)) AS score_pct,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, DATEPART(iso_week, snapshot_date), YEAR(snapshot_date)
            ORDER BY snapshot_date DESC
        ) AS rn_week
    FROM secure_scores
),
this_week AS (
    SELECT tenant_id, snapshot_date, score_pct
    FROM weekly
    WHERE rn_week = 1
      AND snapshot_date >= DATEADD(DAY, -7, CAST(SYSUTCDATETIME() AS DATE))
),
last_week AS (
    SELECT tenant_id, snapshot_date, score_pct
    FROM weekly
    WHERE rn_week = 1
      AND snapshot_date >= DATEADD(DAY, -14, CAST(SYSUTCDATETIME() AS DATE))
      AND snapshot_date <  DATEADD(DAY, -7,  CAST(SYSUTCDATETIME() AS DATE))
)
SELECT
    t.tenant_id,
    t.display_name,
    t.department,
    t.risk_tier,
    tw.score_pct        AS current_pct,
    lw.score_pct        AS prior_pct,
    tw.score_pct - ISNULL(lw.score_pct, tw.score_pct) AS wow_change,
    CASE
        WHEN tw.score_pct - ISNULL(lw.score_pct, tw.score_pct) > 0 THEN 'Improving'
        WHEN tw.score_pct - ISNULL(lw.score_pct, tw.score_pct) < 0 THEN 'Declining'
        ELSE 'Stable'
    END AS trend_direction
FROM tenants t
LEFT JOIN this_week tw ON tw.tenant_id = t.tenant_id
LEFT JOIN last_week lw ON lw.tenant_id = t.tenant_id
WHERE t.is_active = 1;

-- Department / Agency rollup — aggregates all tenants in each department
CREATE VIEW v_department_rollup AS
SELECT
    t.department,
    COUNT(DISTINCT t.tenant_id)                   AS tenant_count,
    AVG(ls.score_pct)                             AS avg_score_pct,
    MIN(ls.score_pct)                             AS min_score_pct,
    MAX(ls.score_pct)                             AS max_score_pct,
    MIN(t.display_name)                           AS weakest_tenant,
    ls.snapshot_date
FROM tenants t
JOIN v_latest_scores ls ON ls.tenant_id = t.tenant_id
WHERE t.is_active = 1
  AND t.department IS NOT NULL
GROUP BY t.department, ls.snapshot_date;

-- Category-level trend — how each security domain is tracking over time
CREATE VIEW v_category_trend AS
SELECT
    t.department,
    cs.control_category,
    cs.snapshot_date,
    AVG(cs.score)                              AS avg_score,
    AVG(cs.max_score)                          AS avg_max_score,
    AVG(cs.max_score - cs.score)               AS avg_gap,
    COUNT(DISTINCT cs.tenant_id)               AS tenant_count
FROM control_scores cs
JOIN tenants t ON t.tenant_id = cs.tenant_id
WHERE t.is_active = 1
  AND cs.control_category IS NOT NULL
GROUP BY t.department, cs.control_category, cs.snapshot_date;

-- Risk-tiered summary — for "Critical systems" executive view
CREATE VIEW v_risk_tier_summary AS
SELECT
    t.risk_tier,
    COUNT(DISTINCT t.tenant_id)     AS tenant_count,
    AVG(ls.score_pct)               AS avg_score_pct,
    MIN(ls.score_pct)               AS min_score_pct,
    MAX(ls.score_pct)               AS max_score_pct
FROM tenants t
JOIN v_latest_scores ls ON ls.tenant_id = t.tenant_id
WHERE t.is_active = 1
  AND t.risk_tier IS NOT NULL
GROUP BY t.risk_tier;

-- ============================================================
-- Row-Level Security — tenant data isolation
-- ============================================================
-- The Function App sets SESSION_CONTEXT(N'tenant_id') before every query.
-- Set SESSION_CONTEXT(N'is_admin') = 1 for cross-tenant orchestrator queries.

CREATE FUNCTION dbo.fn_tenant_rls_predicate(@tenant_id AS NVARCHAR(36))
RETURNS TABLE
WITH SCHEMABINDING
AS
RETURN
    SELECT 1 AS result
    WHERE
        -- Admin context: orchestrator / reindex jobs (bypasses tenant filter)
        CAST(SESSION_CONTEXT(N'is_admin') AS BIT) = 1
        OR
        -- Tenant-scoped context: matches calling session's tenant
        @tenant_id = CAST(SESSION_CONTEXT(N'tenant_id') AS NVARCHAR(36));
GO

-- Apply filter predicate to all tenant-partitioned tables
CREATE SECURITY POLICY rls_tenant_isolation
    ADD FILTER PREDICATE dbo.fn_tenant_rls_predicate(tenant_id) ON dbo.secure_scores,
    ADD FILTER PREDICATE dbo.fn_tenant_rls_predicate(tenant_id) ON dbo.control_scores,
    ADD FILTER PREDICATE dbo.fn_tenant_rls_predicate(tenant_id) ON dbo.control_profiles,
    ADD FILTER PREDICATE dbo.fn_tenant_rls_predicate(tenant_id) ON dbo.cm_actions,
    ADD FILTER PREDICATE dbo.fn_tenant_rls_predicate(tenant_id) ON dbo.benchmark_scores,
    ADD FILTER PREDICATE dbo.fn_tenant_rls_predicate(tenant_id) ON dbo.compliance_scores,
    ADD FILTER PREDICATE dbo.fn_tenant_rls_predicate(tenant_id) ON dbo.assessments,
    ADD FILTER PREDICATE dbo.fn_tenant_rls_predicate(tenant_id) ON dbo.assessment_controls
WITH (STATE = ON, SCHEMABINDING = ON);
GO

-- ============================================================
-- Compliance Manager Views
-- ============================================================

-- Latest compliance score per tenant (overall category)
CREATE VIEW v_latest_compliance_scores AS
SELECT
    t.tenant_id,
    t.display_name,
    t.department,
    t.department_head,
    t.risk_tier,
    cs.snapshot_date,
    cs.current_score,
    cs.max_score,
    CAST(cs.current_score / NULLIF(cs.max_score, 0) * 100 AS DECIMAL(5,1)) AS compliance_pct,
    cs.category
FROM tenants t
JOIN compliance_scores cs
    ON cs.tenant_id = t.tenant_id
    AND cs.category = 'overall'
    AND cs.snapshot_date = (
        SELECT MAX(snapshot_date)
        FROM compliance_scores
        WHERE tenant_id = t.tenant_id AND category = 'overall'
    )
WHERE t.is_active = 1;

-- Compliance score trend over time
CREATE VIEW v_compliance_trend AS
SELECT
    t.tenant_id,
    t.display_name,
    t.department,
    t.risk_tier,
    cs.snapshot_date,
    cs.current_score,
    cs.max_score,
    CAST(cs.current_score / NULLIF(cs.max_score, 0) * 100 AS DECIMAL(5,1)) AS compliance_pct,
    cs.category
FROM tenants t
JOIN compliance_scores cs ON cs.tenant_id = t.tenant_id
WHERE t.is_active = 1;

-- Week-over-week compliance score change
CREATE VIEW v_compliance_weekly_change AS
WITH weekly AS (
    SELECT
        tenant_id,
        snapshot_date,
        current_score,
        max_score,
        CAST(current_score / NULLIF(max_score, 0) * 100 AS DECIMAL(5,1)) AS compliance_pct,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, DATEPART(iso_week, snapshot_date), YEAR(snapshot_date)
            ORDER BY snapshot_date DESC
        ) AS rn_week
    FROM compliance_scores
    WHERE category = 'overall'
),
this_week AS (
    SELECT tenant_id, snapshot_date, compliance_pct
    FROM weekly
    WHERE rn_week = 1
      AND snapshot_date >= DATEADD(DAY, -7, CAST(SYSUTCDATETIME() AS DATE))
),
last_week AS (
    SELECT tenant_id, snapshot_date, compliance_pct
    FROM weekly
    WHERE rn_week = 1
      AND snapshot_date >= DATEADD(DAY, -14, CAST(SYSUTCDATETIME() AS DATE))
      AND snapshot_date <  DATEADD(DAY, -7,  CAST(SYSUTCDATETIME() AS DATE))
)
SELECT
    t.tenant_id,
    t.display_name,
    t.department,
    t.risk_tier,
    tw.compliance_pct   AS current_pct,
    lw.compliance_pct   AS prior_pct,
    tw.compliance_pct - ISNULL(lw.compliance_pct, tw.compliance_pct) AS wow_change,
    CASE
        WHEN tw.compliance_pct - ISNULL(lw.compliance_pct, tw.compliance_pct) > 0 THEN 'Improving'
        WHEN tw.compliance_pct - ISNULL(lw.compliance_pct, tw.compliance_pct) < 0 THEN 'Declining'
        ELSE 'Stable'
    END AS trend_direction
FROM tenants t
LEFT JOIN this_week tw ON tw.tenant_id = t.tenant_id
LEFT JOIN last_week lw ON lw.tenant_id = t.tenant_id
WHERE t.is_active = 1;

-- Assessment summary — one row per assessment per tenant
CREATE VIEW v_assessment_summary AS
SELECT
    a.tenant_id,
    t.display_name,
    t.department,
    a.assessment_id,
    a.display_name AS assessment_name,
    a.regulation,
    a.status,
    a.compliance_score,
    a.passed_controls,
    a.failed_controls,
    a.total_controls,
    CAST(a.passed_controls * 100.0 / NULLIF(a.total_controls, 0) AS DECIMAL(5,1)) AS pass_rate,
    a.last_modified
FROM assessments a
JOIN tenants t ON t.tenant_id = a.tenant_id
WHERE t.is_active = 1 AND a.status = 'active';

-- Assessment control gaps — controls not yet implemented or failing tests
-- Includes solution/remediation details to show HOW to fix each gap
CREATE VIEW v_assessment_gaps AS
SELECT
    ac.tenant_id,
    t.display_name,
    t.department,
    a.display_name AS assessment_name,
    a.regulation,
    ac.control_name,
    ac.control_family,
    ac.control_category,
    ac.implementation_status,
    ac.test_status,
    ac.score,
    ac.max_score,
    ac.max_score - ISNULL(ac.score, 0) AS points_gap,
    ac.score_impact,
    ac.owner,
    ac.action_url,
    ac.implementation_details,
    ac.test_plan,
    ac.management_response,
    ac.service
FROM assessment_controls ac
JOIN assessments a ON a.tenant_id = ac.tenant_id AND a.assessment_id = ac.assessment_id
JOIN tenants t ON t.tenant_id = ac.tenant_id
WHERE t.is_active = 1
  AND (ac.implementation_status IN ('notImplemented', 'alternative', 'planned')
       OR ac.test_status IN ('failed', 'notAssessed'));

-- Top improvement actions — ranked by score impact, showing the solution
CREATE VIEW v_improvement_actions AS
SELECT
    ac.tenant_id,
    t.display_name,
    t.department,
    a.display_name AS assessment_name,
    a.regulation,
    ac.control_name,
    ac.control_family,
    ac.implementation_status,
    ac.test_status,
    ac.score,
    ac.max_score,
    ac.max_score - ISNULL(ac.score, 0) AS points_gap,
    ac.score_impact,
    ac.owner,
    ac.action_url,
    ac.implementation_details,
    ac.test_plan,
    ac.service,
    CASE
        WHEN ac.implementation_status = 'notImplemented' AND ac.score_impact = 'high' THEN 1
        WHEN ac.implementation_status = 'notImplemented' THEN 2
        WHEN ac.implementation_status = 'planned' THEN 3
        WHEN ac.implementation_status = 'alternative' THEN 4
        ELSE 5
    END AS priority_rank
FROM assessment_controls ac
JOIN assessments a ON a.tenant_id = ac.tenant_id AND a.assessment_id = ac.assessment_id
JOIN tenants t ON t.tenant_id = ac.tenant_id
WHERE t.is_active = 1
  AND a.status = 'active'
  AND ac.implementation_status != 'implemented';

-- Department compliance rollup
CREATE VIEW v_compliance_department_rollup AS
SELECT
    t.department,
    COUNT(DISTINCT t.tenant_id)             AS tenant_count,
    AVG(lcs.compliance_pct)                 AS avg_compliance_pct,
    MIN(lcs.compliance_pct)                 AS min_compliance_pct,
    MAX(lcs.compliance_pct)                 AS max_compliance_pct,
    COUNT(DISTINCT a.assessment_id)         AS total_assessments,
    SUM(a.failed_controls)                  AS total_failed_controls
FROM tenants t
LEFT JOIN v_latest_compliance_scores lcs ON lcs.tenant_id = t.tenant_id
LEFT JOIN assessments a ON a.tenant_id = t.tenant_id AND a.status = 'active'
WHERE t.is_active = 1
  AND t.department IS NOT NULL
GROUP BY t.department;

-- Regulation coverage — how many tenants have assessments per regulation
CREATE VIEW v_regulation_coverage AS
SELECT
    a.regulation,
    COUNT(DISTINCT a.tenant_id)   AS tenant_count,
    COUNT(DISTINCT a.assessment_id) AS assessment_count,
    AVG(a.compliance_score)       AS avg_compliance_score,
    SUM(a.passed_controls)        AS total_passed,
    SUM(a.failed_controls)        AS total_failed,
    SUM(a.total_controls)         AS total_controls,
    CAST(SUM(a.passed_controls) * 100.0 / NULLIF(SUM(a.total_controls), 0) AS DECIMAL(5,1)) AS overall_pass_rate
FROM assessments a
JOIN tenants t ON t.tenant_id = a.tenant_id
WHERE t.is_active = 1 AND a.status = 'active'
GROUP BY a.regulation;

-- Category compliance trend — how each control family is tracking
CREATE VIEW v_compliance_category_trend AS
SELECT
    t.department,
    ac.control_family,
    a.regulation,
    COUNT(*) AS total_controls,
    SUM(CASE WHEN ac.implementation_status = 'implemented' THEN 1 ELSE 0 END) AS implemented,
    SUM(CASE WHEN ac.test_status = 'passed' THEN 1 ELSE 0 END) AS passed,
    SUM(CASE WHEN ac.test_status = 'failed' THEN 1 ELSE 0 END) AS failed,
    AVG(ac.max_score - ISNULL(ac.score, 0)) AS avg_gap
FROM assessment_controls ac
JOIN assessments a ON a.tenant_id = ac.tenant_id AND a.assessment_id = ac.assessment_id
JOIN tenants t ON t.tenant_id = ac.tenant_id
WHERE t.is_active = 1 AND a.status = 'active'
GROUP BY t.department, ac.control_family, a.regulation;
