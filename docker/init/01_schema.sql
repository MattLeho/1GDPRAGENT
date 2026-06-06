-- GDPR Agent - Complete Database Schema
-- This script runs automatically on first container start

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. PROFILES (The User Identities)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    identity_name TEXT NOT NULL,
    encrypted_name TEXT,
    encrypted_email TEXT,
    encrypted_address TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. USER_PROFILES (Authentication)
CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255),
    password_hash TEXT NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_username ON user_profiles(username);

-- 3. REQUESTS (The Core Entity)
CREATE TABLE IF NOT EXISTS requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name TEXT NOT NULL,
    company_url TEXT,
    domain TEXT,
    status TEXT DEFAULT 'draft',
    request_type TEXT DEFAULT 'access',
    progress INTEGER DEFAULT 0,
    data_volume_mb NUMERIC DEFAULT 0,
    next_action_date TIMESTAMP WITH TIME ZONE,
    deadline_date TIMESTAMP WITH TIME ZONE,
    data_period_start TIMESTAMP WITH TIME ZONE,
    data_period_end TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. REQUEST_DETAILS (Account specific info for that company)
CREATE TABLE IF NOT EXISTS request_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    field_key TEXT,
    field_value_encrypted TEXT
);

-- 5. MESSAGES (Activity History)
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    sender TEXT,
    content TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. RECEIVED_DATA (Files with processing status)
CREATE TABLE IF NOT EXISTS received_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    original_name TEXT,
    file_path TEXT,
    file_size_mb NUMERIC,
    file_type TEXT,
    category TEXT,
    status TEXT DEFAULT 'pending',
    processing_stage TEXT,
    processing_progress INTEGER DEFAULT 0,
    extracted_text TEXT,
    markdown_content TEXT,
    transcript TEXT,
    ai_summary TEXT,
    entities_extracted JSONB,
    graph_ingested BOOLEAN DEFAULT FALSE,
    error_message TEXT,
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    date_received TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_received_data_request_id ON received_data(request_id);

-- 7. EMAIL_SETTINGS
CREATE TABLE IF NOT EXISTS email_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT NOT NULL,
    password_encrypted TEXT NOT NULL,
    imap_host TEXT NOT NULL,
    imap_port INTEGER DEFAULT 993,
    connection_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 8. POLICY_ANALYSES
CREATE TABLE IF NOT EXISTS policy_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL,
    dpo_email TEXT,
    company_address TEXT,
    data_collected JSONB,
    retention_period TEXT,
    third_party_sharing JSONB,
    summary TEXT,
    risk_score INTEGER DEFAULT 0,
    analysis_raw JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 9. REQUEST_EVENTS (Timeline tracking)
CREATE TABLE IF NOT EXISTS request_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_description TEXT,
    event_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_request_events_request_id ON request_events(request_id);

-- 10. REQUEST_CHAT_MESSAGES (AI Chat per request)
CREATE TABLE IF NOT EXISTS request_chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    sender TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_request_chat_messages_request_id ON request_chat_messages(request_id);

-- 11. USER_DOCUMENTS (User document management)
CREATE TABLE IF NOT EXISTS user_documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT,
    file_size BIGINT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_documents_user_id ON user_documents(user_id);

-- 12. WORKFLOW_LOGS (N8N and processing logs)
CREATE TABLE IF NOT EXISTS workflow_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    workflow_name TEXT NOT NULL,
    workflow_type TEXT, -- 'n8n', 'file_processing', 'graph_ingestion'
    status TEXT DEFAULT 'started', -- 'started', 'running', 'completed', 'error'
    details JSONB,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_workflow_logs_request_id ON workflow_logs(request_id);

-- 13. APP_SETTINGS (Stored API credentials and settings)
CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    encrypted BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 14. VENDOR_LISTS (ONSIT vendor discovery and bulk GDPR outreach)
CREATE TABLE IF NOT EXISTS vendor_lists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vendor TEXT NOT NULL,
    company_name TEXT,
    domain TEXT,
    dpo_email TEXT,
    risk_level TEXT DEFAULT 'medium',
    source TEXT DEFAULT 'onsit',
    notes TEXT,
    gdpr_email_sent BOOLEAN DEFAULT FALSE,
    gdpr_email_sent_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vendor_lists_domain ON vendor_lists(domain);
CREATE INDEX IF NOT EXISTS idx_vendor_lists_gdpr_sent ON vendor_lists(gdpr_email_sent);

-- 15. AI_CREDENTIALS (encrypted provider keys saved from settings)
CREATE TABLE IF NOT EXISTS ai_credentials (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) UNIQUE NOT NULL,
    api_key_encrypted TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 16. MODEL_PREFERENCES (workflow backend and active model selection)
CREATE TABLE IF NOT EXISTS model_preferences (
    id INTEGER PRIMARY KEY DEFAULT 1,
    workflow_backend TEXT NOT NULL DEFAULT 'built_in',
    provider TEXT NOT NULL DEFAULT 'google',
    model TEXT NOT NULL DEFAULT 'flash_latest',
    workflow_models JSONB NOT NULL DEFAULT '{
        "default": {"provider": "google", "model": "flash_latest"},
        "rlm": {"provider": "google", "model": "flash_latest"},
        "drafting": {"provider": "google", "model": "flash_latest"},
        "extraction": {"provider": "google", "model": "flash_lite_latest"},
        "graph": {"provider": "google", "model": "flash_latest"},
        "policy": {"provider": "google", "model": "flash_latest"}
    }'::jsonb,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT single_model_preferences_row CHECK (id = 1)
);

INSERT INTO model_preferences (id, workflow_backend, provider, model, workflow_models)
VALUES (
    1,
    'built_in',
    'google',
    'flash_latest',
    '{
        "default": {"provider": "google", "model": "flash_latest"},
        "rlm": {"provider": "google", "model": "flash_latest"},
        "drafting": {"provider": "google", "model": "flash_latest"},
        "extraction": {"provider": "google", "model": "flash_lite_latest"},
        "graph": {"provider": "google", "model": "flash_latest"},
        "policy": {"provider": "google", "model": "flash_latest"}
    }'::jsonb
)
ON CONFLICT (id) DO NOTHING;

-- 17. DATA_ARTIFACTS (request-scoped visualizable outputs)
CREATE TABLE IF NOT EXISTS data_artifacts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    file_id UUID REFERENCES received_data(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    title TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence NUMERIC DEFAULT 1.0,
    source_span TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_data_artifacts_request_id ON data_artifacts(request_id);
CREATE INDEX IF NOT EXISTS idx_data_artifacts_file_id ON data_artifacts(file_id);
CREATE INDEX IF NOT EXISTS idx_data_artifacts_type ON data_artifacts(artifact_type);

-- Create access_requests view for compatibility
CREATE OR REPLACE VIEW access_requests AS
SELECT 
    id,
    company_name,
    company_url,
    domain,
    status,
    request_type,
    created_at
FROM requests;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO admin;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO admin;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'GDPR Agent database schema initialized successfully!';
END $$;
