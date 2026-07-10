ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS legacy_integer_id BIGINT;
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_profiles_legacy_integer_id ON user_profiles(legacy_integer_id) WHERE legacy_integer_id IS NOT NULL;

DO $$
BEGIN
  IF to_regclass('public.user_profiles_legacy_integer') IS NOT NULL THEN
    INSERT INTO user_profiles(id,username,email,password_hash,avatar_url,profile_picture_url,created_at,updated_at,legacy_integer_id)
    SELECT gen_random_uuid(),username,email,COALESCE(password_hash,'legacy-password-reset-required'),
           COALESCE(avatar_url,profile_picture_url),profile_picture_url,
           COALESCE(created_at,NOW()),COALESCE(updated_at,NOW()),id
    FROM user_profiles_legacy_integer
    ON CONFLICT(username) DO NOTHING;
  END IF;

  IF to_regclass('public.user_documents_legacy_integer') IS NOT NULL THEN
    INSERT INTO user_documents(id,user_id,file_name,file_path,file_type,file_size,created_at)
    SELECT gen_random_uuid(),up.id,d.file_name,d.file_path,d.file_type,d.file_size,COALESCE(d.created_at,NOW())
    FROM user_documents_legacy_integer d JOIN user_profiles up ON up.legacy_integer_id=d.user_id
    WHERE NOT EXISTS(SELECT 1 FROM user_documents current WHERE current.user_id=up.id AND current.file_path=d.file_path);
  END IF;
END $$;
