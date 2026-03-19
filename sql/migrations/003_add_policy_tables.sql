-- Migration 003: Add DLP policies, IRM policies, sensitive info types, compliance assessments
-- These are additive — no existing tables are modified.

-- DLP Policies
CREATE TABLE IF NOT EXISTS dlp_policies (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    policy_id       TEXT NOT NULL,
    display_name    TEXT,
    status          TEXT,
    policy_type     TEXT,
    rules_count     INT DEFAULT 0,
    created         TEXT,
    modified        TEXT,
    mode            TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, policy_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_dlp_policies_tenant
    ON dlp_policies(tenant_id, snapshot_date DESC);

-- IRM Policies
CREATE TABLE IF NOT EXISTS irm_policies (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    policy_id       TEXT NOT NULL,
    display_name    TEXT,
    status          TEXT,
    policy_type     TEXT,
    created         TEXT,
    triggers        TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, policy_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_irm_policies_tenant
    ON irm_policies(tenant_id, snapshot_date DESC);

-- Sensitive Information Types
CREATE TABLE IF NOT EXISTS sensitive_info_types (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    type_id         TEXT NOT NULL,
    name            TEXT,
    description     TEXT,
    is_custom       BOOLEAN DEFAULT FALSE,
    category        TEXT,
    scope           TEXT,
    state           TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, type_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_sensitive_info_types_tenant
    ON sensitive_info_types(tenant_id, snapshot_date DESC);

-- Compliance Assessments
CREATE TABLE IF NOT EXISTS compliance_assessments (
    id                      SERIAL PRIMARY KEY,
    tenant_id               TEXT NOT NULL REFERENCES tenants(tenant_id),
    assessment_id           TEXT NOT NULL,
    display_name            TEXT,
    status                  TEXT,
    framework               TEXT,
    completion_percentage   REAL DEFAULT 0,
    created                 TEXT,
    category                TEXT,
    snapshot_date           DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, assessment_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_compliance_assessments_tenant
    ON compliance_assessments(tenant_id, snapshot_date DESC);
