-- Reconcile the historical settings schema without replacing existing UUID rows.
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS profile_picture_url TEXT;
UPDATE user_profiles SET profile_picture_url = avatar_url
WHERE profile_picture_url IS NULL AND avatar_url IS NOT NULL;

CREATE TABLE IF NOT EXISTS id_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN ('passport','drivers_license','national_id','utility_bill')),
    file_name VARCHAR(500) NOT NULL,
    file_url TEXT NOT NULL,
    censored_url TEXT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_id_documents_type ON id_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_id_documents_uploaded_at ON id_documents(uploaded_at DESC);

COMMENT ON TABLE user_profiles IS 'User profile information for local authentication and settings';
COMMENT ON TABLE id_documents IS 'Identity documents for GDPR verification with censored/uncensored versions';
