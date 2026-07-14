-- Task 5 predecessor repair: bind local authenticated users to canonical evidence profiles.
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS default_profile_id UUID REFERENCES profiles(id) ON DELETE RESTRICT;

DO $$
DECLARE row RECORD; created_profile UUID;
BEGIN
  FOR row IN SELECT id,username FROM user_profiles WHERE default_profile_id IS NULL LOOP
    INSERT INTO profiles(identity_name) VALUES(row.username) RETURNING id INTO created_profile;
    UPDATE user_profiles SET default_profile_id=created_profile,updated_at=NOW() WHERE id=row.id;
  END LOOP;
END $$;

ALTER TABLE user_profiles ALTER COLUMN default_profile_id SET NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_profiles_default_profile ON user_profiles(default_profile_id);
