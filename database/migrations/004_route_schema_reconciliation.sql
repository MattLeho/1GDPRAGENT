-- Reconcile schemas formerly created lazily by application routes.
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS profile_picture_url TEXT;

ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS company VARCHAR(255);
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS domain VARCHAR(255);
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS thread_id UUID DEFAULT gen_random_uuid();
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS policy_url TEXT;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS policy_markdown TEXT;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS policy_summary TEXT;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS dpo_email VARCHAR(255);
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS compliance_score INTEGER;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS request_type VARCHAR(50);
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS draft_subject TEXT;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS draft_body TEXT;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS drafted_at TIMESTAMPTZ;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS sent_at TIMESTAMPTZ;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS sent_via VARCHAR(50) DEFAULT 'n8n';
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS email_status VARCHAR(50);
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS response_received_at TIMESTAMPTZ;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS response_content TEXT;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS response_summary TEXT;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS follow_up_needed BOOLEAN DEFAULT false;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS follow_up_reason TEXT;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS follow_up_sent_at TIMESTAMPTZ;
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'initialized';
ALTER TABLE request_threads ADD COLUMN IF NOT EXISTS conversation_history JSONB DEFAULT '[]'::jsonb;
CREATE UNIQUE INDEX IF NOT EXISTS uq_request_threads_thread_id ON request_threads(thread_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_request_threads_company_domain ON request_threads(lower(company),COALESCE(domain,'')) WHERE company IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_threads_status ON request_threads(status);

ALTER TABLE n8n_webhooks ADD COLUMN IF NOT EXISTS webhook_name VARCHAR(100);
ALTER TABLE n8n_webhooks ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
ALTER TABLE n8n_webhooks ALTER COLUMN workflow_key DROP NOT NULL;
UPDATE n8n_webhooks SET webhook_name=COALESCE(webhook_name,workflow_key) WHERE webhook_name IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_n8n_webhooks_name ON n8n_webhooks(webhook_name);

INSERT INTO model_preferences(id,workflow_backend,provider,model,workflow_models)
VALUES(1,'built_in','google','flash_latest','{}'::jsonb) ON CONFLICT(id) DO NOTHING;
