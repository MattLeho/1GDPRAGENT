-- Task 6 derived evidence is append-only/versioned. Hypothesis current status is
-- mutable only through its immutable transition ledger.
CREATE OR REPLACE FUNCTION reject_task6_derived_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only; create a new analysis/version',TG_TABLE_NAME;
END $$;

DO $$
DECLARE name TEXT;
BEGIN
  FOREACH name IN ARRAY ARRAY[
    'capability_taxonomy','capability_candidates','privacy_graph_snapshots',
    'identifier_statistics','edge_risks','identifier_removal_simulations',
    'policy_source_versions','privacy_purposes','policy_claims',
    'purpose_distance_assessments','privacy_datasets','privacy_authorities',
    'institutional_access_edges','privacy_hypothesis_transitions',
    'deletion_simulations','expected_removals','deletion_verifications',
    'privacy_query_audits'
  ] LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS task6_append_only ON %I',name);
    EXECUTE format('CREATE TRIGGER task6_append_only BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION reject_task6_derived_mutation()',name);
  END LOOP;
END $$;
