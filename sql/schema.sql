-- ══════════════════════════════════════════════════════════════════
-- Compliance Advisor — PostgreSQL Schema (v3: Compliance Workload APIs)
-- ══════════════════════════════════════════════════════════════════

-- Tenant registry (one row per tenant)
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id       TEXT PRIMARY KEY,
    display_name    TEXT NOT NULL,
    department      TEXT NOT NULL,
    risk_tier       TEXT DEFAULT 'Medium',
    status          TEXT DEFAULT 'pending',
    collected_at    TIMESTAMPTZ,
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
    has_protection  BOOLEAN DEFAULT FALSE,
    applicable_to   TEXT DEFAULT '',
    application_mode TEXT DEFAULT '',
    is_endpoint_protection_enabled BOOLEAN DEFAULT FALSE,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
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

-- Retention event types (Records Management)
CREATE TABLE IF NOT EXISTS retention_event_types (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    event_type_id   TEXT NOT NULL,
    display_name    TEXT,
    description     TEXT,
    created         TEXT,
    modified        TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, event_type_id, snapshot_date)
);

-- Retention labels (Records Management) — beta API, may require delegated auth
CREATE TABLE IF NOT EXISTS retention_labels (
    id                      SERIAL PRIMARY KEY,
    tenant_id               TEXT NOT NULL REFERENCES tenants(tenant_id),
    label_id                TEXT NOT NULL,
    name                    TEXT,
    description             TEXT,
    is_in_use               BOOLEAN DEFAULT FALSE,
    retention_duration      TEXT,
    action_after            TEXT,
    default_record_behavior TEXT,
    created                 TEXT,
    modified                TEXT,
    snapshot_date           DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, label_id, snapshot_date)
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
    ip_address      TEXT DEFAULT '',
    client_app      TEXT DEFAULT '',
    result_status   TEXT DEFAULT '',
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
    description     TEXT DEFAULT '',
    assigned_to     TEXT DEFAULT '',
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

-- Insider Risk Management alerts (from Defender legacy alerts API)
CREATE TABLE IF NOT EXISTS irm_alerts (
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
    description     TEXT DEFAULT '',
    assigned_to     TEXT DEFAULT '',
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, alert_id, snapshot_date)
);

-- Secure Score snapshots
CREATE TABLE IF NOT EXISTS secure_scores (
    id                  SERIAL PRIMARY KEY,
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    current_score       REAL NOT NULL,
    max_score           REAL NOT NULL,
    score_date          DATE NOT NULL,
    snapshot_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    data_current_score  REAL DEFAULT 0,
    data_max_score      REAL DEFAULT 0,
    UNIQUE (tenant_id, score_date, snapshot_date)
);

-- Improvement actions (Secure Score control profiles)
CREATE TABLE IF NOT EXISTS improvement_actions (
    id                  SERIAL PRIMARY KEY,
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    control_id          TEXT NOT NULL,
    title               TEXT,
    control_category    TEXT,
    max_score           REAL DEFAULT 0,
    current_score       REAL DEFAULT 0,
    implementation_cost TEXT,
    user_impact         TEXT,
    tier                TEXT,
    service             TEXT,
    threats             TEXT,
    remediation         TEXT,
    state               TEXT DEFAULT 'Default',
    deprecated          BOOLEAN DEFAULT FALSE,
    rank                INT DEFAULT 0,
    snapshot_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, control_id, snapshot_date)
);



-- Information Barrier policies
CREATE TABLE IF NOT EXISTS info_barrier_policies (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    policy_id       TEXT NOT NULL,
    display_name    TEXT,
    state           TEXT,
    segments_applied TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, policy_id, snapshot_date)
);

-- User content policies (userDataSecurityAndGovernance processContent probe)
CREATE TABLE IF NOT EXISTS user_content_policies (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    user_id         TEXT NOT NULL,
    user_upn        TEXT NOT NULL,
    action          TEXT,
    policy_id       TEXT,
    policy_name     TEXT,
    rule_id         TEXT,
    rule_name       TEXT,
    match_count     INTEGER DEFAULT 0,
    UNIQUE (tenant_id, snapshot_date, user_id)
);

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

-- Threat Assessment Requests
CREATE TABLE IF NOT EXISTS threat_assessment_requests (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    request_id      TEXT NOT NULL,
    category        TEXT,
    content_type    TEXT,
    status          TEXT,
    created         TEXT,
    result_type     TEXT,
    result_message  TEXT,
    snapshot_date   DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, request_id, snapshot_date)
);

-- Purview-prioritized incidents (derived from Graph security incidents correlated to DLP/IRM alerts)
CREATE TABLE IF NOT EXISTS purview_incidents (
    id                  SERIAL PRIMARY KEY,
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    incident_id         TEXT NOT NULL,
    display_name        TEXT,
    severity            TEXT,
    status              TEXT,
    classification      TEXT,
    determination       TEXT,
    created             TEXT,
    last_update         TEXT,
    assigned_to         TEXT,
    alerts_count        INT DEFAULT 0,
    purview_alerts_count INT DEFAULT 0,
    snapshot_date       DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, incident_id, snapshot_date)
);

-- Daily compliance trend (computed by timer trigger)
CREATE TABLE IF NOT EXISTS compliance_trend (
    id                  SERIAL PRIMARY KEY,
    snapshot_date       DATE NOT NULL,
    department          TEXT,
    ediscovery_cases    INT DEFAULT 0,
    sensitivity_labels  INT DEFAULT 0,

    dlp_alerts          INT DEFAULT 0,
    audit_records       INT DEFAULT 0,
    tenant_count        INT DEFAULT 0,
    UNIQUE (snapshot_date, department)
);

-- Ingestion log (idempotency tracking)
CREATE TABLE IF NOT EXISTS ingestion_log (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL,
    snapshot_date   DATE NOT NULL,
    payload_hash    TEXT NOT NULL,
    ingested_at     TIMESTAMPTZ DEFAULT now(),
    record_counts   JSONB,
    UNIQUE (tenant_id, snapshot_date, payload_hash)
);

-- ── Indexes ──────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_ediscovery_tenant
    ON ediscovery_cases(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_sensitivity_labels_tenant
    ON sensitivity_labels(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_retention_events_tenant
    ON retention_events(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_retention_event_types_tenant
    ON retention_event_types(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_retention_labels_tenant
    ON retention_labels(tenant_id, snapshot_date DESC);

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

CREATE INDEX IF NOT EXISTS idx_secure_scores_tenant
    ON secure_scores(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_improvement_actions_tenant
    ON improvement_actions(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_improvement_actions_category
    ON improvement_actions(control_category);

CREATE INDEX IF NOT EXISTS idx_irm_alerts_tenant
    ON irm_alerts(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_irm_alerts_severity
    ON irm_alerts(severity);



CREATE INDEX IF NOT EXISTS idx_info_barrier_policies_tenant
    ON info_barrier_policies(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_dlp_policies_tenant
    ON dlp_policies(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_irm_policies_tenant
    ON irm_policies(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_sensitive_info_types_tenant
    ON sensitive_info_types(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_compliance_assessments_tenant
    ON compliance_assessments(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_threat_assessment_requests_tenant
    ON threat_assessment_requests(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_purview_incidents_tenant
    ON purview_incidents(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_ingestion_log_lookup
    ON ingestion_log(tenant_id, snapshot_date, payload_hash);

-- Standalone snapshot_date indexes for date-filtered dashboard queries
CREATE INDEX IF NOT EXISTS idx_audit_records_snapshot
    ON audit_records(snapshot_date);

CREATE INDEX IF NOT EXISTS idx_dlp_alerts_snapshot
    ON dlp_alerts(snapshot_date);

CREATE INDEX IF NOT EXISTS idx_compliance_trend_snapshot
    ON compliance_trend(snapshot_date);

-- ── Schema migrations ────────────────────────────────────────────

-- v0.33: Add alert evidence + classification fields to DLP and IRM alert tables
ALTER TABLE dlp_alerts ADD COLUMN IF NOT EXISTS classification TEXT DEFAULT '';
ALTER TABLE dlp_alerts ADD COLUMN IF NOT EXISTS determination TEXT DEFAULT '';
ALTER TABLE dlp_alerts ADD COLUMN IF NOT EXISTS recommended_actions TEXT DEFAULT '';
ALTER TABLE dlp_alerts ADD COLUMN IF NOT EXISTS incident_id TEXT DEFAULT '';
ALTER TABLE dlp_alerts ADD COLUMN IF NOT EXISTS mitre_techniques TEXT DEFAULT '';
ALTER TABLE dlp_alerts ADD COLUMN IF NOT EXISTS evidence JSONB DEFAULT '[]'::jsonb;

ALTER TABLE irm_alerts ADD COLUMN IF NOT EXISTS classification TEXT DEFAULT '';
ALTER TABLE irm_alerts ADD COLUMN IF NOT EXISTS determination TEXT DEFAULT '';
ALTER TABLE irm_alerts ADD COLUMN IF NOT EXISTS recommended_actions TEXT DEFAULT '';
ALTER TABLE irm_alerts ADD COLUMN IF NOT EXISTS incident_id TEXT DEFAULT '';
ALTER TABLE irm_alerts ADD COLUMN IF NOT EXISTS mitre_techniques TEXT DEFAULT '';
ALTER TABLE irm_alerts ADD COLUMN IF NOT EXISTS evidence JSONB DEFAULT '[]'::jsonb;

-- ── Threat Hunting ─────────────────────────────────────────────

-- Hunt runs (each execution of a KQL query)
CREATE TABLE IF NOT EXISTS hunt_runs (
    id              SERIAL PRIMARY KEY,
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    template_name   TEXT,
    question        TEXT,
    kql_query       TEXT NOT NULL,
    result_count    INTEGER DEFAULT 0,
    ai_narrative    TEXT,
    run_at          TIMESTAMPTZ DEFAULT NOW(),
    snapshot_date   DATE DEFAULT CURRENT_DATE
);

-- Hunt results (individual findings from a hunt run)
CREATE TABLE IF NOT EXISTS hunt_results (
    id              SERIAL PRIMARY KEY,
    run_id          INTEGER NOT NULL REFERENCES hunt_runs(id),
    tenant_id       TEXT NOT NULL REFERENCES tenants(tenant_id),
    finding_type    TEXT NOT NULL,
    severity        TEXT DEFAULT 'info',
    account_upn     TEXT,
    object_name     TEXT,
    action_type     TEXT,
    evidence        JSONB,
    detected_at     TIMESTAMPTZ,
    snapshot_date   DATE DEFAULT CURRENT_DATE
);

CREATE INDEX IF NOT EXISTS idx_hunt_runs_tenant
    ON hunt_runs(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_hunt_results_tenant
    ON hunt_results(tenant_id, snapshot_date DESC);

CREATE INDEX IF NOT EXISTS idx_hunt_results_run
    ON hunt_results(run_id);

CREATE INDEX IF NOT EXISTS idx_hunt_results_severity
    ON hunt_results(severity);
