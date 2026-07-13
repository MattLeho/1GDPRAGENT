DO $$ BEGIN CREATE TYPE ingestion_support_status AS ENUM ('SUPPORTED_DETERMINISTIC','SUPPORTED_WITH_OPTIONAL_SPECIALIST','METADATA_ONLY','QUARANTINED','UNSUPPORTED'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE ingestion_item_status AS ENUM ('pending','processing','completed','failed','quarantined','unsupported','ambiguous'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE schema_review_status AS ENUM ('unknown','proposed','approved','rejected','deprecated'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE pipeline_checkpoint_status AS ENUM ('pending','running','completed','failed','quarantined','skipped'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE OR REPLACE FUNCTION evidence_locator_shape_valid(locator_type evidence_locator_type, locator JSONB)
RETURNS BOOLEAN LANGUAGE SQL IMMUTABLE AS $$
SELECT CASE locator_type
  WHEN 'json_pointer' THEN jsonb_typeof(locator->'pointer')='string' AND (locator->>'pointer'='' OR locator->>'pointer' LIKE '/%')
  WHEN 'json_record' THEN jsonb_typeof(locator->'record')='number' AND (locator->>'record')::int>=0 AND (NOT locator?'pointer' OR locator->>'pointer'='' OR locator->>'pointer' LIKE '/%')
  WHEN 'csv_row' THEN jsonb_typeof(locator->'row')='number' AND (locator->>'row')::int>=1 AND NOT (locator?'column')
  WHEN 'csv_cell' THEN jsonb_typeof(locator->'row')='number' AND (locator->>'row')::int>=1 AND jsonb_typeof(locator->'column') IN ('string','number')
  WHEN 'text_span' THEN jsonb_typeof(locator->'byte_start')='number' AND jsonb_typeof(locator->'byte_end')='number' AND (locator->>'byte_start')::bigint>=0 AND (locator->>'byte_end')::bigint>(locator->>'byte_start')::bigint
  WHEN 'text_line' THEN jsonb_typeof(locator->'line')='number' AND (locator->>'line')::int>=1
  WHEN 'text_byte_span' THEN jsonb_typeof(locator->'byte_start')='number' AND jsonb_typeof(locator->'byte_end')='number' AND (locator->>'byte_start')::bigint>=0 AND (locator->>'byte_end')::bigint>(locator->>'byte_start')::bigint
  WHEN 'xml_element' THEN jsonb_typeof(locator->'xpath')='string' AND length(locator->>'xpath')>0
  WHEN 'html_dom_span' THEN jsonb_typeof(locator->'selector')='string' AND length(locator->>'selector')>0
  WHEN 'pdf_page_block' THEN jsonb_typeof(locator->'page')='number' AND (locator->>'page')::int>=1 AND jsonb_typeof(locator->'block')='number' AND (locator->>'block')::int>=0
  WHEN 'pdf_region' THEN jsonb_typeof(locator->'page')='number' AND (locator->>'page')::int>=1 AND (locator->>'width')::numeric>0 AND (locator->>'height')::numeric>0
  WHEN 'office_paragraph' THEN jsonb_typeof(locator->'paragraph')='number' AND (locator->>'paragraph')::int>=0
  WHEN 'office_table_cell' THEN jsonb_typeof(locator->'table')='number' AND jsonb_typeof(locator->'row')='number' AND jsonb_typeof(locator->'column')='number'
  WHEN 'spreadsheet_cell' THEN jsonb_typeof(locator->'sheet')='string' AND (locator->>'row')::int>=1 AND (locator->>'column')::int>=1
  WHEN 'slide_shape' THEN (locator->>'slide')::int>=1 AND (locator->>'shape')::int>=0
  WHEN 'slide_notes' THEN (locator->>'slide')::int>=1 AND COALESCE((locator->>'note')::int,0)>=0
  WHEN 'email_header' THEN (locator->>'message')::int>=0 AND jsonb_typeof(locator->'header')='string'
  WHEN 'email_mime_part' THEN (locator->>'message')::int>=0 AND jsonb_typeof(locator->'part')='string'
  WHEN 'email_attachment' THEN (locator->>'message')::int>=0 AND jsonb_typeof(locator->'part')='string'
  WHEN 'calendar_component' THEN jsonb_typeof(locator->'component')='string'
  WHEN 'vcard_property' THEN (locator->>'card')::int>=0 AND jsonb_typeof(locator->'property')='string'
  WHEN 'media_time_range' THEN (locator->>'start_ms')::bigint>=0 AND (locator->>'end_ms')::bigint>(locator->>'start_ms')::bigint
  WHEN 'image_region' THEN (locator->>'x')::numeric>=0 AND (locator->>'y')::numeric>=0 AND (locator->>'width')::numeric>0 AND (locator->>'height')::numeric>0
  WHEN 'video_frame' THEN (locator->>'timestamp_ms')::bigint>=0
  WHEN 'subtitle_cue' THEN (locator->>'cue')::int>=1 AND (locator->>'start_ms')::bigint>=0 AND (locator->>'end_ms')::bigint>(locator->>'start_ms')::bigint
  WHEN 'geospatial_feature' THEN jsonb_typeof(locator->'feature') IN ('string','number')
  WHEN 'database_table_row' THEN jsonb_typeof(locator->'table')='string' AND jsonb_typeof(locator->'row_key')='object'
  WHEN 'database_cell' THEN jsonb_typeof(locator->'table')='string' AND jsonb_typeof(locator->'row_key')='object' AND jsonb_typeof(locator->'column')='string'
  WHEN 'archive_member' THEN jsonb_typeof(locator->'member_path')='string' AND length(locator->>'member_path')>0
  ELSE FALSE END
$$;

CREATE TABLE IF NOT EXISTS format_support_registry (
    format_key TEXT PRIMARY KEY,
    family TEXT NOT NULL,
    probe_priority INTEGER NOT NULL DEFAULT 100 CHECK(probe_priority>=0),
    adapter_id TEXT,
    adapter_version TEXT,
    support_status ingestion_support_status NOT NULL,
    supported_extensions JSONB NOT NULL DEFAULT '[]',
    supported_mime_types JSONB NOT NULL DEFAULT '[]',
    magic_signatures JSONB NOT NULL DEFAULT '[]',
    task_routes JSONB NOT NULL DEFAULT '[]',
    capability_flags JSONB NOT NULL DEFAULT '[]',
    locator_types JSONB NOT NULL DEFAULT '[]',
    supports_streaming BOOLEAN NOT NULL DEFAULT FALSE,
    maximum_tested_fixture_size BIGINT CHECK(maximum_tested_fixture_size IS NULL OR maximum_tested_fixture_size>=0),
    system_dependencies JSONB NOT NULL DEFAULT '[]',
    security_notes JSONB NOT NULL DEFAULT '[]',
    known_unsupported_features JSONB NOT NULL DEFAULT '[]',
    fixture_ids JSONB NOT NULL DEFAULT '[]',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS structure_fingerprints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    fingerprint_hash CHAR(64) NOT NULL UNIQUE CHECK(fingerprint_hash ~ '^[0-9a-f]{64}$'),
    family TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    provider_version TEXT NOT NULL,
    canonical_shape JSONB NOT NULL,
    sample_count INTEGER NOT NULL DEFAULT 0 CHECK(sample_count>=0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS file_ingestion_records (
    artifact_id UUID PRIMARY KEY REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    status ingestion_item_status NOT NULL DEFAULT 'pending',
    support_status ingestion_support_status,
    detected_format TEXT,
    adapter_id TEXT,
    adapter_version TEXT,
    quarantine_reason TEXT,
    next_action TEXT,
    warnings JSONB NOT NULL DEFAULT '[]',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS declarative_parser_specs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parser_id TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    file_family TEXT NOT NULL,
    spec JSONB NOT NULL,
    spec_hash CHAR(64) NOT NULL CHECK(spec_hash ~ '^[0-9a-f]{64}$'),
    review_status schema_review_status NOT NULL DEFAULT 'proposed',
    proposed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    approved_at TIMESTAMPTZ,
    approved_by TEXT,
    UNIQUE(parser_id,parser_version),
    UNIQUE(spec_hash),
    CHECK(review_status<>'approved' OR (approved_at IS NOT NULL AND approved_by IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS schema_registry_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    structure_fingerprint_id UUID NOT NULL REFERENCES structure_fingerprints(id) ON DELETE RESTRICT,
    source_service TEXT,
    data_domain TEXT NOT NULL,
    file_family TEXT NOT NULL,
    parser_spec_id UUID NOT NULL REFERENCES declarative_parser_specs(id) ON DELETE RESTRICT,
    normalised_event_type TEXT NOT NULL,
    review_status schema_review_status NOT NULL DEFAULT 'unknown',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(structure_fingerprint_id,parser_spec_id)
);

CREATE TABLE IF NOT EXISTS schema_interpretation_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    structure_fingerprint_id UUID NOT NULL REFERENCES structure_fingerprints(id) ON DELETE RESTRICT,
    interpretation_version TEXT NOT NULL,
    execution_record_id UUID REFERENCES execution_records(id) ON DELETE RESTRICT,
    sample_manifest JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(structure_fingerprint_id,interpretation_version)
);

CREATE TABLE IF NOT EXISTS event_partitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    partition_key TEXT NOT NULL,
    storage_uri TEXT NOT NULL,
    file_hash CHAR(64) NOT NULL CHECK(file_hash ~ '^[0-9a-f]{64}$'),
    schema_version TEXT NOT NULL,
    row_count BIGINT NOT NULL CHECK(row_count>=0),
    min_occurred_at TIMESTAMPTZ,
    max_occurred_at TIMESTAMPTZ,
    byte_size BIGINT NOT NULL CHECK(byte_size>=0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(analysis_run_id,partition_key,file_hash)
);

CREATE TABLE IF NOT EXISTS activity_event_observations (
    event_id UUID NOT NULL,
    export_snapshot_id UUID NOT NULL REFERENCES export_snapshots(id) ON DELETE RESTRICT,
    artifact_id UUID NOT NULL REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    source_locator_id UUID NOT NULL REFERENCES evidence_locators(id) ON DELETE RESTRICT,
    record_signature CHAR(64) NOT NULL CHECK(record_signature ~ '^[0-9a-f]{64}$'),
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(event_id,export_snapshot_id,artifact_id,source_locator_id)
);

CREATE TABLE IF NOT EXISTS pipeline_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    stage TEXT NOT NULL CHECK(stage IN ('inventory','hashing','file_typing','family_extraction','fingerprinting','parsing','normalisation','feature_extraction','temporal_aggregation','assertion_generation','graph_projection')),
    item_key TEXT NOT NULL,
    idempotency_key CHAR(64) NOT NULL CHECK(idempotency_key ~ '^[0-9a-f]{64}$'),
    content_hash CHAR(64) CHECK(content_hash IS NULL OR content_hash ~ '^[0-9a-f]{64}$'),
    parser_version TEXT,
    status pipeline_checkpoint_status NOT NULL DEFAULT 'pending',
    attempt INTEGER NOT NULL DEFAULT 1 CHECK(attempt>=1),
    progress JSONB NOT NULL DEFAULT '{}',
    error JSONB,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(analysis_run_id,stage,item_key,idempotency_key)
);

CREATE TABLE IF NOT EXISTS temporal_states (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    subject_id TEXT NOT NULL,
    history_type TEXT NOT NULL CHECK(history_type IN ('personal_behavioural','controller_profile','system_understanding')),
    state_type TEXT NOT NULL,
    state_key TEXT NOT NULL,
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    controller_observed_from TIMESTAMPTZ,
    controller_observed_to TIMESTAMPTZ,
    system_asserted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    superseded_at TIMESTAMPTZ,
    dimensions JSONB NOT NULL,
    evidence_event_ids JSONB NOT NULL DEFAULT '[]',
    detector_id TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    CHECK(valid_to IS NULL OR valid_from IS NULL OR valid_to>=valid_from)
);

CREATE TABLE IF NOT EXISTS temporal_aggregates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    subject_id TEXT NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_key TEXT NOT NULL,
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,
    values JSONB NOT NULL,
    source_event_count BIGINT NOT NULL CHECK(source_event_count>=0),
    detector_id TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK(window_end IS NULL OR window_start IS NULL OR window_end>=window_start)
);

CREATE INDEX IF NOT EXISTS idx_file_ingestion_run_status ON file_ingestion_records(analysis_run_id,status);
CREATE INDEX IF NOT EXISTS idx_schema_registry_fingerprint ON schema_registry_entries(structure_fingerprint_id,review_status);
CREATE INDEX IF NOT EXISTS idx_event_partitions_run ON event_partitions(analysis_run_id,created_at);
CREATE INDEX IF NOT EXISTS idx_event_observations_signature ON activity_event_observations(record_signature);
CREATE INDEX IF NOT EXISTS idx_pipeline_checkpoints_run_stage ON pipeline_checkpoints(analysis_run_id,stage,status);
CREATE INDEX IF NOT EXISTS idx_temporal_states_asof ON temporal_states(subject_id,history_type,valid_from,valid_to);
CREATE INDEX IF NOT EXISTS idx_temporal_aggregates_window ON temporal_aggregates(subject_id,aggregate_type,window_start,window_end);

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='source_artifacts_structure_fingerprint_fk') THEN
    ALTER TABLE source_artifacts ADD CONSTRAINT source_artifacts_structure_fingerprint_fk FOREIGN KEY(structure_fingerprint_id) REFERENCES structure_fingerprints(id) ON DELETE RESTRICT;
  END IF;
END $$;
