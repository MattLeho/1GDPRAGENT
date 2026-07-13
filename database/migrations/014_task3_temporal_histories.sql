-- Task 3 Wave 5: preserve every temporal axis and keep derived histories append-only.
ALTER TABLE temporal_states ADD COLUMN IF NOT EXISTS occurred_at TIMESTAMPTZ;
ALTER TABLE temporal_states ADD COLUMN IF NOT EXISTS exported_at TIMESTAMPTZ;
ALTER TABLE temporal_states ADD COLUMN IF NOT EXISTS ingested_at TIMESTAMPTZ;

ALTER TABLE temporal_aggregates ADD COLUMN IF NOT EXISTS history_type TEXT;
UPDATE temporal_aggregates SET history_type='system_understanding' WHERE history_type IS NULL;
ALTER TABLE temporal_aggregates ALTER COLUMN history_type SET NOT NULL;
DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='temporal_aggregates_history_type_check') THEN
    ALTER TABLE temporal_aggregates ADD CONSTRAINT temporal_aggregates_history_type_check
    CHECK(history_type IN ('personal_behavioural','controller_profile','system_understanding'));
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS temporal_topic_assignments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    topic_id TEXT NOT NULL,
    topic_path JSONB NOT NULL,
    source_event_ids JSONB NOT NULL,
    assignment_method TEXT NOT NULL,
    assignment_version TEXT NOT NULL,
    confidence NUMERIC NOT NULL CHECK(confidence>=0 AND confidence<=1),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS temporal_episodes (
    id UUID PRIMARY KEY,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    subject_id TEXT NOT NULL,
    history_type TEXT NOT NULL CHECK(history_type IN ('personal_behavioural','controller_profile','system_understanding')),
    episode_kind TEXT NOT NULL CHECK(episode_kind IN ('ProjectEpisodeCandidate','TopicClusterEpisodeCandidate')),
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    evidence_event_ids JSONB NOT NULL,
    detector_id TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK(end_at>=start_at)
);

CREATE TABLE IF NOT EXISTS personal_eras (
    id UUID PRIMARY KEY,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    subject_id TEXT NOT NULL,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ NOT NULL,
    monthly_feature_vectors JSONB NOT NULL,
    change_point_indices JSONB NOT NULL,
    evidence_event_ids JSONB NOT NULL,
    detector_id TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK(end_at>=start_at)
);

CREATE TABLE IF NOT EXISTS personal_era_labels (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    era_id UUID NOT NULL REFERENCES personal_eras(id) ON DELETE RESTRICT,
    label_source TEXT NOT NULL CHECK(label_source IN ('machine','human')),
    label TEXT NOT NULL,
    execution_record_id UUID REFERENCES execution_records(id) ON DELETE RESTRICT,
    labelled_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK((label_source='machine' AND execution_record_id IS NOT NULL) OR (label_source='human' AND labelled_by IS NOT NULL))
);

CREATE TABLE IF NOT EXISTS export_snapshot_deltas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    before_snapshot_id UUID NOT NULL REFERENCES export_snapshots(id) ON DELETE RESTRICT,
    after_snapshot_id UUID NOT NULL REFERENCES export_snapshots(id) ON DELETE RESTRICT,
    entity_type TEXT NOT NULL CHECK(entity_type IN ('assertion','schema','event_observation')),
    entity_key TEXT NOT NULL,
    delta_status TEXT NOT NULL CHECK(delta_status IN ('NEW','REMOVED_FROM_EXPORT','UNCHANGED','MODIFIED')),
    drift_type TEXT NOT NULL CHECK(drift_type IN ('PERSONAL_DRIFT','CONTROLLER_DRIFT','UNDERSTANDING_DRIFT')),
    before_value JSONB,
    after_value JSONB,
    interpretation TEXT NOT NULL DEFAULT 'newly observed by this system',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(before_snapshot_id,after_snapshot_id,entity_type,entity_key)
);

CREATE OR REPLACE VIEW current_temporal_states AS
SELECT * FROM temporal_states
WHERE superseded_at IS NULL
  AND (valid_from IS NULL OR valid_from<=NOW())
  AND (valid_to IS NULL OR valid_to>NOW());

CREATE OR REPLACE FUNCTION temporal_states_as_of(
    subject_key TEXT,
    valid_as_of TIMESTAMPTZ,
    system_as_of TIMESTAMPTZ,
    requested_history TEXT DEFAULT NULL
) RETURNS SETOF temporal_states LANGUAGE SQL STABLE AS $$
SELECT state.* FROM temporal_states state
WHERE state.subject_id=subject_key
  AND (requested_history IS NULL OR state.history_type=requested_history)
  AND state.system_asserted_at<=system_as_of
  AND (state.superseded_at IS NULL OR state.superseded_at>system_as_of)
  AND (state.valid_from IS NULL OR state.valid_from<=valid_as_of)
  AND (state.valid_to IS NULL OR state.valid_to>valid_as_of)
ORDER BY state.history_type,state.state_type,state.state_key,state.system_asserted_at
$$;

CREATE OR REPLACE FUNCTION prevent_temporal_state_overwrite()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP='UPDATE' AND OLD.superseded_at IS NULL AND NEW.superseded_at IS NOT NULL
     AND (to_jsonb(NEW)-'superseded_at')=(to_jsonb(OLD)-'superseded_at') THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'temporal state history is append-only; only one-time supersession is allowed';
END $$;

DROP TRIGGER IF EXISTS trg_temporal_states_history_guard ON temporal_states;
CREATE TRIGGER trg_temporal_states_history_guard
BEFORE UPDATE OR DELETE ON temporal_states
FOR EACH ROW EXECUTE FUNCTION prevent_temporal_state_overwrite();

DO $$
DECLARE table_name TEXT;
BEGIN
  FOREACH table_name IN ARRAY ARRAY['temporal_aggregates','temporal_topic_assignments','temporal_episodes','personal_eras','personal_era_labels','export_snapshot_deltas']
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I','trg_'||table_name||'_append_only',table_name);
    EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION prevent_task3_provenance_mutation()','trg_'||table_name||'_append_only',table_name);
  END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS idx_temporal_states_history_axes ON temporal_states(subject_id,history_type,valid_from,valid_to,system_asserted_at,superseded_at);
CREATE INDEX IF NOT EXISTS idx_temporal_episodes_subject_time ON temporal_episodes(subject_id,start_at,end_at);
CREATE INDEX IF NOT EXISTS idx_personal_eras_subject_time ON personal_eras(subject_id,start_at,end_at);
CREATE INDEX IF NOT EXISTS idx_export_snapshot_deltas_pair ON export_snapshot_deltas(before_snapshot_id,after_snapshot_id,drift_type);
