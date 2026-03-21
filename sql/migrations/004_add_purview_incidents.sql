-- Migration 004: Add Purview-prioritized incidents table
-- Stores incidents from Graph security/incidents scoped to Purview signal correlation.

CREATE TABLE IF NOT EXISTS purview_incidents (
    id                   SERIAL PRIMARY KEY,
    tenant_id            TEXT NOT NULL REFERENCES tenants(tenant_id),
    incident_id          TEXT NOT NULL,
    display_name         TEXT,
    severity             TEXT,
    status               TEXT,
    classification       TEXT,
    determination        TEXT,
    created              TEXT,
    last_update          TEXT,
    assigned_to          TEXT,
    alerts_count         INT DEFAULT 0,
    purview_alerts_count INT DEFAULT 0,
    snapshot_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    UNIQUE (tenant_id, incident_id, snapshot_date)
);

CREATE INDEX IF NOT EXISTS idx_purview_incidents_tenant
    ON purview_incidents(tenant_id, snapshot_date DESC);
