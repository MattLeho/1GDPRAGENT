-- Catalogue every derived card independently of whether it has supporting
-- evidence. This also records the precise immutable materialisation/window for
-- stable project and era ids reused across multiple period snapshots.
CREATE TABLE IF NOT EXISTS insight_catalogue (
    materialisation_id UUID NOT NULL REFERENCES insight_materialisations(id) ON DELETE RESTRICT,
    insight_id UUID NOT NULL,
    detector_id TEXT NOT NULL,
    detector_version TEXT NOT NULL,
    analysis_run_id UUID REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,
    evidence_count INTEGER NOT NULL CHECK(evidence_count>=0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(materialisation_id,insight_id),
    CHECK(window_end IS NULL OR window_start IS NULL OR window_end>=window_start)
);

DROP TRIGGER IF EXISTS insight_catalogue_no_update ON insight_catalogue;
CREATE TRIGGER insight_catalogue_no_update BEFORE UPDATE ON insight_catalogue
FOR EACH ROW EXECUTE FUNCTION reject_immutable_update();
DROP TRIGGER IF EXISTS insight_catalogue_no_delete ON insight_catalogue;
CREATE TRIGGER insight_catalogue_no_delete BEFORE DELETE ON insight_catalogue
FOR EACH ROW EXECUTE FUNCTION reject_immutable_delete();

CREATE INDEX IF NOT EXISTS idx_insight_catalogue_lookup
ON insight_catalogue(insight_id,created_at DESC);
