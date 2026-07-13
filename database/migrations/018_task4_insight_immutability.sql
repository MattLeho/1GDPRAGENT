-- Task 4 insight outputs are versioned derivations and evidence records.
-- Corrections are represented by a new materialisation/candidate, never by
-- rewriting or deleting the record that supported an earlier explanation.
DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY[
        'insight_materialisations',
        'insight_aggregate_buckets',
        'insight_evidence_index',
        'external_context_events',
        'temporal_correlation_candidates',
        'media_location_candidates'
    ]
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I_no_update ON %I', table_name, table_name);
        EXECUTE format(
            'CREATE TRIGGER %I_no_update BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION reject_immutable_update()',
            table_name,
            table_name
        );
        EXECUTE format('DROP TRIGGER IF EXISTS %I_no_delete ON %I', table_name, table_name);
        EXECUTE format(
            'CREATE TRIGGER %I_no_delete BEFORE DELETE ON %I FOR EACH ROW EXECUTE FUNCTION reject_immutable_delete()',
            table_name,
            table_name
        );
    END LOOP;
END $$;
