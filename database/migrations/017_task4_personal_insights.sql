-- Task 4 Personal Insights stores only versioned derived materialisations and
-- reviewable candidates. ActivityEvent Parquet, accepted Assertions and Task 3
-- temporal histories remain the canonical source evidence.
CREATE TABLE IF NOT EXISTS insight_materialisations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id TEXT NOT NULL,
    analysis_run_id UUID REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    temporal_mode TEXT NOT NULL CHECK(temporal_mode IN ('point_in_time','period','compare')),
    granularity TEXT NOT NULL CHECK(granularity IN ('day','week','month','quarter','year','custom')),
    from_at TIMESTAMPTZ,
    to_at TIMESTAMPTZ,
    point_at TIMESTAMPTZ,
    compare_from_at TIMESTAMPTZ,
    compare_to_at TIMESTAMPTZ,
    module_key TEXT NOT NULL,
    cache_key CHAR(64) NOT NULL CHECK(cache_key ~ '^[0-9a-f]{64}$'),
    source_partition_hashes JSONB NOT NULL DEFAULT '[]',
    payload JSONB NOT NULL,
    derivation_method TEXT NOT NULL,
    derivation_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(cache_key,derivation_version),
    CHECK((temporal_mode='point_in_time' AND point_at IS NOT NULL AND from_at IS NULL AND to_at IS NULL)
       OR (temporal_mode<>'point_in_time' AND point_at IS NULL AND from_at IS NOT NULL AND to_at IS NOT NULL AND to_at>from_at))
);

CREATE TABLE IF NOT EXISTS insight_aggregate_buckets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    materialisation_id UUID NOT NULL REFERENCES insight_materialisations(id) ON DELETE RESTRICT,
    subject_id TEXT NOT NULL,
    granularity TEXT NOT NULL CHECK(granularity IN ('day','week','month','quarter','year')),
    bucket_start TIMESTAMPTZ NOT NULL,
    bucket_end TIMESTAMPTZ NOT NULL,
    aggregate_type TEXT NOT NULL,
    aggregate_key TEXT NOT NULL,
    values JSONB NOT NULL,
    evidence_event_ids JSONB NOT NULL DEFAULT '[]',
    source_event_count BIGINT NOT NULL CHECK(source_event_count>=0),
    UNIQUE(materialisation_id,granularity,bucket_start,aggregate_type,aggregate_key),
    CHECK(bucket_end>bucket_start)
);

CREATE TABLE IF NOT EXISTS insight_evidence_index (
    insight_id UUID NOT NULL,
    materialisation_id UUID NOT NULL REFERENCES insight_materialisations(id) ON DELETE RESTRICT,
    evidence_kind TEXT NOT NULL CHECK(evidence_kind IN ('activity_event','assertion','temporal_state','source_artifact','evidence_locator','external_context_event','media_location_candidate')),
    evidence_ref_id UUID NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('supporting','exposure','comparison','contradicting','user_confirmation')),
    artifact_id UUID,
    locator_id UUID,
    occurred_at TIMESTAMPTZ,
    weight NUMERIC CHECK(weight IS NULL OR weight>=0),
    PRIMARY KEY(insight_id,evidence_kind,evidence_ref_id,role)
);

CREATE TABLE IF NOT EXISTS external_context_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    topics JSONB NOT NULL DEFAULT '[]',
    jurisdiction TEXT,
    source_uri TEXT,
    source_artifact_id UUID REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK(ended_at IS NULL OR ended_at>=occurred_at)
);

CREATE TABLE IF NOT EXISTS temporal_correlation_candidates (
    id UUID PRIMARY KEY,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    local_change_id UUID NOT NULL,
    external_event_id UUID NOT NULL REFERENCES external_context_events(id) ON DELETE RESTRICT,
    temporal_proximity NUMERIC NOT NULL CHECK(temporal_proximity>=0 AND temporal_proximity<=1),
    semantic_relevance NUMERIC NOT NULL CHECK(semantic_relevance>=0 AND semantic_relevance<=1),
    user_exposure_evidence JSONB NOT NULL DEFAULT '[]',
    direct_user_statement BOOLEAN NOT NULL DEFAULT FALSE,
    preceding_related_activity BOOLEAN NOT NULL DEFAULT FALSE,
    behavioural_persistence NUMERIC NOT NULL CHECK(behavioural_persistence>=0),
    competing_explanations_count INTEGER NOT NULL CHECK(competing_explanations_count>=0),
    status TEXT NOT NULL CHECK(status IN ('coincidence_candidate','possible_relation','evidence_supported_relation','user_confirmed','rejected')),
    detector_id TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    calculated_features JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK(status<>'evidence_supported_relation' OR jsonb_array_length(user_exposure_evidence)>0),
    CHECK(status<>'user_confirmed' OR direct_user_statement),
    UNIQUE(analysis_run_id,local_change_id,external_event_id,detector_version)
);

CREATE TABLE IF NOT EXISTS media_location_candidates (
    id UUID PRIMARY KEY,
    analysis_run_id UUID REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    artifact_id UUID NOT NULL REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    occurred_at TIMESTAMPTZ,
    temporal_precision TEXT NOT NULL,
    location_type TEXT,
    lat DOUBLE PRECISION CHECK(lat IS NULL OR (lat>=-90 AND lat<=90)),
    lon DOUBLE PRECISION CHECK(lon IS NULL OR (lon>=-180 AND lon<=180)),
    place_label TEXT,
    basis TEXT NOT NULL CHECK(basis IN ('exif_gps','takeout_sidecar','visual_landmark','user_confirmed')),
    confidence NUMERIC NOT NULL CHECK(confidence>=0 AND confidence<=1),
    evidence_class TEXT NOT NULL CHECK(evidence_class IN ('strong_observation','candidate','user_confirmed','rejected')),
    media_origin TEXT NOT NULL CHECK(media_origin IN ('camera_origin','screenshot','downloaded_media','edited_media','generated_media','unknown')),
    evidence_locator_id UUID NOT NULL REFERENCES evidence_locators(id) ON DELETE RESTRICT,
    detector_id TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    reviewed_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK(NOT(media_origin IN ('screenshot','downloaded_media','generated_media') AND evidence_class='strong_observation')),
    CHECK(NOT(basis='visual_landmark' AND evidence_class='strong_observation'))
);

CREATE TABLE IF NOT EXISTS insight_settings (
    singleton BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK(singleton),
    media_analysis_mode TEXT NOT NULL DEFAULT 'metadata_only' CHECK(media_analysis_mode IN ('metadata_only','selective_visual','full_visual')),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO insight_settings(singleton) VALUES(TRUE) ON CONFLICT(singleton) DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_insight_materialisations_subject_period ON insight_materialisations(subject_id,from_at,to_at,module_key);
CREATE INDEX IF NOT EXISTS idx_insight_evidence_ref ON insight_evidence_index(evidence_kind,evidence_ref_id);
CREATE INDEX IF NOT EXISTS idx_external_context_time ON external_context_events(occurred_at,event_type);
CREATE INDEX IF NOT EXISTS idx_media_location_artifact ON media_location_candidates(artifact_id,occurred_at);
