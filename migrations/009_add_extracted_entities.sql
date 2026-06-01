-- Migration: Add extracted_entities column to received_data table
-- Stores structured GDPR entities extracted via LangExtract
-- This is separate from the ONSIT extraction pipeline

ALTER TABLE received_data
ADD COLUMN IF NOT EXISTS extracted_entities JSONB DEFAULT NULL;

-- Index for querying by entity class
CREATE INDEX IF NOT EXISTS idx_received_data_extracted_entities
ON received_data USING GIN (extracted_entities);

COMMENT ON COLUMN received_data.extracted_entities IS 'Structured GDPR entities extracted via LangExtract (JSON array of {entity_class, text, start_offset, end_offset, attributes, confidence})';
