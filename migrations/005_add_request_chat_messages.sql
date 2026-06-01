-- Migration: Add request chat messages table
-- Purpose: Store AI chat conversations for each access request

CREATE TABLE IF NOT EXISTS request_chat_messages (
    id SERIAL PRIMARY KEY,
    request_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT fk_request
        FOREIGN KEY (request_id)
        REFERENCES access_requests(id)
        ON DELETE CASCADE
);

-- Create index for faster queries
CREATE INDEX IF NOT EXISTS idx_request_chat_messages_request_id 
    ON request_chat_messages(request_id);

-- Create index for timestamp ordering
CREATE INDEX IF NOT EXISTS idx_request_chat_messages_timestamp 
    ON request_chat_messages(timestamp);

COMMENT ON TABLE request_chat_messages IS 'Stores AI chat conversations for access requests';
COMMENT ON COLUMN request_chat_messages.request_id IS 'References the access request this chat belongs to';
COMMENT ON COLUMN request_chat_messages.role IS 'Either user or assistant (AI)';
COMMENT ON COLUMN request_chat_messages.content IS 'The message content';
COMMENT ON COLUMN request_chat_messages.timestamp IS 'When the message was sent';
