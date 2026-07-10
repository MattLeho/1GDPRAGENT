-- Preserve every analytical output version instead of delete-and-reinsert replacement.
CREATE TABLE IF NOT EXISTS data_artifacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    file_id UUID REFERENCES received_data(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,
    title TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence NUMERIC DEFAULT 1.0,
    source_span TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
ALTER TABLE data_artifacts ADD COLUMN IF NOT EXISTS analysis_run_id UUID REFERENCES analysis_runs(id) ON DELETE RESTRICT;
ALTER TABLE data_artifacts ADD COLUMN IF NOT EXISTS artifact_version INTEGER;
ALTER TABLE data_artifacts ADD COLUMN IF NOT EXISTS supersedes_artifact_id UUID REFERENCES data_artifacts(id) ON DELETE RESTRICT;
ALTER TABLE data_artifacts ADD COLUMN IF NOT EXISTS derivation_method TEXT;
ALTER TABLE data_artifacts ADD COLUMN IF NOT EXISTS derivation_version TEXT;

INSERT INTO analysis_runs(id,run_type,request_id,status,pipeline_version,configuration,started_at,completed_at,created_at)
SELECT gen_random_uuid(),'legacy_artifact_backfill',da.request_id,'completed','legacy-pre-task1',jsonb_build_object('backfilled',true,'request_key',COALESCE(da.request_id::text,'orphan')),MIN(da.created_at),MAX(da.updated_at),MIN(da.created_at)
FROM data_artifacts da WHERE da.analysis_run_id IS NULL GROUP BY da.request_id;

WITH ranked_runs AS (
 SELECT id,request_id,row_number() OVER(PARTITION BY request_id ORDER BY created_at,id) rn
 FROM analysis_runs WHERE run_type='legacy_artifact_backfill'
), ranked_artifacts AS (
 SELECT da.id,rr.id run_id,row_number() OVER(PARTITION BY da.file_id,da.artifact_type,da.title ORDER BY da.created_at,da.id) version
 FROM data_artifacts da JOIN ranked_runs rr ON rr.request_id IS NOT DISTINCT FROM da.request_id AND rr.rn=1 WHERE da.analysis_run_id IS NULL
)
UPDATE data_artifacts da SET analysis_run_id=ra.run_id,artifact_version=ra.version,derivation_method='legacy_artifact_generator',derivation_version='pre-task1'
FROM ranked_artifacts ra WHERE da.id=ra.id;

ALTER TABLE data_artifacts ALTER COLUMN artifact_version SET DEFAULT 1;
ALTER TABLE data_artifacts ALTER COLUMN artifact_version SET NOT NULL;
ALTER TABLE data_artifacts ALTER COLUMN analysis_run_id SET NOT NULL;
ALTER TABLE data_artifacts ALTER COLUMN derivation_method SET DEFAULT 'legacy_unknown';
ALTER TABLE data_artifacts ALTER COLUMN derivation_method SET NOT NULL;
ALTER TABLE data_artifacts ALTER COLUMN derivation_version SET DEFAULT 'legacy_unknown';
ALTER TABLE data_artifacts ALTER COLUMN derivation_version SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_data_artifact_version ON data_artifacts(file_id,artifact_type,title,artifact_version);
CREATE INDEX IF NOT EXISTS idx_data_artifacts_latest ON data_artifacts(request_id,file_id,artifact_version DESC);

CREATE OR REPLACE VIEW current_data_artifacts AS
SELECT DISTINCT ON (file_id,artifact_type,title) * FROM data_artifacts
ORDER BY file_id,artifact_type,title,artifact_version DESC,created_at DESC;
