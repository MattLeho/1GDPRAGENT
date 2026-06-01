-- Migration: Add vendor tracking columns
-- Purpose: Track GDPR email status for vendors

ALTER TABLE vendor_lists 
ADD COLUMN IF NOT EXISTS gdpr_email_sent BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS gdpr_email_sent_at TIMESTAMP;

-- Create index for tracking
CREATE INDEX IF NOT EXISTS idx_vendor_lists_gdpr_sent 
    ON vendor_lists(gdpr_email_sent);

COMMENT ON COLUMN vendor_lists.gdpr_email_sent IS 'Whether GDPR request email has been sent to this vendor';
COMMENT ON COLUMN vendor_lists.gdpr_email_sent_at IS 'Timestamp when GDPR email was sent';
