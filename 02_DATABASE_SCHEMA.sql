-- ENABLE UUID EXTENSION
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- DROP EXISTING TABLES TO ENSURE SCHEMA UPDATE
DROP TABLE IF EXISTS received_data CASCADE;
DROP TABLE IF EXISTS messages CASCADE;
DROP TABLE IF EXISTS request_details CASCADE;
DROP TABLE IF EXISTS requests CASCADE;
DROP TABLE IF EXISTS policy_analyses CASCADE;
DROP VIEW IF EXISTS policy_analysis CASCADE;

-- 1. PROFILES (The User Identities)
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    identity_name TEXT NOT NULL, -- e.g. "Personal", "Work"
    encrypted_name TEXT,         -- AES Encrypted Real Name
    encrypted_email TEXT,        -- AES Encrypted Email
    encrypted_address TEXT,      -- AES Encrypted Address
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. REQUESTS (The Core Entity)
CREATE TABLE IF NOT EXISTS requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name TEXT NOT NULL,
    company_url TEXT,
    domain TEXT, -- for logos
    status TEXT DEFAULT 'draft', -- draft, scheduled, processing, action_required, completed
    request_type TEXT DEFAULT 'access', -- access, deletion, access+deletion
    progress INTEGER DEFAULT 0, -- 0-100
    data_volume_mb NUMERIC DEFAULT 0,
    next_action_date TIMESTAMP WITH TIME ZONE,
    deadline_date TIMESTAMP WITH TIME ZONE,
    data_period_start TIMESTAMP WITH TIME ZONE, -- Start of requested data period
    data_period_end TIMESTAMP WITH TIME ZONE,   -- End of requested data period
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. REQUEST_DETAILS (Account specific info for that company)
CREATE TABLE IF NOT EXISTS request_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    field_key TEXT,  -- e.g. "username", "phone"
    field_value_encrypted TEXT
);

-- 4. MESSAGES (History)
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    sender TEXT, -- 'user', 'agent', 'company'
    content TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 5. RECEIVED_DATA (Files with processing status)
CREATE TABLE IF NOT EXISTS received_data (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    original_name TEXT,
    file_path TEXT, -- Local storage path
    file_size_mb NUMERIC,
    file_type TEXT, -- MIME type
    category TEXT, -- pdf, audio, image, spreadsheet, document, other
    
    -- Processing status
    status TEXT DEFAULT 'pending', -- pending, processing, completed, error
    processing_stage TEXT, -- upload, extract, transcribe, analyze, ingest
    processing_progress INTEGER DEFAULT 0, -- 0-100
    
    -- Processed content
    extracted_text TEXT,
    markdown_content TEXT,
    transcript TEXT,
    
    -- AI analysis
    ai_summary TEXT,
    entities_extracted JSONB,
    graph_ingested BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    error_message TEXT,
    processing_started_at TIMESTAMP WITH TIME ZONE,
    processing_completed_at TIMESTAMP WITH TIME ZONE,
    date_received TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 6. EMAIL_SETTINGS (IMAP credentials for agent)
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

-- 7. POLICY_ANALYSES (Stored privacy policy analysis - unified table name)
CREATE TABLE IF NOT EXISTS policy_analyses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    url TEXT NOT NULL UNIQUE,
    domain TEXT NOT NULL,
    dpo_email TEXT,
    company_address TEXT,
    data_collected JSONB, -- Array of data types collected
    retention_period TEXT,
    third_party_sharing JSONB, -- Array of third parties
    summary TEXT,
    risk_score INTEGER DEFAULT 0,
    analysis_raw JSONB, -- Full raw analysis from LLM
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 8. POLICY_ANALYSIS (View for backwards compatibility with existing code)
CREATE OR REPLACE VIEW policy_analysis AS
SELECT 
    id,
    NULL::UUID as request_id, -- Legacy field
    url as company_url,
    dpo_email,
    company_address,
    data_collected,
    retention_period,
    third_party_sharing,
    analysis_raw,
    created_at as analyzed_at
FROM policy_analyses;

-- 9. REQUEST_EVENTS (Timeline tracking)
CREATE TABLE IF NOT EXISTS request_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL, -- 'created', 'email_sent', 'response_received', 'action_required', 'data_received', 'completed'
    event_description TEXT,
    event_date TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for faster event lookups
CREATE INDEX IF NOT EXISTS idx_request_events_request_id ON request_events(request_id);

-- 10. REQUEST_CHAT_MESSAGES (AI chat per request)
CREATE TABLE IF NOT EXISTS request_chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    sender TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_request_chat_messages_request_id ON request_chat_messages(request_id);

-- 11. VENDOR_LISTS (ONSIT vendor discovery and bulk GDPR outreach)
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

-- 12. AI_CREDENTIALS (encrypted provider keys saved from settings)
CREATE TABLE IF NOT EXISTS ai_credentials (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) UNIQUE NOT NULL,
    api_key_encrypted TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 13. MODEL_PREFERENCES (workflow backend and active model selection)
CREATE TABLE IF NOT EXISTS model_preferences (
    id INTEGER PRIMARY KEY DEFAULT 1,
    workflow_backend TEXT NOT NULL DEFAULT 'built_in',
    provider TEXT NOT NULL DEFAULT 'google',
    model TEXT NOT NULL DEFAULT 'gemini-2.5-flash',
    workflow_models JSONB NOT NULL DEFAULT '{
        "default": {"provider": "google", "model": "gemini-2.5-flash"},
        "rlm": {"provider": "google", "model": "gemini-2.5-flash"},
        "drafting": {"provider": "google", "model": "gemini-2.5-flash"},
        "extraction": {"provider": "google", "model": "gemini-2.5-flash-lite"},
        "graph": {"provider": "google", "model": "gemini-2.5-flash"},
        "policy": {"provider": "google", "model": "gemini-2.5-flash"}
    }'::jsonb,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT single_model_preferences_row CHECK (id = 1)
);

INSERT INTO model_preferences (id, workflow_backend, provider, model, workflow_models)
VALUES (
    1,
    'built_in',
    'google',
    'gemini-2.5-flash',
    '{
        "default": {"provider": "google", "model": "gemini-2.5-flash"},
        "rlm": {"provider": "google", "model": "gemini-2.5-flash"},
        "drafting": {"provider": "google", "model": "gemini-2.5-flash"},
        "extraction": {"provider": "google", "model": "gemini-2.5-flash-lite"},
        "graph": {"provider": "google", "model": "gemini-2.5-flash"},
        "policy": {"provider": "google", "model": "gemini-2.5-flash"}
    }'::jsonb
)
ON CONFLICT (id) DO NOTHING;
