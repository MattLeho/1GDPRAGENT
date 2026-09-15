-- POLICY-001: a policy interpretation is evidence for one request in one
-- canonical profile. Legacy global URL rows are backfilled only where one
-- request can be identified unambiguously; ambiguous rows fail closed.

ALTER TABLE policy_analyses ADD COLUMN IF NOT EXISTS profile_id UUID;
ALTER TABLE policy_analyses ADD COLUMN IF NOT EXISTS request_id UUID;
ALTER TABLE policy_analyses ADD COLUMN IF NOT EXISTS provenance JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE policy_analyses ADD COLUMN IF NOT EXISTS execution_record_id UUID;

WITH candidates AS (
    SELECT policy.id AS policy_id,
           MIN(request.id::text)::uuid AS request_id,
           MIN(request.profile_id::text)::uuid AS profile_id
    FROM policy_analyses policy
    JOIN requests request
      ON request.profile_id IS NOT NULL
     AND (request.company_url = policy.url OR request.domain = policy.domain)
    WHERE policy.profile_id IS NULL OR policy.request_id IS NULL
    GROUP BY policy.id
    HAVING COUNT(DISTINCT request.id) = 1
       AND COUNT(DISTINCT request.profile_id) = 1
)
UPDATE policy_analyses policy
SET profile_id = candidates.profile_id,
    request_id = candidates.request_id
FROM candidates
WHERE policy.id = candidates.policy_id
  AND (policy.profile_id IS NULL OR policy.request_id IS NULL);

DO $$
DECLARE
    unowned_count BIGINT;
BEGIN
    SELECT COUNT(*) INTO unowned_count FROM policy_analyses
    WHERE profile_id IS NULL OR request_id IS NULL;
    IF unowned_count > 0 THEN
        RAISE EXCEPTION
            'POLICY-001 cannot infer canonical profile and request ownership for % policy_analyses row(s). Repair those rows explicitly before retrying.',
            unowned_count;
    END IF;
END $$;

ALTER TABLE policy_analyses ALTER COLUMN profile_id SET NOT NULL;
ALTER TABLE policy_analyses ALTER COLUMN request_id SET NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'policy_analyses_profile_id_fkey') THEN
        ALTER TABLE policy_analyses ADD CONSTRAINT policy_analyses_profile_id_fkey
            FOREIGN KEY(profile_id) REFERENCES profiles(id) ON DELETE RESTRICT;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'policy_analyses_request_id_fkey') THEN
        ALTER TABLE policy_analyses ADD CONSTRAINT policy_analyses_request_id_fkey
            FOREIGN KEY(request_id) REFERENCES requests(id) ON DELETE CASCADE;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'policy_analyses_execution_record_id_fkey') THEN
        ALTER TABLE policy_analyses ADD CONSTRAINT policy_analyses_execution_record_id_fkey
            FOREIGN KEY(execution_record_id) REFERENCES execution_records(id) ON DELETE SET NULL;
    END IF;
END $$;

ALTER TABLE policy_analyses DROP CONSTRAINT IF EXISTS policy_analyses_url_key;
CREATE UNIQUE INDEX IF NOT EXISTS policy_analyses_profile_request_url_uidx
    ON policy_analyses(profile_id, request_id, url);
CREATE INDEX IF NOT EXISTS policy_analyses_profile_request_created_idx
    ON policy_analyses(profile_id, request_id, created_at DESC);
