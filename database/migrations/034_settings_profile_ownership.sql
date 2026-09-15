-- SETTINGS-002: make task execution configuration and audit data profile-owned.
-- Legacy configuration has no ownership relation. It is assigned only when the
-- installation has exactly one profile; otherwise this migration fails closed.

ALTER TABLE task_routes ADD COLUMN IF NOT EXISTS profile_id UUID;
ALTER TABLE processing_settings ADD COLUMN IF NOT EXISTS profile_id UUID;
ALTER TABLE execution_records ADD COLUMN IF NOT EXISTS profile_id UUID;
ALTER TABLE n8n_webhooks ADD COLUMN IF NOT EXISTS profile_id UUID;

UPDATE execution_records record
SET profile_id = run.profile_id
FROM analysis_runs run
WHERE record.analysis_run_id = run.id
  AND record.profile_id IS NULL
  AND run.profile_id IS NOT NULL;

DO $$
DECLARE
    canonical_profile UUID;
    profile_count INTEGER;
    table_name TEXT;
    unowned_count BIGINT;
BEGIN
    SELECT COUNT(*), MIN(id::text)::uuid INTO profile_count, canonical_profile FROM profiles;

    IF profile_count = 1 THEN
        UPDATE task_routes SET profile_id = canonical_profile WHERE profile_id IS NULL;
        UPDATE processing_settings SET profile_id = canonical_profile WHERE profile_id IS NULL;
        UPDATE execution_records SET profile_id = canonical_profile WHERE profile_id IS NULL;
        UPDATE n8n_webhooks SET profile_id = canonical_profile WHERE profile_id IS NULL;
    END IF;

    FOREACH table_name IN ARRAY ARRAY['task_routes','processing_settings','execution_records','n8n_webhooks']
    LOOP
        EXECUTE format('SELECT COUNT(*) FROM %I WHERE profile_id IS NULL', table_name)
        INTO unowned_count;
        IF unowned_count > 0 THEN
            RAISE EXCEPTION
                'SETTINGS-002 cannot infer canonical ownership for % row(s) in %. Assign profile_id explicitly before retrying.',
                unowned_count, table_name;
        END IF;
    END LOOP;
END $$;

ALTER TABLE task_routes ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE processing_settings ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE execution_records ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE n8n_webhooks ALTER COLUMN profile_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='task_routes_profile_id_fkey') THEN
        ALTER TABLE task_routes ADD CONSTRAINT task_routes_profile_id_fkey
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='processing_settings_profile_id_fkey') THEN
        ALTER TABLE processing_settings ADD CONSTRAINT processing_settings_profile_id_fkey
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='execution_records_profile_id_fkey') THEN
        ALTER TABLE execution_records ADD CONSTRAINT execution_records_profile_id_fkey
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='n8n_webhooks_profile_id_fkey') THEN
        ALTER TABLE n8n_webhooks ADD CONSTRAINT n8n_webhooks_profile_id_fkey
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT;
    END IF;
END $$;

ALTER TABLE task_routes DROP CONSTRAINT IF EXISTS task_routes_pkey;
CREATE UNIQUE INDEX IF NOT EXISTS task_routes_profile_task_key_uidx ON task_routes(profile_id, task_key);

CREATE SEQUENCE IF NOT EXISTS processing_settings_id_seq;
SELECT setval('processing_settings_id_seq', GREATEST(COALESCE((SELECT MAX(id) FROM processing_settings), 0), 1), true);
ALTER SEQUENCE processing_settings_id_seq OWNED BY processing_settings.id;
ALTER TABLE processing_settings ALTER COLUMN id SET DEFAULT nextval('processing_settings_id_seq');
CREATE UNIQUE INDEX IF NOT EXISTS processing_settings_profile_uidx ON processing_settings(profile_id);

DROP INDEX IF EXISTS uq_n8n_webhooks_name;
ALTER TABLE n8n_webhooks DROP CONSTRAINT IF EXISTS n8n_webhooks_workflow_key_key;
CREATE UNIQUE INDEX IF NOT EXISTS n8n_webhooks_profile_name_uidx ON n8n_webhooks(profile_id, webhook_name);

CREATE INDEX IF NOT EXISTS execution_records_profile_started_idx
    ON execution_records(profile_id, started_at DESC);
