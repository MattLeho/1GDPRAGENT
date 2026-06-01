-- Migration: Add user_profiles and id_documents tables for Settings

-- User Profiles table
CREATE TABLE IF NOT EXISTS user_profiles (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255),
    profile_picture_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_username ON user_profiles(username);

-- ID Documents table
CREATE TABLE IF NOT EXISTS id_documents (
    id SERIAL PRIMARY KEY,
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN ('passport', 'drivers_license', 'national_id', 'utility_bill')),
    file_name VARCHAR(500) NOT NULL,
    file_url TEXT NOT NULL,
    censored_url TEXT,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_id_documents_type ON id_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_id_documents_uploaded_at ON id_documents(uploaded_at DESC);

-- Comments for documentation
COMMENT ON TABLE user_profiles IS 'User profile information for local authentication and settings';
COMMENT ON TABLE id_documents IS 'Identity documents for GDPR verification with censored/uncensored versions';

COMMENT ON COLUMN user_profiles.password_hash IS 'bcrypt hashed password for local authentication';
COMMENT ON COLUMN user_profiles.profile_picture_url IS 'Path to uploaded profile picture';
COMMENT ON COLUMN id_documents.censored_url IS 'Path to auto-redacted version with sensitive info hidden';
