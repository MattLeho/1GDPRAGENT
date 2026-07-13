-- Task 5 Wave 3: encrypted, explicitly reviewed built-in email transport drafts.

CREATE TABLE IF NOT EXISTS email_transport_drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES requests(id) ON DELETE SET NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_ciphertext TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','reviewed','sent','failed')),
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    transport_message_id TEXT,
    error JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    CHECK((status='draft' AND reviewed_at IS NULL AND reviewed_by IS NULL)
       OR (status IN ('reviewed','sent','failed') AND reviewed_at IS NOT NULL AND reviewed_by IS NOT NULL)),
    CHECK(status<>'sent' OR (sent_at IS NOT NULL AND transport_message_id IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS email_transport_drafts_status_idx
    ON email_transport_drafts(status,created_at DESC);
