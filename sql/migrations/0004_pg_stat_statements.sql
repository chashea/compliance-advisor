-- ════════════════════════════════════════════════════════════════
-- Migration 0004: Enable pg_stat_statements extension
-- ════════════════════════════════════════════════════════════════
--
-- The shared_preload_libraries server-config change (Bicep) loads the
-- extension into postgres on startup. CREATE EXTENSION installs the
-- bookkeeping objects in this database so queries are tracked.
--
-- Operators inspect with::
--
--     SELECT calls, mean_exec_time, total_exec_time, query
--     FROM pg_stat_statements
--     WHERE mean_exec_time > 100  -- slowest 100ms+
--     ORDER BY total_exec_time DESC
--     LIMIT 20;

CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- Reset on every migration apply is intentional: we want each release
-- to start with a clean baseline so trends are deploy-correlated.
SELECT pg_stat_statements_reset();
