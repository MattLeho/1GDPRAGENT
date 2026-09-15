-- SETTINGS-002 hardening: processing_settings has been one row per profile
-- since migration 034, but the migration-010 singleton guard `CHECK (id = 1)`
-- survives that migration. The first profile to save settings receives id 1
-- and the second receives id 2 from processing_settings_id_seq, which the
-- guard rejects, so a second profile could never persist processing settings.
--
-- Drop the singleton guard. Per-profile uniqueness is enforced by
-- processing_settings_profile_uidx (migration 034) and ownership by
-- processing_settings_profile_id_fkey. Idempotent.

DO $$
DECLARE
    guard RECORD;
BEGIN
    FOR guard IN
        SELECT conname
        FROM pg_constraint
        WHERE conrelid = 'public.processing_settings'::regclass
          AND contype = 'c'
          AND pg_get_constraintdef(oid) ~* '\(\s*id\s*=\s*1\s*\)'
    LOOP
        EXECUTE format('ALTER TABLE processing_settings DROP CONSTRAINT %I', guard.conname);
    END LOOP;
END $$;
