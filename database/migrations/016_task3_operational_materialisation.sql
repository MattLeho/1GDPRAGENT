-- Task 3 predecessor repair: make deterministic feature and temporal stages
-- operational in the canonical ingestion pipeline. All outputs are versioned
-- derivations; ActivityEvent Parquet remains the raw behavioural truth.
CREATE TABLE IF NOT EXISTS temporal_materialisation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    partition_file_hash CHAR(64) NOT NULL CHECK(partition_file_hash ~ '^[0-9a-f]{64}$'),
    derivation_method TEXT NOT NULL,
    derivation_version TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('running','completed','failed')),
    event_count BIGINT NOT NULL DEFAULT 0 CHECK(event_count>=0),
    feature_count BIGINT NOT NULL DEFAULT 0 CHECK(feature_count>=0),
    aggregate_count BIGINT NOT NULL DEFAULT 0 CHECK(aggregate_count>=0),
    state_count BIGINT NOT NULL DEFAULT 0 CHECK(state_count>=0),
    error JSONB,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    UNIQUE(analysis_run_id,partition_file_hash,derivation_version)
);

CREATE TABLE IF NOT EXISTS deterministic_feature_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    materialisation_run_id UUID NOT NULL REFERENCES temporal_materialisation_runs(id) ON DELETE RESTRICT,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    feature_key CHAR(64) NOT NULL CHECK(feature_key ~ '^[0-9a-f]{64}$'),
    feature_type TEXT NOT NULL,
    detector_id TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    candidate_status TEXT NOT NULL,
    calculated_values JSONB NOT NULL,
    confidence NUMERIC,
    rule_result BOOLEAN,
    source_event_ids JSONB NOT NULL DEFAULT '[]',
    source_artifact_ids JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(analysis_run_id,feature_key)
);

ALTER TABLE temporal_aggregates
    ADD COLUMN IF NOT EXISTS materialisation_run_id UUID REFERENCES temporal_materialisation_runs(id) ON DELETE RESTRICT;
ALTER TABLE temporal_states
    ADD COLUMN IF NOT EXISTS materialisation_run_id UUID REFERENCES temporal_materialisation_runs(id) ON DELETE RESTRICT;
ALTER TABLE temporal_episodes
    ADD COLUMN IF NOT EXISTS materialisation_run_id UUID REFERENCES temporal_materialisation_runs(id) ON DELETE RESTRICT;
ALTER TABLE personal_eras
    ADD COLUMN IF NOT EXISTS materialisation_run_id UUID REFERENCES temporal_materialisation_runs(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_feature_candidates_run_type
    ON deterministic_feature_candidates(analysis_run_id,feature_type);
CREATE INDEX IF NOT EXISTS idx_temporal_materialisation_run
    ON temporal_materialisation_runs(analysis_run_id,status);
