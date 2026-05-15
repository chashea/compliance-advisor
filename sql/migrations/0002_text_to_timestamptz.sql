-- ════════════════════════════════════════════════════════════════
-- Migration 0002: Convert TEXT timestamp columns to TIMESTAMPTZ
-- ════════════════════════════════════════════════════════════════
--
-- 17 columns across 11 tables were stored as TEXT containing ISO-8601
-- strings. This prevents range queries, prevents proper indexing, and
-- makes trend / MTTR queries do string compares instead of arithmetic.
--
-- Strategy:
--   • For each column, add a <col>_raw TEXT backup populated from the
--     current value before the type cast. This lets us roll back without
--     data loss for one release cycle.
--   • Cast TEXT → TIMESTAMPTZ via NULLIF(<col>, '')::timestamptz.
--     The NULLIF maps the collector's empty-string default to NULL.
--     Anything that fails to parse aborts the migration — by design,
--     since malformed data should never have been ingested.
--   • A follow-up migration after a soak period drops the _raw columns.
--
-- Idempotency: each ALTER is gated on information_schema lookups so
-- yoyo + the legacy IF-NOT-EXISTS pattern coexist for environments that
-- bypass yoyo state tracking.

DO $$
DECLARE
    rec RECORD;
    cols CONSTANT TEXT[][] := ARRAY[
        ['retention_events',          'created'],
        ['retention_event_types',     'created'],
        ['retention_event_types',     'modified'],
        ['retention_labels',          'created'],
        ['retention_labels',          'modified'],
        ['audit_records',             'created'],
        ['dlp_alerts',                'created'],
        ['dlp_alerts',                'resolved'],
        ['irm_alerts',                'created'],
        ['irm_alerts',                'resolved'],
        ['dlp_policies',              'created'],
        ['dlp_policies',              'modified'],
        ['irm_policies',              'created'],
        ['compliance_assessments',    'created'],
        ['threat_assessment_requests','created'],
        ['purview_incidents',         'created'],
        ['purview_incidents',         'last_update']
    ];
    t TEXT;
    c TEXT;
    current_type TEXT;
BEGIN
    FOR i IN 1..array_upper(cols, 1) LOOP
        t := cols[i][1];
        c := cols[i][2];

        SELECT data_type INTO current_type
        FROM information_schema.columns
        WHERE table_name = t AND column_name = c;

        IF current_type IS NULL THEN
            RAISE NOTICE 'Skipping %.%: column does not exist', t, c;
            CONTINUE;
        END IF;

        IF current_type = 'timestamp with time zone' THEN
            RAISE NOTICE 'Skipping %.%: already TIMESTAMPTZ', t, c;
            CONTINUE;
        END IF;

        EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS %I TEXT', t, c || '_raw');
        EXECUTE format('UPDATE %I SET %I = %I WHERE %I IS NULL', t, c || '_raw', c, c || '_raw');
        EXECUTE format(
            'ALTER TABLE %I ALTER COLUMN %I TYPE TIMESTAMPTZ '
            'USING NULLIF(%I, '''')::timestamptz',
            t, c, c
        );
        RAISE NOTICE 'Converted %.% to TIMESTAMPTZ (backup in %_raw)', t, c, c;
    END LOOP;
END $$;
