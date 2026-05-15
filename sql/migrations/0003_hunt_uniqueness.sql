-- ════════════════════════════════════════════════════════════════
-- Migration 0003: UNIQUE constraints on hunt_runs and hunt_results
-- ════════════════════════════════════════════════════════════════
--
-- The hunt tables had no UNIQUE constraints. Re-running the same
-- template against the same tenant duplicates run rows; re-running and
-- re-persisting the same KQL row duplicates result rows. Both add noise
-- to dashboards and inflate counts.
--
-- This migration:
--   1. De-duplicates existing rows, keeping the lowest id per natural
--      key (oldest record by row creation order, since id is SERIAL).
--   2. Adds the UNIQUE constraints.
--
-- Hunt result natural key is (run_id, finding_type, account_upn,
-- object_name) — the same template producing the same finding for the
-- same target should be one row, not two.

-- ── 1. Deduplicate hunt_runs ──────────────────────────────────────
DELETE FROM hunt_runs h
USING hunt_runs h2
WHERE h.id > h2.id
  AND h.tenant_id     IS NOT DISTINCT FROM h2.tenant_id
  AND h.template_name IS NOT DISTINCT FROM h2.template_name
  AND h.run_at        IS NOT DISTINCT FROM h2.run_at;

-- ── 2. Deduplicate hunt_results ───────────────────────────────────
-- Must run BEFORE the constraint, and AFTER hunt_runs dedup so that
-- results pointing at deleted run_ids are also removed.
DELETE FROM hunt_results r
WHERE NOT EXISTS (SELECT 1 FROM hunt_runs WHERE id = r.run_id);

DELETE FROM hunt_results r
USING hunt_results r2
WHERE r.id > r2.id
  AND r.run_id       IS NOT DISTINCT FROM r2.run_id
  AND r.finding_type IS NOT DISTINCT FROM r2.finding_type
  AND r.account_upn  IS NOT DISTINCT FROM r2.account_upn
  AND r.object_name  IS NOT DISTINCT FROM r2.object_name;

-- ── 3. Constraints ───────────────────────────────────────────────
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'hunt_runs_uniq'
    ) THEN
        ALTER TABLE hunt_runs
            ADD CONSTRAINT hunt_runs_uniq UNIQUE (tenant_id, template_name, run_at);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'hunt_results_uniq'
    ) THEN
        ALTER TABLE hunt_results
            ADD CONSTRAINT hunt_results_uniq
            UNIQUE (run_id, finding_type, account_upn, object_name);
    END IF;
END $$;
