-- Task 2: privacy-aware task execution, per-workflow routing, and secure connectors.
CREATE TABLE IF NOT EXISTS task_routes (
    task_key TEXT PRIMARY KEY,
    engine_id TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    execution_location TEXT NOT NULL CHECK (execution_location IN ('local','external','automatic')),
    fallback_chain JSONB NOT NULL DEFAULT '[]'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT true,
    max_concurrency INTEGER NOT NULL DEFAULT 1 CHECK (max_concurrency > 0),
    batch_size INTEGER NOT NULL DEFAULT 1 CHECK (batch_size > 0),
    timeout_ms INTEGER NOT NULL DEFAULT 30000 CHECK (timeout_ms BETWEEN 1000 AND 3600000),
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS processing_settings (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    processing_mode TEXT NOT NULL DEFAULT 'local_first'
        CHECK (processing_mode IN ('strict_local','local_first','controlled_cloud')),
    external_fallback_enabled BOOLEAN NOT NULL DEFAULT false,
    approved_external_engines JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO processing_settings(id) VALUES(1) ON CONFLICT(id) DO NOTHING;

CREATE TABLE IF NOT EXISTS workflow_preferences (
    workflow_key TEXT PRIMARY KEY,
    execution_mode TEXT NOT NULL DEFAULT 'built_in'
        CHECK (execution_mode IN ('built_in','n8n','hybrid','disabled')),
    enabled BOOLEAN NOT NULL DEFAULT true,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    fallback_order JSONB NOT NULL DEFAULT '["built_in"]'::jsonb,
    schedule JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- A legacy global choice becomes a safe initial preference for every core workflow.
WITH legacy AS (
  SELECT CASE workflow_backend
    WHEN 'n8n' THEN 'n8n'
    WHEN 'hybrid' THEN 'hybrid'
    ELSE 'built_in' END AS mode
  FROM model_preferences WHERE id=1
), workflows(workflow_key) AS (VALUES
 ('policy.acquisition'),('policy.analysis'),('request.drafting'),('email.sending'),
 ('email.connection_test'),('inbox.monitoring'),('response.classification'),
 ('response.attachment_detection'),('response.parsing'),('file.ingestion'),
 ('identity.ingestion'),('grounded.extraction'),('graph.projection'),
 ('graph.query'),('speech.transcription'),('vendor.ocr'),('policy.scanning'),
 ('makged.validation')
)
INSERT INTO workflow_preferences(workflow_key,execution_mode,fallback_order)
SELECT workflow_key, COALESCE(mode,'built_in'),
       CASE COALESCE(mode,'built_in') WHEN 'hybrid' THEN '["built_in","n8n"]'::jsonb
       WHEN 'n8n' THEN '["n8n"]'::jsonb ELSE '["built_in"]'::jsonb END
FROM workflows LEFT JOIN legacy ON true
ON CONFLICT(workflow_key) DO NOTHING;

CREATE TABLE IF NOT EXISTS execution_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_run_id UUID REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    task_key TEXT NOT NULL,
    workflow_key TEXT,
    engine_id TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    execution_location TEXT NOT NULL CHECK (execution_location IN ('local','external')),
    source_artifact_ids UUID[] NOT NULL DEFAULT '{}',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running'
        CHECK (status IN ('running','completed','failed','blocked')),
    input_size BIGINT,
    output_size BIGINT,
    error JSONB
);
CREATE INDEX IF NOT EXISTS idx_execution_records_external
    ON execution_records(execution_location,started_at DESC);
CREATE INDEX IF NOT EXISTS idx_execution_records_run
    ON execution_records(analysis_run_id,started_at DESC);

CREATE TABLE IF NOT EXISTS connector_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_key TEXT NOT NULL,
    account_key TEXT NOT NULL DEFAULT 'default',
    secret_ciphertext TEXT,
    encryption_version TEXT NOT NULL DEFAULT 'aes-256-gcm-v1',
    credential_version INTEGER NOT NULL DEFAULT 1,
    needs_reentry BOOLEAN NOT NULL DEFAULT false,
    rotated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(connector_key,account_key)
);

ALTER TABLE email_settings ADD COLUMN IF NOT EXISTS smtp_host TEXT;
ALTER TABLE email_settings ADD COLUMN IF NOT EXISTS smtp_port INTEGER DEFAULT 465;
ALTER TABLE email_settings ADD COLUMN IF NOT EXISTS smtp_secure BOOLEAN DEFAULT true;
ALTER TABLE email_settings ADD COLUMN IF NOT EXISTS credential_id UUID REFERENCES connector_credentials(id) ON DELETE SET NULL;
ALTER TABLE email_settings ADD COLUMN IF NOT EXISTS credential_status TEXT NOT NULL DEFAULT 'missing'
    CHECK (credential_status IN ('active','missing','needs_reentry'));
ALTER TABLE email_settings ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ;
ALTER TABLE email_settings ADD COLUMN IF NOT EXISTS next_sync_at TIMESTAMPTZ;
ALTER TABLE email_settings ADD COLUMN IF NOT EXISTS paused BOOLEAN NOT NULL DEFAULT false;

-- The old value was supplied by browser btoa(). It is explicitly quarantined, not
-- promoted into the encrypted credential store. Re-entry is required.
UPDATE email_settings
SET credential_status='needs_reentry', connection_verified=false
WHERE credential_id IS NULL AND NULLIF(password_encrypted,'') IS NOT NULL;

CREATE TABLE IF NOT EXISTS transcript_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_artifact_id UUID NOT NULL REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    execution_record_id UUID REFERENCES execution_records(id) ON DELETE RESTRICT,
    engine_id TEXT NOT NULL,
    model TEXT,
    language TEXT,
    segments JSONB NOT NULL DEFAULT '[]'::jsonb,
    words JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    transcript TEXT NOT NULL,
    derivation_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS outbound_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    workflow_key TEXT NOT NULL DEFAULT 'email.sending',
    transport TEXT NOT NULL,
    transport_message_id TEXT,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('queued','sent','failed')),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS inbox_checkpoints (
    connector_key TEXT NOT NULL,
    account_key TEXT NOT NULL DEFAULT 'default',
    last_uid BIGINT,
    last_checked_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'idle',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY(connector_key,account_key)
);
