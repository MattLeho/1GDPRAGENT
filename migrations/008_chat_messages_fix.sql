-- Create compatibility view for chat messages migration
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

-- Now create chat messages table
CREATE TABLE IF NOT EXISTS request_chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID NOT NULL,
    sender TEXT NOT NULL, -- 'user' or 'assistant'
    message TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    FOREIGN KEY (request_id) REFERENCES requests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_request_chat_messages_request_id ON request_chat_messages(request_id);
