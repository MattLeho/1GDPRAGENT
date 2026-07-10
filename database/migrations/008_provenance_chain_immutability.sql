CREATE UNIQUE INDEX IF NOT EXISTS uq_source_artifact_occurrence
ON source_artifacts(export_snapshot_id,original_path,COALESCE(archive_member_path,''));

CREATE OR REPLACE FUNCTION reject_immutable_update() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION '% rows are immutable; create a new version or occurrence',TG_TABLE_NAME; END $$;

DROP TRIGGER IF EXISTS source_artifacts_no_update ON source_artifacts;
CREATE TRIGGER source_artifacts_no_update BEFORE UPDATE ON source_artifacts FOR EACH ROW EXECUTE FUNCTION reject_immutable_update();
DROP TRIGGER IF EXISTS export_snapshots_no_update ON export_snapshots;
CREATE TRIGGER export_snapshots_no_update BEFORE UPDATE ON export_snapshots FOR EACH ROW EXECUTE FUNCTION reject_immutable_update();
DROP TRIGGER IF EXISTS export_snapshots_no_delete ON export_snapshots;
CREATE TRIGGER export_snapshots_no_delete BEFORE DELETE ON export_snapshots FOR EACH ROW EXECUTE FUNCTION reject_immutable_delete();
DROP TRIGGER IF EXISTS assertion_evidence_no_update ON assertion_evidence;
CREATE TRIGGER assertion_evidence_no_update BEFORE UPDATE ON assertion_evidence FOR EACH ROW EXECUTE FUNCTION reject_immutable_update();
DROP TRIGGER IF EXISTS assertion_evidence_no_delete ON assertion_evidence;
CREATE TRIGGER assertion_evidence_no_delete BEFORE DELETE ON assertion_evidence FOR EACH ROW EXECUTE FUNCTION reject_immutable_delete();
DROP TRIGGER IF EXISTS assertion_derivations_no_update ON assertion_derivations;
CREATE TRIGGER assertion_derivations_no_update BEFORE UPDATE ON assertion_derivations FOR EACH ROW EXECUTE FUNCTION reject_immutable_update();
DROP TRIGGER IF EXISTS assertion_derivations_no_delete ON assertion_derivations;
CREATE TRIGGER assertion_derivations_no_delete BEFORE DELETE ON assertion_derivations FOR EACH ROW EXECUTE FUNCTION reject_immutable_delete();
