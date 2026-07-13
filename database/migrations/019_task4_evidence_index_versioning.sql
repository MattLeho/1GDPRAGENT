-- Evidence links belong to a specific immutable materialisation. The original
-- key omitted materialisation_id, so a stable project/era insight id could keep
-- pointing at the first cached period that indexed it.
ALTER TABLE insight_evidence_index
    DROP CONSTRAINT IF EXISTS insight_evidence_index_pkey;
ALTER TABLE insight_evidence_index
    ADD PRIMARY KEY(materialisation_id,insight_id,evidence_kind,evidence_ref_id,role);

-- Temporal aggregates are canonical Task 3 inputs and can now be traced by the
-- same evidence inspector as events, assertions, and temporal states.
ALTER TABLE insight_evidence_index
    DROP CONSTRAINT IF EXISTS insight_evidence_index_evidence_kind_check;
ALTER TABLE insight_evidence_index
    ADD CONSTRAINT insight_evidence_index_evidence_kind_check CHECK(evidence_kind IN (
        'activity_event','assertion','temporal_state','temporal_aggregate',
        'source_artifact','evidence_locator','external_context_event',
        'media_location_candidate'
    ));
