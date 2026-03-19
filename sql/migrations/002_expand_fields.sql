-- Migration 002: Expand data ingestion fields
-- Run BEFORE deploying the updated collector/functions code.

-- Audit records: add ip_address, client_app, result_status
ALTER TABLE audit_records ADD COLUMN IF NOT EXISTS ip_address TEXT DEFAULT '';
ALTER TABLE audit_records ADD COLUMN IF NOT EXISTS client_app TEXT DEFAULT '';
ALTER TABLE audit_records ADD COLUMN IF NOT EXISTS result_status TEXT DEFAULT '';

-- DLP alerts: add description, assigned_to
ALTER TABLE dlp_alerts ADD COLUMN IF NOT EXISTS description TEXT DEFAULT '';
ALTER TABLE dlp_alerts ADD COLUMN IF NOT EXISTS assigned_to TEXT DEFAULT '';

-- IRM alerts: add description, assigned_to
ALTER TABLE irm_alerts ADD COLUMN IF NOT EXISTS description TEXT DEFAULT '';
ALTER TABLE irm_alerts ADD COLUMN IF NOT EXISTS assigned_to TEXT DEFAULT '';
