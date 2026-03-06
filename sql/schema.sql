-- ══════════════════════════════════════════════════════════════════
-- Compliance Advisor — PostgreSQL Schema
-- ══════════════════════════════════════════════════════════════════

-- Tenant registry (one row per GCC tenant)
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id       TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    department      TEXT NOT NULL,
    risk_tier       TEXT DEFAULT 'Medium',
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- Daily posture snapshots (one row per tenant per collection run)
CREATE TABLE IF NOT EXISTS posture_snapshots (
    id                  SERIAL PRIMARY KEY,
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    snapshot_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    compliance_score    REAL NOT NULL,
    max_score           REAL NOT NULL DEFAULT 350,
    compliance_pct      REAL GENERATED ALWAYS AS (
        CASE WHEN max_score > 0
             THEN ROUND((compliance_score / max_score * 100)::numeric, 2)
             ELSE 0
        END
    ) STORED,
    collector_version   TEXT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, snapshot_date)
);

-- Compliance Manager assessments
CREATE TABLE IF NOT EXISTS assessments (
    id                  SERIAL PRIMARY KEY,
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    assessment_id       TEXT NOT NULL,
    assessment_name     TEXT,
    regulation          TEXT NOT NULL,
    compliance_score    REAL DEFAULT 0,
    passed_controls     INT DEFAULT 0,
    failed_controls     INT DEFAULT 0,
    total_controls      INT DEFAULT 0,
    pass_rate           REAL GENERATED ALWAYS AS (
        CASE WHEN total_controls > 0
             THEN ROUND((passed_controls::numeric / total_controls * 100), 2)
             ELSE 0
        END
    ) STORED,
    snapshot_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, assessment_id, snapshot_date)
);

-- Individual improvement actions (with self-calculated scoring)
CREATE TABLE IF NOT EXISTS improvement_actions (
    id                      SERIAL PRIMARY KEY,
    tenant_id               TEXT NOT NULL REFERENCES tenants(tenant_id),
    action_id               TEXT NOT NULL,
    control_name            TEXT,
    control_family          TEXT,
    regulation              TEXT,
    implementation_status   TEXT,
    test_status             TEXT,
    action_category         TEXT,
    is_mandatory            BOOLEAN DEFAULT TRUE,
    point_value             INT DEFAULT 0,
    owner                   TEXT,
    service                 TEXT,
    description             TEXT,
    remediation_steps       TEXT,
    snapshot_date           DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, action_id, snapshot_date)
);

-- Daily compliance trend (computed by timer trigger)
CREATE TABLE IF NOT EXISTS compliance_trend (
    id                  SERIAL PRIMARY KEY,
    snapshot_date       DATE NOT NULL,
    department          TEXT,
    avg_compliance_pct  REAL,
    min_compliance_pct  REAL,
    max_compliance_pct  REAL,
    tenant_count        INT,
    UNIQUE (snapshot_date, department)
);

-- ── Indexes ──────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_snapshots_tenant_date
    ON posture_snapshots(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_snapshots_date
    ON posture_snapshots(snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_assessments_tenant
    ON assessments(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_assessments_regulation
    ON assessments(regulation);

CREATE INDEX IF NOT EXISTS idx_actions_tenant
    ON improvement_actions(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_actions_status
    ON improvement_actions(implementation_status);

CREATE INDEX IF NOT EXISTS idx_trend_date
    ON compliance_trend(snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_tenants_dept
    ON tenants(department);
