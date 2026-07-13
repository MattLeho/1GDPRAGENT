CREATE TABLE IF NOT EXISTS extraction_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    artifact_id UUID NOT NULL REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    unit_key TEXT NOT NULL,
    unit_type TEXT NOT NULL,
    ordinal BIGINT NOT NULL CHECK(ordinal>=0),
    parent_unit_key TEXT,
    text_value TEXT,
    scalar_value JSONB,
    structured_payload JSONB,
    metadata JSONB NOT NULL DEFAULT '{}',
    evidence_locator_id UUID NOT NULL REFERENCES evidence_locators(id) ON DELETE RESTRICT,
    adapter_id TEXT NOT NULL,
    adapter_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(analysis_run_id,artifact_id,adapter_id,adapter_version,unit_key)
);

CREATE TABLE IF NOT EXISTS specialist_task_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    artifact_id UUID NOT NULL REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    task_key TEXT NOT NULL CHECK(task_key IN (
      'document.ocr','image.ocr','image.origin_classification','image.caption',
      'image.landmark_candidate','speech.transcription','speech.translation','speech.diarisation',
      'schema.interpretation','semantic.adjudication'
    )),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','completed','failed','blocked','skipped')),
    input_manifest JSONB NOT NULL,
    execution_record_id UUID REFERENCES execution_records(id) ON DELETE RESTRICT,
    output_manifest JSONB,
    error JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    UNIQUE(analysis_run_id,artifact_id,task_key)
);

ALTER TABLE received_data ADD COLUMN IF NOT EXISTS original_name TEXT;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS file_path TEXT;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS file_size_mb NUMERIC;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS file_type TEXT;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS category TEXT;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS processing_stage TEXT;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS processing_progress INTEGER DEFAULT 0;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS extracted_text TEXT;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS markdown_content TEXT;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS transcript TEXT;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS ai_summary TEXT;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS entities_extracted JSONB;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS processing_started_at TIMESTAMPTZ;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS processing_completed_at TIMESTAMPTZ;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS derived_content_basis TEXT;
ALTER TABLE received_data ADD COLUMN IF NOT EXISTS provenance_status TEXT;
UPDATE received_data SET
  derived_content_basis=COALESCE(derived_content_basis,'legacy_model_summary'),
  provenance_status=COALESCE(provenance_status,'unverified_legacy')
WHERE ai_summary IS NOT NULL;

DO $$
DECLARE table_name TEXT;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['extraction_units','specialist_task_requests']
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I','trg_'||table_name||'_append_only',table_name);
    EXECUTE format('CREATE TRIGGER %I BEFORE DELETE ON %I FOR EACH ROW EXECUTE FUNCTION prevent_task3_provenance_mutation()','trg_'||table_name||'_append_only',table_name);
  END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS idx_extraction_units_artifact ON extraction_units(artifact_id,unit_type,ordinal);
CREATE INDEX IF NOT EXISTS idx_specialist_tasks_run_status ON specialist_task_requests(analysis_run_id,status,task_key);
