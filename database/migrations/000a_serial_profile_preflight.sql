-- Preserve installations that manually applied the historical SERIAL user_profiles migration.
DO $$
DECLARE id_type TEXT;
BEGIN
  SELECT data_type INTO id_type FROM information_schema.columns
  WHERE table_schema='public' AND table_name='user_profiles' AND column_name='id';
  IF id_type IN ('integer','bigint','smallint') THEN
    IF to_regclass('public.user_documents') IS NOT NULL THEN
      ALTER TABLE user_documents RENAME TO user_documents_legacy_integer;
    END IF;
    ALTER TABLE user_profiles RENAME TO user_profiles_legacy_integer;
    IF to_regclass('public.user_profiles_pkey') IS NOT NULL THEN ALTER INDEX user_profiles_pkey RENAME TO user_profiles_legacy_integer_pkey; END IF;
    IF to_regclass('public.user_profiles_username_key') IS NOT NULL THEN ALTER INDEX user_profiles_username_key RENAME TO user_profiles_legacy_integer_username_key; END IF;
    IF to_regclass('public.idx_user_profiles_username') IS NOT NULL THEN ALTER INDEX idx_user_profiles_username RENAME TO idx_user_profiles_legacy_integer_username; END IF;
  END IF;
END $$;
