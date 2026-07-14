-- Task 6 Wave 0 authoritative contracts. Neo4j remains a derived projection.
CREATE TABLE IF NOT EXISTS capability_taxonomy(
  capability_key TEXT NOT NULL,taxonomy_version TEXT NOT NULL,label TEXT NOT NULL,
  description TEXT NOT NULL,active BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY(capability_key,taxonomy_version),
  CHECK(capability_key IN('age_classification','cross_service_identity_resolution',
  'location_reconstruction','social_graph_reconstruction','purchase_profiling',
  'behavioural_personalisation','behavioural_prediction','biometric_matching',
  'communications_content_scanning','device_correlation','interest_inference',
  'sensitive_interest_inference','risk_scoring','automated_access_restriction')));

CREATE TABLE IF NOT EXISTS capability_candidates(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),profile_id UUID NOT NULL REFERENCES profiles(id),
  capability_key TEXT NOT NULL,taxonomy_version TEXT NOT NULL,rule_id TEXT NOT NULL,
  rule_version TEXT NOT NULL,supporting_assertion_ids UUID[] NOT NULL DEFAULT '{}',
  supporting_aggregate_ids UUID[] NOT NULL DEFAULT '{}',evidence_status TEXT NOT NULL
  CHECK(evidence_status IN('evidenced_from_export','documented','legally_authorised',
  'technically_possible','speculative','human_confirmed')),rule_result JSONB NOT NULL,
  confidence NUMERIC CHECK(confidence IS NULL OR confidence BETWEEN 0 AND 1),
  analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id),calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  FOREIGN KEY(capability_key,taxonomy_version) REFERENCES capability_taxonomy(capability_key,taxonomy_version),
  UNIQUE(profile_id,capability_key,rule_id,rule_version,analysis_run_id),CHECK(jsonb_typeof(rule_result)='object'));

CREATE TABLE IF NOT EXISTS privacy_graph_snapshots(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),profile_id UUID NOT NULL REFERENCES profiles(id),
  graph_version TEXT NOT NULL,method TEXT NOT NULL,method_version TEXT NOT NULL,
  node_ids UUID[] NOT NULL DEFAULT '{}',edge_assertion_ids UUID[] NOT NULL DEFAULT '{}',
  snapshot_hash CHAR(64) NOT NULL CHECK(snapshot_hash~'^[0-9a-f]{64}$'),
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),UNIQUE(profile_id,graph_version,snapshot_hash));
CREATE TABLE IF NOT EXISTS identifier_statistics(
  graph_snapshot_id UUID NOT NULL REFERENCES privacy_graph_snapshots(id),identifier_node_id UUID NOT NULL,
  controller_count INT NOT NULL CHECK(controller_count>=0),service_count INT NOT NULL CHECK(service_count>=0),
  data_domain_count INT NOT NULL CHECK(data_domain_count>=0),schema_count INT NOT NULL CHECK(schema_count>=0),
  first_seen TIMESTAMPTZ,last_seen TIMESTAMPTZ,temporal_persistence_seconds NUMERIC NOT NULL CHECK(temporal_persistence_seconds>=0),
  occurrence_count BIGINT NOT NULL CHECK(occurrence_count>=0),degree NUMERIC NOT NULL CHECK(degree>=0),
  betweenness NUMERIC NOT NULL CHECK(betweenness>=0),articulation_point BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY(graph_snapshot_id,identifier_node_id),CHECK(first_seen IS NULL OR last_seen IS NULL OR last_seen>=first_seen));
CREATE TABLE IF NOT EXISTS edge_risks(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),graph_snapshot_id UUID NOT NULL REFERENCES privacy_graph_snapshots(id),
  assertion_id UUID REFERENCES assertions(id),source_node_id UUID NOT NULL,target_node_id UUID NOT NULL,linkage_type TEXT NOT NULL,
  directness NUMERIC NOT NULL CHECK(directness BETWEEN 0 AND 1),stability NUMERIC NOT NULL CHECK(stability BETWEEN 0 AND 1),
  cross_context_reuse NUMERIC NOT NULL CHECK(cross_context_reuse BETWEEN 0 AND 1),
  uniqueness_gain NUMERIC NOT NULL CHECK(uniqueness_gain BETWEEN 0 AND 1),
  legal_accessibility NUMERIC CHECK(legal_accessibility IS NULL OR legal_accessibility BETWEEN 0 AND 1),
  reversibility NUMERIC NOT NULL CHECK(reversibility BETWEEN 0 AND 1),confidence NUMERIC NOT NULL CHECK(confidence BETWEEN 0 AND 1),
  UNIQUE(graph_snapshot_id,source_node_id,target_node_id,linkage_type));
CREATE TABLE IF NOT EXISTS identifier_removal_simulations(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),graph_snapshot_id UUID NOT NULL REFERENCES privacy_graph_snapshots(id),
  graph_version TEXT NOT NULL,selected_identifier_node_ids UUID[] NOT NULL CHECK(cardinality(selected_identifier_node_ids)>0),
  calculation_method TEXT NOT NULL,connected_components_before INT NOT NULL CHECK(connected_components_before>=0),
  connected_components_after INT NOT NULL CHECK(connected_components_after>=0),
  cross_domain_paths_before BIGINT NOT NULL CHECK(cross_domain_paths_before>=0),
  cross_domain_paths_after BIGINT NOT NULL CHECK(cross_domain_paths_after>=0),
  disconnected_path_fraction NUMERIC NOT NULL CHECK(disconnected_path_fraction BETWEEN 0 AND 1),
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());

CREATE TABLE IF NOT EXISTS policy_source_versions(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),source_artifact_id UUID NOT NULL REFERENCES source_artifacts(id),
  policy_key TEXT NOT NULL,version_label TEXT NOT NULL,effective_from TIMESTAMPTZ,effective_to TIMESTAMPTZ,
  retrieved_at TIMESTAMPTZ NOT NULL,source_uri TEXT,content_hash CHAR(64) NOT NULL CHECK(content_hash~'^[0-9a-f]{64}$'),
  UNIQUE(policy_key,version_label,content_hash),CHECK(effective_from IS NULL OR effective_to IS NULL OR effective_to>=effective_from));
CREATE TABLE IF NOT EXISTS privacy_purposes(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),purpose_key TEXT NOT NULL,label TEXT NOT NULL,description TEXT,
  valid_from TIMESTAMPTZ,valid_to TIMESTAMPTZ,UNIQUE(purpose_key,valid_from),
  CHECK(valid_from IS NULL OR valid_to IS NULL OR valid_to>=valid_from));
CREATE TABLE IF NOT EXISTS policy_claims(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),policy_source_version_id UUID NOT NULL REFERENCES policy_source_versions(id),
  claim_type TEXT NOT NULL,claim_text TEXT NOT NULL,status TEXT NOT NULL CHECK(status IN('candidate','accepted','rejected','superseded')),
  evidence_locator_ids UUID[] NOT NULL CHECK(cardinality(evidence_locator_ids)>0),valid_from TIMESTAMPTZ,valid_to TIMESTAMPTZ,
  analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id),CHECK(valid_from IS NULL OR valid_to IS NULL OR valid_to>=valid_from));
CREATE TABLE IF NOT EXISTS purpose_distance_assessments(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),original_purpose_id UUID NOT NULL REFERENCES privacy_purposes(id),
  current_purpose_id UUID NOT NULL REFERENCES privacy_purposes(id),distance INT NOT NULL CHECK(distance BETWEEN 0 AND 4),
  heuristic_version TEXT NOT NULL,feature_vector JSONB NOT NULL,wording TEXT NOT NULL DEFAULT 'Possible purpose drift'
  CHECK(wording='Possible purpose drift'),assertion_ids UUID[] NOT NULL DEFAULT '{}',
  analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id),created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(original_purpose_id,current_purpose_id,heuristic_version,analysis_run_id),CHECK(jsonb_typeof(feature_vector)='object'));

CREATE TABLE IF NOT EXISTS privacy_datasets(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),profile_id UUID NOT NULL REFERENCES profiles(id),dataset_key TEXT NOT NULL,label TEXT NOT NULL,
  storage_class TEXT NOT NULL DEFAULT 'unknown' CHECK(storage_class IN('centrally_stored','federated_mutually_accessible',
  'independently_stored_linkable','unknown')),UNIQUE(profile_id,dataset_key));
CREATE TABLE IF NOT EXISTS privacy_authorities(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),authority_key TEXT NOT NULL UNIQUE,name TEXT NOT NULL,jurisdiction TEXT);
CREATE TABLE IF NOT EXISTS institutional_access_edges(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),profile_id UUID NOT NULL REFERENCES profiles(id),source_ref TEXT NOT NULL,target_ref TEXT NOT NULL,
  access_type TEXT NOT NULL CHECK(access_type IN('CONTROLS','PROCESSES','HOSTS','CAN_REQUEST','HAS_LEGAL_GATEWAY_TO','SHARES_WITH','USES_SUBPROCESSOR')),
  epistemic_state TEXT NOT NULL CHECK(epistemic_state IN('currently_observed','potentially_enabled','alleged_unverified')),
  jurisdiction TEXT,legal_instrument TEXT,requirements JSONB NOT NULL DEFAULT '[]',transparency TEXT,
  assertion_id UUID NOT NULL REFERENCES assertions(id),created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(profile_id,source_ref,target_ref,access_type,assertion_id),CHECK(jsonb_typeof(requirements)='array'));

CREATE TABLE IF NOT EXISTS privacy_hypotheses(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),profile_id UUID NOT NULL REFERENCES profiles(id),detector_id TEXT NOT NULL,
  detector_version TEXT NOT NULL,statement TEXT NOT NULL,unresolved_question TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'open'
  CHECK(status IN('open','request_drafted','request_sent','confirmed','rejected','unresolved','superseded')),
  supporting_assertion_ids UUID[] NOT NULL DEFAULT '{}',request_id UUID REFERENCES requests(id),
  supersedes_id UUID REFERENCES privacy_hypotheses(id),analysis_run_id UUID NOT NULL REFERENCES analysis_runs(id),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS privacy_hypothesis_transitions(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),hypothesis_id UUID NOT NULL REFERENCES privacy_hypotheses(id),
  status_before TEXT,status_after TEXT NOT NULL CHECK(status_after IN('open','request_drafted','request_sent','confirmed','rejected','unresolved','superseded')),
  evidence_assertion_ids UUID[] NOT NULL DEFAULT '{}',actor TEXT NOT NULL,transitioned_at TIMESTAMPTZ NOT NULL DEFAULT NOW());

CREATE TABLE IF NOT EXISTS deletion_simulations(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),profile_id UUID NOT NULL REFERENCES profiles(id),
  deletion_plan_id UUID REFERENCES deletion_plans(id),graph_snapshot_id UUID NOT NULL REFERENCES privacy_graph_snapshots(id),
  method TEXT NOT NULL,method_version TEXT NOT NULL,selected_identifier_node_ids UUID[] NOT NULL DEFAULT '{}',
  predicted_effects JSONB NOT NULL,calculated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),CHECK(jsonb_typeof(predicted_effects)='object'));
CREATE TABLE IF NOT EXISTS expected_removals(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),deletion_simulation_id UUID NOT NULL REFERENCES deletion_simulations(id),
  object_type TEXT NOT NULL,object_ref TEXT NOT NULL,expected_effect TEXT NOT NULL,evidence_assertion_ids UUID[] NOT NULL DEFAULT '{}',
  UNIQUE(deletion_simulation_id,object_type,object_ref));
CREATE TABLE IF NOT EXISTS deletion_verifications(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),expected_removal_id UUID NOT NULL REFERENCES expected_removals(id),
  later_export_snapshot_id UUID NOT NULL REFERENCES export_snapshots(id),status TEXT NOT NULL
  CHECK(status IN('EXPECTED_REMOVED','CONFIRMED_REMOVED_FROM_OBSERVED_EXPORT','STILL_OBSERVED','UNVERIFIABLE')),
  observed_assertion_ids UUID[] NOT NULL DEFAULT '{}',explanation TEXT NOT NULL,checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(expected_removal_id,later_export_snapshot_id));
CREATE TABLE IF NOT EXISTS privacy_query_audits(
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),profile_id UUID NOT NULL REFERENCES profiles(id),tool_name TEXT NOT NULL,
  arguments JSONB NOT NULL,result_hash CHAR(64) NOT NULL CHECK(result_hash~'^[0-9a-f]{64}$'),
  assertion_ids UUID[] NOT NULL DEFAULT '{}',evidence_locator_ids UUID[] NOT NULL DEFAULT '{}',
  source_artifact_ids UUID[] NOT NULL DEFAULT '{}',unknowns JSONB NOT NULL DEFAULT '[]',executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CHECK(jsonb_typeof(arguments)='object' AND jsonb_typeof(unknowns)='array'));

CREATE INDEX IF NOT EXISTS idx_capability_candidates_profile ON capability_candidates(profile_id,capability_key,evidence_status);
CREATE INDEX IF NOT EXISTS idx_graph_snapshots_profile_time ON privacy_graph_snapshots(profile_id,calculated_at DESC);
CREATE INDEX IF NOT EXISTS idx_access_profile_type ON institutional_access_edges(profile_id,access_type,epistemic_state);
CREATE INDEX IF NOT EXISTS idx_hypotheses_profile_status ON privacy_hypotheses(profile_id,status,updated_at DESC);
