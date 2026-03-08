-- ══════════════════════════════════════════════════════════════════
-- Compliance Advisor — PostgreSQL Schema (v2: Graph API data model)
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
    secure_score        REAL NOT NULL,
    max_score           REAL NOT NULL DEFAULT 0,
    score_pct           REAL GENERATED ALWAYS AS (
        CASE WHEN max_score > 0
             THEN ROUND((secure_score / max_score * 100)::numeric, 2)
             ELSE 0
        END
    ) STORED,
    active_user_count   INT DEFAULT 0,
    licensed_user_count INT DEFAULT 0,
    controls_total      INT DEFAULT 0,
    controls_implemented INT DEFAULT 0,
    collector_version   TEXT,
    created_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (tenant_id, snapshot_date)
);

-- Per-control scores from latest Secure Score snapshot
CREATE TABLE IF NOT EXISTS control_scores (
    id                      SERIAL PRIMARY KEY,
    tenant_id               TEXT NOT NULL REFERENCES tenants(tenant_id),
    control_name            TEXT NOT NULL,
    category                TEXT,
    score                   REAL DEFAULT 0,
    score_pct               REAL DEFAULT 0,
    implementation_status   TEXT,
    last_synced             TEXT,
    description             TEXT,
    snapshot_date           DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, control_name, snapshot_date)
);

-- Secure Score control profiles (definitions, not per-tenant scores)
CREATE TABLE IF NOT EXISTS control_profiles (
    id                  SERIAL PRIMARY KEY,
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    control_id          TEXT NOT NULL,
    title               TEXT,
    max_score           REAL DEFAULT 0,
    service             TEXT,
    category            TEXT,
    action_type         TEXT,
    tier                TEXT,
    implementation_cost TEXT,
    user_impact         TEXT,
    snapshot_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, control_id, snapshot_date)
);

-- Security alerts from Microsoft 365 Defender
CREATE TABLE IF NOT EXISTS security_alerts (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    alert_id        TEXT NOT NULL,
    title           TEXT,
    severity        TEXT,
    status          TEXT,
    category        TEXT,
    service_source  TEXT,
    created         TEXT,
    resolved        TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, alert_id, snapshot_date)
);

-- Security incidents
CREATE TABLE IF NOT EXISTS security_incidents (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    incident_id     TEXT NOT NULL,
    display_name    TEXT,
    severity        TEXT,
    status          TEXT,
    classification  TEXT,
    created         TEXT,
    last_update     TEXT,
    assigned_to     TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, incident_id, snapshot_date)
);

-- Risky users from Identity Protection
CREATE TABLE IF NOT EXISTS risky_users (
    id                  SERIAL PRIMARY KEY,
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    user_id             TEXT NOT NULL,
    user_display_name   TEXT,
    user_principal_name TEXT,
    risk_level          TEXT,
    risk_state          TEXT,
    risk_detail         TEXT,
    risk_last_updated   TEXT,
    snapshot_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, user_id, snapshot_date)
);

-- M365 service health
CREATE TABLE IF NOT EXISTS service_health (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    service_name    TEXT NOT NULL,
    status          TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, service_name, snapshot_date)
);

-- Daily compliance trend (computed by timer trigger)
CREATE TABLE IF NOT EXISTS compliance_trend (
    id                  SERIAL PRIMARY KEY,
    snapshot_date       DATE NOT NULL,
    department          TEXT,
    avg_score_pct       REAL,
    min_score_pct       REAL,
    max_score_pct       REAL,
    tenant_count        INT,
    UNIQUE (snapshot_date, department)
);

-- ── Indexes ──────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_snapshots_tenant_date
    ON posture_snapshots(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_snapshots_date
    ON posture_snapshots(snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_control_scores_tenant
    ON control_scores(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_control_profiles_tenant
    ON control_profiles(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_tenant
    ON security_alerts(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_alerts_severity
    ON security_alerts(severity);

CREATE INDEX IF NOT EXISTS idx_incidents_tenant
    ON security_incidents(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_risky_users_tenant
    ON risky_users(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_service_health_tenant
    ON service_health(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_trend_date
    ON compliance_trend(snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_tenants_dept
    ON tenants(department);
