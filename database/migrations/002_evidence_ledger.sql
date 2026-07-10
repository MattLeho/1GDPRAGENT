-- Canonical immutable evidence and assertion ledger.
DO $$ BEGIN CREATE TYPE analysis_run_status AS ENUM ('pending','running','completed','failed','cancelled'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE source_type AS ENUM ('controller_export','takeout_export','dsar_response','manual_import'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE file_type_status AS ENUM ('declared','detected','matched','mismatch','unknown'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE evidence_locator_type AS ENUM ('json_pointer','csv_row','csv_cell','text_span','html_dom_span','media_time_range','image_region','archive_member'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE assertion_object_type AS ENUM ('node_ref','literal','json','unknown'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE assertion_type AS ENUM ('fact','relationship','classification','hypothesis'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE assertion_data_class AS ENUM ('declared','observed','derived','inferred'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE assertion_status AS ENUM ('candidate','accepted','rejected','superseded'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE epistemic_basis AS ENUM ('source_explicit','controller_assigned','deterministic_derivation','model_hypothesis','human_confirmed'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE temporal_precision AS ENUM ('exact','day','month','year','range','unknown'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS analysis_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_type TEXT NOT NULL,
    profile_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    request_id UUID REFERENCES requests(id) ON DELETE SET NULL,
    status analysis_run_status NOT NULL DEFAULT 'pending',
    pipeline_version TEXT NOT NULL,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS export_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_id UUID REFERENCES profiles(id) ON DELETE SET NULL,
    request_id UUID REFERENCES requests(id) ON DELETE SET NULL,
    controller_key TEXT,
    source_type source_type NOT NULL,
    exported_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS content_blobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sha256 CHAR(64) NOT NULL UNIQUE CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    byte_size BIGINT NOT NULL CHECK (byte_size >= 0),
    storage_uri TEXT NOT NULL,
    first_ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS source_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    export_snapshot_id UUID NOT NULL REFERENCES export_snapshots(id) ON DELETE RESTRICT,
    parent_artifact_id UUID REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    content_blob_id UUID NOT NULL REFERENCES content_blobs(id) ON DELETE RESTRICT,
    original_path TEXT NOT NULL,
    archive_member_path TEXT,
    file_name TEXT NOT NULL,
    declared_mime TEXT,
    detected_mime TEXT,
    extension TEXT,
    file_type_status file_type_status NOT NULL DEFAULT 'unknown',
    canonical_hash CHAR(64) CHECK (canonical_hash IS NULL OR canonical_hash ~ '^[0-9a-f]{64}$'),
    structure_fingerprint_id UUID,
    source_organisation TEXT,
    source_product TEXT,
    source_service TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(export_snapshot_id, original_path, archive_member_path)
);

CREATE OR REPLACE FUNCTION evidence_locator_shape_valid(locator_type evidence_locator_type, locator JSONB)
RETURNS BOOLEAN LANGUAGE SQL IMMUTABLE AS $$
SELECT CASE locator_type
  WHEN 'json_pointer' THEN jsonb_typeof(locator->'pointer') = 'string' AND (locator->>'pointer' = '' OR locator->>'pointer' LIKE '/%')
  WHEN 'csv_row' THEN jsonb_typeof(locator->'row') = 'number' AND (locator->>'row')::int >= 1 AND NOT (locator ? 'column')
  WHEN 'csv_cell' THEN jsonb_typeof(locator->'row') = 'number' AND (locator->>'row')::int >= 1 AND (jsonb_typeof(locator->'column') IN ('string','number'))
  WHEN 'text_span' THEN jsonb_typeof(locator->'byte_start') = 'number' AND jsonb_typeof(locator->'byte_end') = 'number' AND (locator->>'byte_start')::int >= 0 AND (locator->>'byte_end')::int > (locator->>'byte_start')::int
  WHEN 'html_dom_span' THEN jsonb_typeof(locator->'selector') = 'string' AND (NOT locator ? 'text_start' OR (locator->>'text_start')::int >= 0) AND (NOT locator ? 'text_end' OR (locator->>'text_end')::int > COALESCE((locator->>'text_start')::int, -1))
  WHEN 'media_time_range' THEN jsonb_typeof(locator->'start_ms') = 'number' AND jsonb_typeof(locator->'end_ms') = 'number' AND (locator->>'start_ms')::bigint >= 0 AND (locator->>'end_ms')::bigint > (locator->>'start_ms')::bigint
  WHEN 'image_region' THEN jsonb_typeof(locator->'x') = 'number' AND jsonb_typeof(locator->'y') = 'number' AND jsonb_typeof(locator->'width') = 'number' AND jsonb_typeof(locator->'height') = 'number' AND (locator->>'width')::numeric > 0 AND (locator->>'height')::numeric > 0
  WHEN 'archive_member' THEN jsonb_typeof(locator->'member_path') = 'string' AND length(locator->>'member_path') > 0
  ELSE FALSE END
$$;

CREATE TABLE IF NOT EXISTS evidence_locators (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    artifact_id UUID NOT NULL REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    locator_type evidence_locator_type NOT NULL,
    locator JSONB NOT NULL,
    raw_hash CHAR(64) NOT NULL CHECK (raw_hash ~ '^[0-9a-f]{64}$'),
    verified BOOLEAN NOT NULL DEFAULT FALSE,
    verification_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (evidence_locator_shape_valid(locator_type, locator))
);

CREATE TABLE IF NOT EXISTS assertions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_type TEXT NOT NULL,
    subject_ref TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object_type assertion_object_type NOT NULL,
    object_ref TEXT,
    object_value JSONB,
    assertion_type assertion_type NOT NULL,
    data_class assertion_data_class NOT NULL,
    status assertion_status NOT NULL DEFAULT 'candidate',
    epistemic_basis epistemic_basis NOT NULL,
    confidence NUMERIC CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    valid_from TIMESTAMPTZ,
    valid_to TIMESTAMPTZ,
    temporal_precision temporal_precision NOT NULL DEFAULT 'unknown',
    controller_observed_from TIMESTAMPTZ,
    controller_observed_to TIMESTAMPTZ,
    exported_at TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL,
    system_asserted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    superseded_at TIMESTAMPTZ,
    supersedes_assertion_id UUID REFERENCES assertions(id) ON DELETE RESTRICT,
    derivation_method TEXT NOT NULL,
    derivation_version TEXT NOT NULL,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    CHECK ((object_ref IS NOT NULL)::int + (object_value IS NOT NULL)::int = 1),
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
    CHECK (status <> 'superseded' OR superseded_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS assertion_evidence (
    assertion_id UUID NOT NULL REFERENCES assertions(id) ON DELETE RESTRICT,
    evidence_locator_id UUID NOT NULL REFERENCES evidence_locators(id) ON DELETE RESTRICT,
    PRIMARY KEY(assertion_id, evidence_locator_id)
);

CREATE TABLE IF NOT EXISTS assertion_derivations (
    assertion_id UUID NOT NULL REFERENCES assertions(id) ON DELETE RESTRICT,
    source_assertion_id UUID NOT NULL REFERENCES assertions(id) ON DELETE RESTRICT,
    PRIMARY KEY(assertion_id, source_assertion_id),
    CHECK (assertion_id <> source_assertion_id)
);

CREATE OR REPLACE FUNCTION enforce_assertion_semantic_immutability() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF ROW(OLD.subject_type,OLD.subject_ref,OLD.predicate,OLD.object_type,OLD.object_ref,OLD.object_value,OLD.assertion_type,OLD.data_class,OLD.epistemic_basis,OLD.confidence,OLD.valid_from,OLD.valid_to,OLD.temporal_precision,OLD.controller_observed_from,OLD.controller_observed_to,OLD.exported_at,OLD.ingested_at,OLD.derivation_method,OLD.derivation_version,OLD.analysis_run_id)
     IS DISTINCT FROM
     ROW(NEW.subject_type,NEW.subject_ref,NEW.predicate,NEW.object_type,NEW.object_ref,NEW.object_value,NEW.assertion_type,NEW.data_class,NEW.epistemic_basis,NEW.confidence,NEW.valid_from,NEW.valid_to,NEW.temporal_precision,NEW.controller_observed_from,NEW.controller_observed_to,NEW.exported_at,NEW.ingested_at,NEW.derivation_method,NEW.derivation_version,NEW.analysis_run_id) THEN
    RAISE EXCEPTION 'assertion semantic content is immutable; supersede it with a new assertion';
  END IF;
  IF OLD.status IN ('accepted','rejected','superseded') AND NEW.status NOT IN (OLD.status, 'superseded') THEN
    RAISE EXCEPTION 'terminal assertion status cannot be reopened';
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS assertion_semantic_immutability ON assertions;
CREATE TRIGGER assertion_semantic_immutability BEFORE UPDATE ON assertions FOR EACH ROW EXECUTE FUNCTION enforce_assertion_semantic_immutability();

CREATE OR REPLACE FUNCTION enforce_assertion_acceptance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE verified_count INTEGER;
BEGIN
  IF NEW.status = 'accepted' AND (TG_OP = 'INSERT' OR OLD.status IS DISTINCT FROM NEW.status) THEN
    IF NEW.derivation_method = '' OR NEW.derivation_version = '' THEN RAISE EXCEPTION 'accepted assertion requires derivation method and version'; END IF;
    SELECT count(*) INTO verified_count FROM assertion_evidence ae JOIN evidence_locators el ON el.id=ae.evidence_locator_id WHERE ae.assertion_id=NEW.id AND el.verified;
    IF NEW.epistemic_basis = 'model_hypothesis' AND verified_count = 0 THEN RAISE EXCEPTION 'model hypothesis requires verified evidence before acceptance'; END IF;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS assertion_acceptance_guard ON assertions;
CREATE CONSTRAINT TRIGGER assertion_acceptance_guard AFTER INSERT OR UPDATE OF status ON assertions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION enforce_assertion_acceptance();

CREATE INDEX IF NOT EXISTS idx_analysis_runs_request ON analysis_runs(request_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_artifacts_snapshot ON source_artifacts(export_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_evidence_locators_artifact ON evidence_locators(artifact_id);
CREATE INDEX IF NOT EXISTS idx_assertions_current ON assertions(subject_type, subject_ref, status);
CREATE INDEX IF NOT EXISTS idx_assertions_run ON assertions(analysis_run_id);
