-- Task 5 Wave 2: local browser bridge pairing and replay ledger.

CREATE TABLE IF NOT EXISTS browser_bridge_pairings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_instance_id UUID NOT NULL REFERENCES connector_instances(id) ON DELETE RESTRICT,
    token_hash CHAR(64) NOT NULL UNIQUE CHECK(token_hash ~ '^[0-9a-f]{64}$'),
    label TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS browser_bridge_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pairing_id UUID NOT NULL REFERENCES browser_bridge_pairings(id) ON DELETE RESTRICT,
    message_id UUID NOT NULL,
    connector_instance_id UUID NOT NULL REFERENCES connector_instances(id) ON DELETE RESTRICT,
    protocol_version INTEGER NOT NULL CHECK(protocol_version=1),
    frame_hash CHAR(64) NOT NULL CHECK(frame_hash ~ '^[0-9a-f]{64}$'),
    status TEXT NOT NULL CHECK(status IN ('receiving','acknowledged','failed')),
    record_count INTEGER NOT NULL CHECK(record_count BETWEEN 1 AND 250),
    response JSONB,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    UNIQUE(pairing_id,message_id),
    CHECK(status<>'acknowledged' OR (response IS NOT NULL AND completed_at IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS browser_bridge_pairings_instance_idx
    ON browser_bridge_pairings(connector_instance_id,created_at DESC);
CREATE INDEX IF NOT EXISTS browser_bridge_messages_connector_idx
    ON browser_bridge_messages(connector_instance_id,received_at DESC);
