-- ══════════════════════════════════════════════════════════════════
-- Compliance Advisor — PostgreSQL Schema (v3: Compliance Workload APIs)
-- ══════════════════════════════════════════════════════════════════

-- Tenant registry (one row per GCC tenant)
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id       TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    department      TEXT NOT NULL,
    risk_tier       TEXT DEFAULT 'Medium',
    created_at      TIMESTAMPTZ DEFAULT now()
);

-- eDiscovery cases
CREATE TABLE IF NOT EXISTS ediscovery_cases (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    case_id         TEXT NOT NULL,
    display_name    TEXT,
    status          TEXT,
    created         TEXT,
    closed          TEXT,
    external_id     TEXT,
    custodian_count INT DEFAULT 0,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, case_id, snapshot_date)
);

-- Sensitivity labels (Information Protection)
CREATE TABLE IF NOT EXISTS sensitivity_labels (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    label_id        TEXT NOT NULL,
    name            TEXT,
    description     TEXT,
    color           TEXT,
    is_active       BOOLEAN DEFAULT TRUE,
    parent_id       TEXT,
    priority        INT DEFAULT 0,
    tooltip         TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, label_id, snapshot_date)
);

-- Retention labels (Records Management)
CREATE TABLE IF NOT EXISTS retention_labels (
    id                      SERIAL PRIMARY KEY,
    tenant_id               TEXT NOT NULL REFERENCES tenants(tenant_id),
    label_id                TEXT NOT NULL,
    display_name            TEXT,
    retention_duration      TEXT,
    retention_trigger       TEXT,
    action_after_retention  TEXT,
    is_in_use               BOOLEAN DEFAULT FALSE,
    status                  TEXT,
    snapshot_date           DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, label_id, snapshot_date)
);

-- Retention events (Records Management)
CREATE TABLE IF NOT EXISTS retention_events (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    event_id        TEXT NOT NULL,
    display_name    TEXT,
    event_type      TEXT,
    created         TEXT,
    event_status    TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, event_id, snapshot_date)
);

-- Audit log records
CREATE TABLE IF NOT EXISTS audit_records (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    record_id       TEXT NOT NULL,
    record_type     TEXT,
    operation       TEXT,
    service         TEXT,
    user_id         TEXT,
    created         TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, record_id, snapshot_date)
);

-- DLP alerts (Data Security)
CREATE TABLE IF NOT EXISTS dlp_alerts (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    alert_id        TEXT NOT NULL,
    title           TEXT,
    severity        TEXT,
    status          TEXT,
    category        TEXT,
    policy_name     TEXT,
    created         TEXT,
    resolved        TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, alert_id, snapshot_date)
);

-- Data Security & Governance protection scopes
CREATE TABLE IF NOT EXISTS protection_scopes (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    scope_type      TEXT NOT NULL,
    execution_mode  TEXT,
    locations       TEXT,
    activity_types  TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, scope_type, snapshot_date)
);

-- Daily compliance trend (computed by timer trigger)
CREATE TABLE IF NOT EXISTS compliance_trend (
    id                  SERIAL PRIMARY KEY,
    snapshot_date       DATE NOT NULL,
    department          TEXT,
    ediscovery_cases    INT DEFAULT 0,
    sensitivity_labels  INT DEFAULT 0,
    retention_labels    INT DEFAULT 0,
    dlp_alerts          INT DEFAULT 0,
    audit_records       INT DEFAULT 0,
    tenant_count        INT DEFAULT 0,
    UNIQUE (snapshot_date, department)
);

-- ── Indexes ──────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_ediscovery_tenant
    ON ediscovery_cases(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_sensitivity_labels_tenant
    ON sensitivity_labels(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_retention_labels_tenant
    ON retention_labels(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_retention_events_tenant
    ON retention_events(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_audit_records_tenant
    ON audit_records(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_dlp_alerts_tenant
    ON dlp_alerts(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_dlp_alerts_severity
    ON dlp_alerts(severity);

CREATE INDEX IF NOT EXISTS idx_protection_scopes_tenant
    ON protection_scopes(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_trend_date
    ON compliance_trend(snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_tenants_dept
    ON tenants(department);
