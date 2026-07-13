-- Task 5 Wave 6: review audit and provenance-preserving local purge support.

CREATE TABLE IF NOT EXISTS retention_decision_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    retention_decision_id UUID NOT NULL REFERENCES retention_decisions(id) ON DELETE RESTRICT,
    actor TEXT NOT NULL,
    review_status TEXT NOT NULL CHECK(review_status IN ('approved','rejected')),
    reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(retention_decision_id),
    CHECK(jsonb_typeof(reasons)='array')
);

CREATE TABLE IF NOT EXISTS deletion_plan_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deletion_plan_id UUID NOT NULL REFERENCES deletion_plans(id) ON DELETE RESTRICT,
    actor TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('reviewed','approved','rejected')),
    confirmation TEXT NOT NULL,
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS minimized_evidence_segments (
    evidence_locator_id UUID PRIMARY KEY REFERENCES evidence_locators(id) ON DELETE RESTRICT,
    source_artifact_id UUID NOT NULL REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    resolved_bytes BYTEA NOT NULL,
    resolved_hash CHAR(64) NOT NULL CHECK(resolved_hash ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS content_purge_tombstones (
    source_artifact_id UUID PRIMARY KEY REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    original_content_blob_id UUID NOT NULL REFERENCES content_blobs(id) ON DELETE RESTRICT,
    original_sha256 CHAR(64) NOT NULL CHECK(original_sha256 ~ '^[0-9a-f]{64}$'),
    content_purged_at TIMESTAMPTZ NOT NULL,
    retained_evidence_basis JSONB NOT NULL,
    full_source_unavailable BOOLEAN NOT NULL DEFAULT TRUE CHECK(full_source_unavailable),
    CHECK(jsonb_typeof(retained_evidence_basis)='object')
);

CREATE INDEX IF NOT EXISTS minimized_evidence_segments_artifact_idx
    ON minimized_evidence_segments(source_artifact_id);
