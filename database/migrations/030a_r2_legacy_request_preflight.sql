-- R2 preflight for partially created historical request tables.
--
-- Some supported installations predate the canonical baseline and already
-- have a minimal `requests` table. Because migration 001 intentionally uses
-- CREATE TABLE IF NOT EXISTS, it cannot fill columns missing from such a
-- table. Migration 031 reads these legacy operational columns during its safe
-- backfill and compatibility-view creation, so establish their shapes first.
-- No lifecycle or legal dates are inferred here.

ALTER TABLE requests ADD COLUMN IF NOT EXISTS progress INTEGER DEFAULT 0;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS data_volume_mb NUMERIC DEFAULT 0;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS next_action_date TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS deadline_date TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS data_period_start TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS data_period_end TIMESTAMPTZ;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS notes TEXT;
