-- ============================================================
-- Compliance Advisor - SQLite Database Schema
-- SQLite translation of sql/schema.sql (no RLS, no IDENTITY triggers)
-- Requires SQLite 3.25+ for window functions used in weekly-change views.
-- ============================================================

-- ── Audit log (append-only) ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS audit_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type    TEXT    NOT NULL,
    tenant_id     TEXT    NULL,
    performed_by  TEXT    NULL,
    details       TEXT    NULL,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Tenant registry: one row per monitored M365 tenant
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id       TEXT    NOT NULL PRIMARY KEY,
    display_name    TEXT    NOT NULL,
    region          TEXT    NULL,
    department      TEXT    NULL,
    department_head TEXT    NULL,
    risk_tier       TEXT    NULL,
    app_id          TEXT    NOT NULL,
    kv_secret_name  TEXT    NULL DEFAULT '',
    is_active       INTEGER NOT NULL DEFAULT 1,
    onboarded_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    last_synced_at  TEXT    NULL
);

-- Daily Secure Score snapshots
CREATE TABLE IF NOT EXISTS secure_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id       TEXT    NOT NULL REFERENCES tenants(tenant_id),
    snapshot_date   TEXT    NOT NULL,
    current_score   REAL    NOT NULL,
    max_score       REAL    NOT NULL,
    licensed_users  INTEGER NULL,
    active_users    INTEGER NULL,
    enabled_services TEXT   NULL,
    raw_json        TEXT    NULL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    CONSTRAINT uq_secure_scores UNIQUE (tenant_id, snapshot_date)
);

-- Per-control score breakdown from each snapshot
CREATE TABLE IF NOT EXISTS control_scores (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id           TEXT    NOT NULL REFERENCES tenants(tenant_id),
    snapshot_date       TEXT    NOT NULL,
    control_name        TEXT    NOT NULL,
    control_category    TEXT    NULL,
    score               REAL    NOT NULL,
    max_score           REAL    NOT NULL,
    description         TEXT    NULL,
    CONSTRAINT uq_control_scores UNIQUE (tenant_id, snapshot_date, control_name)
);

-- Secure Score control profiles (catalog)
CREATE TABLE IF NOT EXISTS control_profiles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id           TEXT    NOT NULL REFERENCES tenants(tenant_id),
    control_name        TEXT    NOT NULL,
    title               TEXT    NULL,
    control_category    TEXT    NULL,
    max_score           REAL    NULL,
    rank                INTEGER NULL,
    action_type         TEXT    NULL,
    service             TEXT    NULL,
    tier                TEXT    NULL,
    deprecated          INTEGER NOT NULL DEFAULT 0,
    control_state       TEXT    NULL,
    assigned_to         TEXT    NULL,
    remediation_url     TEXT    NULL,
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    CONSTRAINT uq_control_profiles UNIQUE (tenant_id, control_name)
);

-- Compliance Manager improvement actions
CREATE TABLE IF NOT EXISTS cm_actions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id       TEXT    NOT NULL REFERENCES tenants(tenant_id),
    action_name     TEXT    NOT NULL,
    category        TEXT    NULL,
    framework       TEXT    NULL,
    score           REAL    NULL,
    max_score       REAL    NULL,
    status          TEXT    NULL,
    owner           TEXT    NULL,
    notes           TEXT    NULL,
    uploaded_at     TEXT    NOT NULL DEFAULT (datetime('now')),
    CONSTRAINT uq_cm_actions UNIQUE (tenant_id, action_name, framework)
);

-- Comparative benchmarks per snapshot
CREATE TABLE IF NOT EXISTS benchmark_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id       TEXT    NOT NULL REFERENCES tenants(tenant_id),
    snapshot_date   TEXT    NOT NULL,
    basis           TEXT    NOT NULL,
    basis_value     TEXT    NULL,
    average_score   REAL    NOT NULL,
    CONSTRAINT uq_benchmark_scores UNIQUE (tenant_id, snapshot_date, basis, basis_value)
);

-- ============================================================
-- Compliance Manager — Assessments & Compliance Score
-- ============================================================

CREATE TABLE IF NOT EXISTS compliance_scores (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id       TEXT    NOT NULL REFERENCES tenants(tenant_id),
    snapshot_date   TEXT    NOT NULL,
    current_score   REAL    NOT NULL,
    max_score       REAL    NOT NULL,
    category        TEXT    NULL,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    CONSTRAINT uq_compliance_scores UNIQUE (tenant_id, snapshot_date, category)
);

CREATE TABLE IF NOT EXISTS assessments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id       TEXT    NOT NULL REFERENCES tenants(tenant_id),
    assessment_id   TEXT    NOT NULL,
    display_name    TEXT    NOT NULL,
    description     TEXT    NULL,
    status          TEXT    NULL,
    regulation      TEXT    NULL,
    compliance_score REAL   NULL,
    passed_controls INTEGER NULL,
    failed_controls INTEGER NULL,
    total_controls  INTEGER NULL,
    created_date    TEXT    NULL,
    last_modified   TEXT    NULL,
    synced_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    CONSTRAINT uq_assessments UNIQUE (tenant_id, assessment_id)
);

CREATE TABLE IF NOT EXISTS assessment_controls (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id             TEXT    NOT NULL REFERENCES tenants(tenant_id),
    assessment_id         TEXT    NOT NULL,
    control_id            TEXT    NOT NULL,
    control_name          TEXT    NOT NULL,
    control_family        TEXT    NULL,
    control_category      TEXT    NULL,
    implementation_status TEXT    NULL,
    test_status           TEXT    NULL,
    score                 REAL    NULL,
    max_score             REAL    NULL,
    score_impact          TEXT    NULL,
    owner                 TEXT    NULL,
    action_url            TEXT    NULL,
    implementation_details TEXT   NULL,
    test_plan             TEXT    NULL,
    management_response   TEXT    NULL,
    evidence_of_completion TEXT   NULL,
    service               TEXT    NULL,
    notes                 TEXT    NULL,
    synced_at             TEXT    NOT NULL DEFAULT (datetime('now')),
    CONSTRAINT uq_assessment_controls UNIQUE (tenant_id, assessment_id, control_id)
);

-- ============================================================
-- Views
-- ============================================================

-- Latest score per tenant
CREATE VIEW IF NOT EXISTS v_latest_scores AS
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
    ROUND(ss.current_score * 100.0 / MAX(ss.max_score, 1e-9), 1) AS score_pct,
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

-- Top control gaps per tenant
CREATE VIEW IF NOT EXISTS v_top_gaps AS
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
CREATE VIEW IF NOT EXISTS v_enterprise_rollup AS
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

-- Score trend per tenant over time
CREATE VIEW IF NOT EXISTS v_score_trend AS
SELECT
    t.tenant_id,
    t.display_name,
    t.department,
    t.risk_tier,
    ss.snapshot_date,
    ss.current_score,
    ss.max_score,
    ROUND(ss.current_score * 100.0 / MAX(ss.max_score, 1e-9), 1) AS score_pct
FROM tenants t
JOIN secure_scores ss ON ss.tenant_id = t.tenant_id
WHERE t.is_active = 1;

-- Week-over-week score change per tenant (requires SQLite 3.25+)
CREATE VIEW IF NOT EXISTS v_weekly_change AS
WITH weekly AS (
    SELECT
        tenant_id,
        snapshot_date,
        current_score,
        max_score,
        ROUND(current_score * 100.0 / MAX(max_score, 1e-9), 1) AS score_pct,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, strftime('%W', snapshot_date), strftime('%Y', snapshot_date)
            ORDER BY snapshot_date DESC
        ) AS rn_week
    FROM secure_scores
),
this_week AS (
    SELECT tenant_id, snapshot_date, score_pct
    FROM weekly
    WHERE rn_week = 1
      AND snapshot_date >= date('now', '-7 days')
),
last_week AS (
    SELECT tenant_id, snapshot_date, score_pct
    FROM weekly
    WHERE rn_week = 1
      AND snapshot_date >= date('now', '-14 days')
      AND snapshot_date <  date('now', '-7 days')
)
SELECT
    t.tenant_id,
    t.display_name,
    t.department,
    t.risk_tier,
    tw.score_pct        AS current_pct,
    lw.score_pct        AS prior_pct,
    tw.score_pct - COALESCE(lw.score_pct, tw.score_pct) AS wow_change,
    CASE
        WHEN tw.score_pct - COALESCE(lw.score_pct, tw.score_pct) > 0 THEN 'Improving'
        WHEN tw.score_pct - COALESCE(lw.score_pct, tw.score_pct) < 0 THEN 'Declining'
        ELSE 'Stable'
    END AS trend_direction
FROM tenants t
LEFT JOIN this_week tw ON tw.tenant_id = t.tenant_id
LEFT JOIN last_week lw ON lw.tenant_id = t.tenant_id
WHERE t.is_active = 1;

-- Department / Agency rollup
CREATE VIEW IF NOT EXISTS v_department_rollup AS
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

-- Category-level trend
CREATE VIEW IF NOT EXISTS v_category_trend AS
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

-- Risk-tiered summary
CREATE VIEW IF NOT EXISTS v_risk_tier_summary AS
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
-- Compliance Manager Views
-- ============================================================

-- Latest compliance score per tenant
CREATE VIEW IF NOT EXISTS v_latest_compliance_scores AS
SELECT
    t.tenant_id,
    t.display_name,
    t.department,
    t.department_head,
    t.risk_tier,
    cs.snapshot_date,
    cs.current_score,
    cs.max_score,
    ROUND(cs.current_score * 100.0 / MAX(cs.max_score, 1e-9), 1) AS compliance_pct,
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
CREATE VIEW IF NOT EXISTS v_compliance_trend AS
SELECT
    t.tenant_id,
    t.display_name,
    t.department,
    t.risk_tier,
    cs.snapshot_date,
    cs.current_score,
    cs.max_score,
    ROUND(cs.current_score * 100.0 / MAX(cs.max_score, 1e-9), 1) AS compliance_pct,
    cs.category
FROM tenants t
JOIN compliance_scores cs ON cs.tenant_id = t.tenant_id
WHERE t.is_active = 1;

-- Week-over-week compliance score change (requires SQLite 3.25+)
CREATE VIEW IF NOT EXISTS v_compliance_weekly_change AS
WITH weekly AS (
    SELECT
        tenant_id,
        snapshot_date,
        current_score,
        max_score,
        ROUND(current_score * 100.0 / MAX(max_score, 1e-9), 1) AS compliance_pct,
        ROW_NUMBER() OVER (
            PARTITION BY tenant_id, strftime('%W', snapshot_date), strftime('%Y', snapshot_date)
            ORDER BY snapshot_date DESC
        ) AS rn_week
    FROM compliance_scores
    WHERE category = 'overall'
),
this_week AS (
    SELECT tenant_id, snapshot_date, compliance_pct
    FROM weekly
    WHERE rn_week = 1
      AND snapshot_date >= date('now', '-7 days')
),
last_week AS (
    SELECT tenant_id, snapshot_date, compliance_pct
    FROM weekly
    WHERE rn_week = 1
      AND snapshot_date >= date('now', '-14 days')
      AND snapshot_date <  date('now', '-7 days')
)
SELECT
    t.tenant_id,
    t.display_name,
    t.department,
    t.risk_tier,
    tw.compliance_pct   AS current_pct,
    lw.compliance_pct   AS prior_pct,
    tw.compliance_pct - COALESCE(lw.compliance_pct, tw.compliance_pct) AS wow_change,
    CASE
        WHEN tw.compliance_pct - COALESCE(lw.compliance_pct, tw.compliance_pct) > 0 THEN 'Improving'
        WHEN tw.compliance_pct - COALESCE(lw.compliance_pct, tw.compliance_pct) < 0 THEN 'Declining'
        ELSE 'Stable'
    END AS trend_direction
FROM tenants t
LEFT JOIN this_week tw ON tw.tenant_id = t.tenant_id
LEFT JOIN last_week lw ON lw.tenant_id = t.tenant_id
WHERE t.is_active = 1;

-- Assessment summary
CREATE VIEW IF NOT EXISTS v_assessment_summary AS
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
    ROUND(a.passed_controls * 100.0 / MAX(a.total_controls, 1e-9), 1) AS pass_rate,
    a.last_modified
FROM assessments a
JOIN tenants t ON t.tenant_id = a.tenant_id
WHERE t.is_active = 1 AND a.status = 'active';

-- Assessment control gaps
CREATE VIEW IF NOT EXISTS v_assessment_gaps AS
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
    ac.max_score - COALESCE(ac.score, 0) AS points_gap,
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

-- Top improvement actions
CREATE VIEW IF NOT EXISTS v_improvement_actions AS
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
    ac.max_score - COALESCE(ac.score, 0) AS points_gap,
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
CREATE VIEW IF NOT EXISTS v_compliance_department_rollup AS
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

-- Regulation coverage
CREATE VIEW IF NOT EXISTS v_regulation_coverage AS
SELECT
    a.regulation,
    COUNT(DISTINCT a.tenant_id)   AS tenant_count,
    COUNT(DISTINCT a.assessment_id) AS assessment_count,
    AVG(a.compliance_score)       AS avg_compliance_score,
    SUM(a.passed_controls)        AS total_passed,
    SUM(a.failed_controls)        AS total_failed,
    SUM(a.total_controls)         AS total_controls,
    ROUND(SUM(a.passed_controls) * 100.0 / MAX(SUM(a.total_controls), 1e-9), 1) AS overall_pass_rate
FROM assessments a
JOIN tenants t ON t.tenant_id = a.tenant_id
WHERE t.is_active = 1 AND a.status = 'active'
GROUP BY a.regulation;

-- Category compliance trend
CREATE VIEW IF NOT EXISTS v_compliance_category_trend AS
SELECT
    t.department,
    ac.control_family,
    a.regulation,
    COUNT(*) AS total_controls,
    SUM(CASE WHEN ac.implementation_status = 'implemented' THEN 1 ELSE 0 END) AS implemented,
    SUM(CASE WHEN ac.test_status = 'passed' THEN 1 ELSE 0 END) AS passed,
    SUM(CASE WHEN ac.test_status = 'failed' THEN 1 ELSE 0 END) AS failed,
    AVG(ac.max_score - COALESCE(ac.score, 0)) AS avg_gap
FROM assessment_controls ac
JOIN assessments a ON a.tenant_id = ac.tenant_id AND a.assessment_id = ac.assessment_id
JOIN tenants t ON t.tenant_id = ac.tenant_id
WHERE t.is_active = 1 AND a.status = 'active'
GROUP BY t.department, ac.control_family, a.regulation;
