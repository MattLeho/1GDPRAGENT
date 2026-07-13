-- Task 5 Wave 0: canonical connector, retention, and deletion-safety contracts.
-- Secrets remain in the AES-GCM connector_credentials store from migration 010.
-- These tables never constitute semantic graph truth.

CREATE TABLE IF NOT EXISTS source_connector_definitions (
    connector_key TEXT NOT NULL,
    definition_version TEXT NOT NULL,
    display_name TEXT NOT NULL,
    provider TEXT NOT NULL,
    connector_type TEXT NOT NULL,
    modes JSONB NOT NULL,
    data_classes JSONB NOT NULL,
    permissions JSONB NOT NULL,
    supports_backfill BOOLEAN NOT NULL DEFAULT FALSE,
    supports_incremental BOOLEAN NOT NULL DEFAULT FALSE,
    supports_source_delete BOOLEAN NOT NULL DEFAULT FALSE,
    supports_remote_delete_request BOOLEAN NOT NULL DEFAULT FALSE,
    configuration_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(connector_key,definition_version),
    CHECK(jsonb_typeof(modes)='array' AND jsonb_array_length(modes)>0),
    CHECK(jsonb_typeof(data_classes)='array'),
    CHECK(jsonb_typeof(permissions)='array'),
    CHECK(jsonb_typeof(configuration_schema)='object')
);

CREATE TABLE IF NOT EXISTS connector_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_key TEXT NOT NULL,
    definition_version TEXT NOT NULL,
    profile_id UUID REFERENCES profiles(id) ON DELETE RESTRICT,
    account_key TEXT NOT NULL DEFAULT 'default',
    display_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'disconnected' CHECK(status IN (
      'connected','paused','degraded','authentication_required','error','disconnected')),
    enabled_permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    credential_id UUID REFERENCES connector_credentials(id) ON DELETE SET NULL,
    last_sync_at TIMESTAMPTZ,
    next_sync_at TIMESTAMPTZ,
    last_error JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY(connector_key,definition_version)
      REFERENCES source_connector_definitions(connector_key,definition_version) ON DELETE RESTRICT,
    UNIQUE(profile_id,connector_key,account_key),
    CHECK(jsonb_typeof(enabled_permissions)='array'),
    CHECK(jsonb_typeof(configuration)='object')
);

CREATE TABLE IF NOT EXISTS connector_cursors (
    connector_instance_id UUID NOT NULL REFERENCES connector_instances(id) ON DELETE CASCADE,
    cursor_key TEXT NOT NULL DEFAULT 'default',
    cursor_version INTEGER NOT NULL DEFAULT 1 CHECK(cursor_version>0),
    position JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_watermark TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY(connector_instance_id,cursor_key),
    CHECK(jsonb_typeof(position)='object')
);

CREATE TABLE IF NOT EXISTS connector_sync_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_instance_id UUID NOT NULL REFERENCES connector_instances(id) ON DELETE RESTRICT,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    run_kind TEXT NOT NULL CHECK(run_kind IN ('sync','backfill')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','running','completed','failed','cancelled')),
    cursor_before JSONB NOT NULL DEFAULT '{}'::jsonb,
    cursor_after JSONB NOT NULL DEFAULT '{}'::jsonb,
    artefacts_discovered BIGINT NOT NULL DEFAULT 0 CHECK(artefacts_discovered>=0),
    events_produced BIGINT NOT NULL DEFAULT 0 CHECK(events_produced>=0),
    duplicates_skipped BIGINT NOT NULL DEFAULT 0 CHECK(duplicates_skipped>=0),
    errors BIGINT NOT NULL DEFAULT 0 CHECK(errors>=0),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    error JSONB,
    CHECK(completed_at IS NULL OR completed_at>=started_at)
);

CREATE TABLE IF NOT EXISTS connector_raw_records (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_instance_id UUID NOT NULL REFERENCES connector_instances(id) ON DELETE RESTRICT,
    sync_run_id UUID NOT NULL REFERENCES connector_sync_runs(id) ON DELETE RESTRICT,
    source_record_id TEXT NOT NULL,
    source_record_version TEXT NOT NULL DEFAULT '1',
    record_signature CHAR(64) NOT NULL CHECK(record_signature ~ '^[0-9a-f]{64}$'),
    data_class TEXT NOT NULL,
    occurred_at TIMESTAMPTZ,
    observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    media_type TEXT NOT NULL,
    source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    required_permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_artifact_id UUID REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    ingestion_status TEXT NOT NULL DEFAULT 'queued' CHECK(ingestion_status IN ('queued','ingesting','ingested','failed')),
    error JSONB,
    UNIQUE(connector_instance_id,record_signature),
    CHECK(jsonb_typeof(source_metadata)='object'),
    CHECK(jsonb_typeof(required_permissions)='array'),
    CHECK(ingestion_status<>'ingested' OR source_artifact_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS connector_permission_audits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connector_instance_id UUID NOT NULL REFERENCES connector_instances(id) ON DELETE RESTRICT,
    actor TEXT NOT NULL,
    permissions_before JSONB NOT NULL DEFAULT '[]'::jsonb,
    permissions_after JSONB NOT NULL DEFAULT '[]'::jsonb,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK(jsonb_typeof(permissions_before)='array'),
    CHECK(jsonb_typeof(permissions_after)='array')
);

CREATE TABLE IF NOT EXISTS retention_policies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_version INTEGER NOT NULL DEFAULT 1 CHECK(policy_version>0),
    profile_id UUID REFERENCES profiles(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    scope JSONB NOT NULL DEFAULT '{}'::jsonb,
    connector_keys JSONB NOT NULL DEFAULT '[]'::jsonb,
    data_classes JSONB NOT NULL DEFAULT '[]'::jsonb,
    minimum_age_seconds BIGINT NOT NULL DEFAULT 0 CHECK(minimum_age_seconds>=0),
    eligibility_threshold NUMERIC NOT NULL DEFAULT 1 CHECK(eligibility_threshold>=0 AND eligibility_threshold<=1),
    action TEXT NOT NULL CHECK(action IN ('local_purge','source_delete','controller_erasure_candidate','review_only')),
    schedule JSONB,
    grace_period_seconds BIGINT NOT NULL DEFAULT 2592000 CHECK(grace_period_seconds>=0),
    configuration JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(id,policy_version),
    CHECK(jsonb_typeof(scope)='object'),
    CHECK(jsonb_typeof(connector_keys)='array'),
    CHECK(jsonb_typeof(data_classes)='array'),
    CHECK(jsonb_typeof(configuration)='object')
);

CREATE TABLE IF NOT EXISTS retention_decisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_artifact_id UUID NOT NULL REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    classification TEXT NOT NULL CHECK(classification IN (
      'KEEP_LEGAL_OR_REGULATORY','KEEP_FINANCIAL','KEEP_IDENTITY_OR_SECURITY',
      'KEEP_PROJECT_RECORD','KEEP_ACTIVE_CONVERSATION','KEEP_PERSONAL_SIGNIFICANCE',
      'LOW_VALUE_BULK','SPAM','UNSURE')),
    deterministic_evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    semantic_adjudication JSONB,
    confidence NUMERIC NOT NULL CHECK(confidence>=0 AND confidence<=1),
    policy_id UUID NOT NULL,
    policy_version INTEGER NOT NULL,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    review_status TEXT NOT NULL DEFAULT 'pending' CHECK(review_status IN ('pending','approved','rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    FOREIGN KEY(policy_id,policy_version) REFERENCES retention_policies(id,policy_version) ON DELETE RESTRICT,
    UNIQUE(source_artifact_id,policy_id,policy_version,analysis_run_id),
    CHECK(jsonb_typeof(deterministic_evidence)='object'),
    CHECK(semantic_adjudication IS NULL OR jsonb_typeof(semantic_adjudication)='object')
);

CREATE TABLE IF NOT EXISTS deletion_plans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id UUID NOT NULL,
    policy_version INTEGER NOT NULL,
    analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id) ON DELETE RESTRICT,
    dry_run BOOLEAN NOT NULL DEFAULT TRUE,
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','reviewed','approved','executing','completed','cancelled')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reviewed_at TIMESTAMPTZ,
    approved_at TIMESTAMPTZ,
    FOREIGN KEY(policy_id,policy_version) REFERENCES retention_policies(id,policy_version) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS deletion_plan_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deletion_plan_id UUID NOT NULL REFERENCES deletion_plans(id) ON DELETE RESTRICT,
    source_artifact_id UUID NOT NULL REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    retention_decision_id UUID NOT NULL REFERENCES retention_decisions(id) ON DELETE RESTRICT,
    item_group TEXT NOT NULL CHECK(item_group IN ('eligible','protected','uncertain')),
    action TEXT NOT NULL CHECK(action IN ('local_purge','source_delete','controller_erasure_candidate','review_only')),
    reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_delete_capability BOOLEAN NOT NULL DEFAULT FALSE,
    stage TEXT NOT NULL DEFAULT 'candidate' CHECK(stage IN ('candidate','review','quarantine','eligible_for_delete','executed','cancelled')),
    quarantine_at TIMESTAMPTZ,
    grace_expires_at TIMESTAMPTZ,
    UNIQUE(deletion_plan_id,source_artifact_id,action),
    CHECK(jsonb_typeof(reasons)='array'),
    CHECK(NOT(action='source_delete' AND source_delete_capability=FALSE)),
    CHECK(item_group='eligible' OR stage IN ('candidate','review','cancelled')),
    CHECK(grace_expires_at IS NULL OR quarantine_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS source_deletion_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deletion_plan_item_id UUID NOT NULL REFERENCES deletion_plan_items(id) ON DELETE RESTRICT,
    connector_instance_id UUID NOT NULL REFERENCES connector_instances(id) ON DELETE RESTRICT,
    provider_action TEXT NOT NULL,
    reversible BOOLEAN NOT NULL DEFAULT TRUE,
    provider_response_id TEXT,
    provider_status TEXT NOT NULL,
    audit_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(deletion_plan_item_id),
    CHECK(jsonb_typeof(audit_payload)='object')
);

CREATE TABLE IF NOT EXISTS local_purge_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deletion_plan_item_id UUID NOT NULL REFERENCES deletion_plan_items(id) ON DELETE RESTRICT,
    source_artifact_id UUID NOT NULL REFERENCES source_artifacts(id) ON DELETE RESTRICT,
    content_purged_at TIMESTAMPTZ NOT NULL,
    retained_evidence_basis JSONB NOT NULL,
    evidence_locators_preserved BOOLEAN NOT NULL,
    UNIQUE(deletion_plan_item_id),
    CHECK(jsonb_typeof(retained_evidence_basis)='object'),
    CHECK(evidence_locators_preserved)
);

CREATE TABLE IF NOT EXISTS controller_erasure_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    deletion_plan_item_id UUID NOT NULL REFERENCES deletion_plan_items(id) ON DELETE RESTRICT,
    controller_key TEXT NOT NULL,
    existing_request_id UUID REFERENCES requests(id) ON DELETE RESTRICT,
    review_status TEXT NOT NULL DEFAULT 'pending' CHECK(review_status IN ('pending','approved','rejected')),
    automatic_execution_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(deletion_plan_item_id),
    CHECK(NOT automatic_execution_enabled OR review_status='approved')
);

CREATE INDEX IF NOT EXISTS idx_connector_instances_profile_status ON connector_instances(profile_id,status);
CREATE INDEX IF NOT EXISTS idx_connector_runs_instance_started ON connector_sync_runs(connector_instance_id,started_at DESC);
CREATE INDEX IF NOT EXISTS idx_connector_raw_queue ON connector_raw_records(connector_instance_id,ingestion_status,observed_at);
CREATE INDEX IF NOT EXISTS idx_retention_decisions_artifact ON retention_decisions(source_artifact_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deletion_items_plan_group ON deletion_plan_items(deletion_plan_id,item_group,stage);

