-- R1: canonical profile ownership for legacy personal-data roots.
--
-- A legacy row is backfilled only from an existing verified relationship, or
-- when the installation has exactly one canonical profile.  Multi-profile
-- installations with ambiguous legacy rows fail closed and require an
-- explicit ownership repair before this migration is retried.

ALTER TABLE requests ADD COLUMN IF NOT EXISTS profile_id UUID;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS profile_id UUID;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS profile_id UUID;
ALTER TABLE vendor_lists ADD COLUMN IF NOT EXISTS profile_id UUID;
ALTER TABLE id_documents ADD COLUMN IF NOT EXISTS profile_id UUID;
ALTER TABLE connector_credentials ADD COLUMN IF NOT EXISTS profile_id UUID;
ALTER TABLE email_settings ADD COLUMN IF NOT EXISTS profile_id UUID;
ALTER TABLE ai_credentials ADD COLUMN IF NOT EXISTS profile_id UUID;

-- Prefer evidence relationships for request ownership.
WITH candidates AS (
    SELECT request_id, MIN(profile_id::text)::uuid AS profile_id
    FROM (
        SELECT request_id, profile_id
        FROM analysis_runs
        WHERE request_id IS NOT NULL AND profile_id IS NOT NULL
        UNION ALL
        SELECT request_id, profile_id
        FROM export_snapshots
        WHERE request_id IS NOT NULL AND profile_id IS NOT NULL
    ) linked
    GROUP BY request_id
    HAVING COUNT(DISTINCT profile_id) = 1
)
UPDATE requests request
SET profile_id = candidates.profile_id
FROM candidates
WHERE request.id = candidates.request_id
  AND request.profile_id IS NULL;

UPDATE received_data data
SET profile_id = request.profile_id
FROM requests request
WHERE data.request_id = request.id
  AND data.profile_id IS NULL;

UPDATE request_threads thread
SET profile_id = request.profile_id
FROM requests request
WHERE thread.request_id = request.id
  AND thread.profile_id IS NULL;

-- Connector instances already carry canonical profile ownership.
WITH candidates AS (
    SELECT credential_id, MIN(profile_id::text)::uuid AS profile_id
    FROM connector_instances
    WHERE credential_id IS NOT NULL AND profile_id IS NOT NULL
    GROUP BY credential_id
    HAVING COUNT(DISTINCT profile_id) = 1
)
UPDATE connector_credentials credential
SET profile_id = candidates.profile_id
FROM candidates
WHERE credential.id = candidates.credential_id
  AND credential.profile_id IS NULL;

UPDATE email_settings settings
SET profile_id = credential.profile_id
FROM connector_credentials credential
WHERE settings.credential_id = credential.id
  AND settings.profile_id IS NULL
  AND credential.profile_id IS NOT NULL;

DO $$
DECLARE
    canonical_profile UUID;
    profile_count INTEGER;
    table_name TEXT;
    unowned_count BIGINT;
BEGIN
    SELECT COUNT(*), MIN(id::text)::uuid INTO profile_count, canonical_profile FROM profiles;

    IF profile_count = 1 THEN
        UPDATE requests SET profile_id = canonical_profile WHERE profile_id IS NULL;
        UPDATE received_data SET profile_id = canonical_profile WHERE profile_id IS NULL;
        UPDATE request_threads SET profile_id = canonical_profile WHERE profile_id IS NULL;
        UPDATE vendor_lists SET profile_id = canonical_profile WHERE profile_id IS NULL;
        UPDATE id_documents SET profile_id = canonical_profile WHERE profile_id IS NULL;
        UPDATE connector_credentials SET profile_id = canonical_profile WHERE profile_id IS NULL;
        UPDATE email_settings SET profile_id = canonical_profile WHERE profile_id IS NULL;
        UPDATE ai_credentials SET profile_id = canonical_profile WHERE profile_id IS NULL;
    END IF;

    FOREACH table_name IN ARRAY ARRAY['requests','received_data','request_threads','vendor_lists','id_documents','connector_credentials','email_settings','ai_credentials']
    LOOP
        EXECUTE format('SELECT COUNT(*) FROM %I WHERE profile_id IS NULL', table_name)
        INTO unowned_count;
        IF unowned_count > 0 THEN
            RAISE EXCEPTION
                'R1 cannot infer canonical ownership for % row(s) in %. Assign profile_id explicitly before retrying.',
                unowned_count, table_name;
        END IF;
    END LOOP;
END $$;

ALTER TABLE requests ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE received_data ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE request_threads ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE vendor_lists ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE id_documents ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE connector_credentials ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE email_settings ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE ai_credentials ALTER COLUMN profile_id SET NOT NULL;

-- The application deliberately supports one active mail account per profile.
-- Preserve every legacy row and fail with an actionable repair instruction
-- instead of allowing the later unique index to fail opaquely.
DO $$
DECLARE duplicate_profile UUID;
BEGIN
    SELECT profile_id INTO duplicate_profile
    FROM email_settings
    GROUP BY profile_id
    HAVING COUNT(*) > 1
    LIMIT 1;
    IF duplicate_profile IS NOT NULL THEN
        RAISE EXCEPTION
            'R1 found multiple email_settings rows for profile %. Consolidate them to one active account before retrying.',
            duplicate_profile;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='requests_profile_id_fkey') THEN
        ALTER TABLE requests ADD CONSTRAINT requests_profile_id_fkey
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='received_data_profile_id_fkey') THEN
        ALTER TABLE received_data ADD CONSTRAINT received_data_profile_id_fkey
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='request_threads_profile_id_fkey') THEN
        ALTER TABLE request_threads ADD CONSTRAINT request_threads_profile_id_fkey
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='vendor_lists_profile_id_fkey') THEN
        ALTER TABLE vendor_lists ADD CONSTRAINT vendor_lists_profile_id_fkey
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='id_documents_profile_id_fkey') THEN
        ALTER TABLE id_documents ADD CONSTRAINT id_documents_profile_id_fkey
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='connector_credentials_profile_id_fkey') THEN
        ALTER TABLE connector_credentials ADD CONSTRAINT connector_credentials_profile_id_fkey
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='email_settings_profile_id_fkey') THEN
        ALTER TABLE email_settings ADD CONSTRAINT email_settings_profile_id_fkey
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ai_credentials_profile_id_fkey') THEN
        ALTER TABLE ai_credentials ADD CONSTRAINT ai_credentials_profile_id_fkey
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT;
    END IF;
END $$;

ALTER TABLE connector_credentials DROP CONSTRAINT IF EXISTS connector_credentials_connector_key_account_key_key;
CREATE UNIQUE INDEX IF NOT EXISTS connector_credentials_profile_connector_account_uidx
    ON connector_credentials(profile_id, connector_key, account_key);
CREATE UNIQUE INDEX IF NOT EXISTS email_settings_profile_uidx ON email_settings(profile_id);
ALTER TABLE ai_credentials DROP CONSTRAINT IF EXISTS ai_credentials_provider_key;
CREATE UNIQUE INDEX IF NOT EXISTS ai_credentials_profile_provider_uidx ON ai_credentials(profile_id, provider);
CREATE INDEX IF NOT EXISTS requests_profile_created_idx ON requests(profile_id, created_at DESC);
CREATE INDEX IF NOT EXISTS received_data_profile_received_idx ON received_data(profile_id, date_received DESC);
CREATE INDEX IF NOT EXISTS request_threads_profile_updated_idx ON request_threads(profile_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS vendor_lists_profile_updated_idx ON vendor_lists(profile_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS id_documents_profile_uploaded_idx ON id_documents(profile_id, uploaded_at DESC);

CREATE OR REPLACE VIEW access_requests AS
SELECT id, company_name, company_url, domain, status, request_type, created_at, profile_id
FROM requests;
