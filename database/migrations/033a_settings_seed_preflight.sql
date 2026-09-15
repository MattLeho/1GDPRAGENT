-- SETTINGS-002 preflight: remove the ownerless default scaffold row before
-- migration 034 makes processing_settings profile-owned.
--
-- Migration 010 unconditionally seeds `processing_settings(id = 1)` as a
-- global singleton. On a clean install no profile exists yet, and on a
-- multi-profile installation the row belongs to nobody, so migration 034
-- correctly fails closed with "cannot infer canonical ownership".
--
-- A row that still carries every migration-010 default value is
-- indistinguishable from "no row": the runtime returns the same defaults for a
-- profile that has no processing_settings row. Removing such a row therefore
-- loses no configuration and never assigns ownership. A singleton that was
-- modified is left for migration 034, which assigns it only when exactly one
-- profile exists and otherwise fails closed.
--
-- Idempotent, and safe on installations where 034 has already run: rows that
-- are owned by a profile are never touched.

DO $$
DECLARE
    has_profile_column BOOLEAN;
    pristine_filter CONSTANT TEXT :=
        'processing_mode = ''local_first'' '
        'AND external_fallback_enabled = false '
        'AND approved_external_engines = ''[]''::jsonb';
BEGIN
    IF to_regclass('public.processing_settings') IS NULL THEN
        RETURN;
    END IF;

    SELECT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'processing_settings'
          AND column_name = 'profile_id'
    ) INTO has_profile_column;

    IF has_profile_column THEN
        EXECUTE 'DELETE FROM processing_settings WHERE profile_id IS NULL AND ' || pristine_filter;
    ELSE
        EXECUTE 'DELETE FROM processing_settings WHERE ' || pristine_filter;
    END IF;
END $$;
