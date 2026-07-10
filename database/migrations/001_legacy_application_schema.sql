-- Canonical baseline for existing GDPR Agent application data.
-- Idempotent and non-destructive: this migration never drops user tables or rows.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    identity_name TEXT NOT NULL,
    encrypted_name TEXT,
    encrypted_email TEXT,
    encrypted_address TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255),
    password_hash TEXT NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name TEXT NOT NULL,
    company_url TEXT,
    domain TEXT,
    status TEXT DEFAULT 'draft',
    request_type TEXT DEFAULT 'access',
    progress INTEGER DEFAULT 0,
    data_volume_mb NUMERIC DEFAULT 0,
    next_action_date TIMESTAMPTZ,
    deadline_date TIMESTAMPTZ,
    data_period_start TIMESTAMPTZ,
    data_period_end TIMESTAMPTZ,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS request_details (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    field_key TEXT,
    field_value_encrypted TEXT
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    sender TEXT,
    content TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS received_data (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    processing_started_at TIMESTAMPTZ,
    processing_completed_at TIMESTAMPTZ,
    date_received TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS extracted_entities JSONB;

CREATE TABLE IF NOT EXISTS email_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    password_encrypted TEXT NOT NULL,
    imap_host TEXT NOT NULL,
    imap_port INTEGER DEFAULT 993,
    connection_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS policy_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS request_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    event_type TEXT NOT NULL,
    event_description TEXT,
    event_date TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS request_chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    sender TEXT NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES user_profiles(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_type TEXT,
    file_size BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS id_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_type VARCHAR(50) NOT NULL CHECK (document_type IN ('passport','drivers_license','national_id','utility_bill')),
    file_name VARCHAR(500) NOT NULL,
    file_url TEXT NOT NULL,
    censored_url TEXT,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    workflow_name TEXT NOT NULL,
    workflow_type TEXT,
    status TEXT DEFAULT 'started',
    details JSONB,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    encrypted BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS vendor_lists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor TEXT NOT NULL,
    company_name TEXT,
    domain TEXT,
    dpo_email TEXT,
    risk_level TEXT DEFAULT 'medium',
    source TEXT DEFAULT 'onsit',
    notes TEXT,
    gdpr_email_sent BOOLEAN DEFAULT FALSE,
    gdpr_email_sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ai_credentials (
    id SERIAL PRIMARY KEY,
    provider VARCHAR(50) UNIQUE NOT NULL,
    api_key_encrypted TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_preferences (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    workflow_backend TEXT NOT NULL DEFAULT 'built_in',
    provider TEXT NOT NULL DEFAULT 'google',
    model TEXT NOT NULL DEFAULT 'flash_latest',
    workflow_models JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE model_preferences ADD COLUMN IF NOT EXISTS workflow_models JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS request_threads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Request conversation',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS n8n_webhooks (
    id SERIAL PRIMARY KEY,
    workflow_key TEXT UNIQUE NOT NULL,
    webhook_url TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE VIEW access_requests AS
SELECT id, company_name, company_url, domain, status, request_type, created_at FROM requests;

CREATE INDEX IF NOT EXISTS idx_received_data_request_id ON received_data(request_id);
CREATE INDEX IF NOT EXISTS idx_received_data_extracted_entities ON received_data USING GIN(extracted_entities);
CREATE INDEX IF NOT EXISTS idx_request_events_request_id ON request_events(request_id);
CREATE INDEX IF NOT EXISTS idx_request_chat_messages_request_id ON request_chat_messages(request_id);
CREATE INDEX IF NOT EXISTS idx_workflow_logs_request_id ON workflow_logs(request_id);
CREATE INDEX IF NOT EXISTS idx_vendor_lists_domain ON vendor_lists(domain);
