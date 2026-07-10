CREATE OR REPLACE FUNCTION reject_immutable_delete() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION '% rows are immutable and cannot be deleted',TG_TABLE_NAME; END $$;

DROP TRIGGER IF EXISTS assertions_no_delete ON assertions;
CREATE TRIGGER assertions_no_delete BEFORE DELETE ON assertions FOR EACH ROW EXECUTE FUNCTION reject_immutable_delete();
DROP TRIGGER IF EXISTS content_blobs_no_delete ON content_blobs;
CREATE TRIGGER content_blobs_no_delete BEFORE DELETE ON content_blobs FOR EACH ROW EXECUTE FUNCTION reject_immutable_delete();
DROP TRIGGER IF EXISTS source_artifacts_no_delete ON source_artifacts;
CREATE TRIGGER source_artifacts_no_delete BEFORE DELETE ON source_artifacts FOR EACH ROW EXECUTE FUNCTION reject_immutable_delete();
DROP TRIGGER IF EXISTS evidence_locators_no_delete ON evidence_locators;
CREATE TRIGGER evidence_locators_no_delete BEFORE DELETE ON evidence_locators FOR EACH ROW EXECUTE FUNCTION reject_immutable_delete();
DROP TRIGGER IF EXISTS data_artifacts_no_delete ON data_artifacts;
CREATE TRIGGER data_artifacts_no_delete BEFORE DELETE ON data_artifacts FOR EACH ROW EXECUTE FUNCTION reject_immutable_delete();

CREATE OR REPLACE FUNCTION enforce_blob_immutability() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF ROW(OLD.sha256,OLD.byte_size,OLD.storage_uri,OLD.first_ingested_at) IS DISTINCT FROM ROW(NEW.sha256,NEW.byte_size,NEW.storage_uri,NEW.first_ingested_at) THEN RAISE EXCEPTION 'ContentBlob is immutable'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS content_blobs_immutable ON content_blobs;
CREATE TRIGGER content_blobs_immutable BEFORE UPDATE ON content_blobs FOR EACH ROW EXECUTE FUNCTION enforce_blob_immutability();

CREATE OR REPLACE FUNCTION enforce_locator_immutability() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF ROW(OLD.artifact_id,OLD.locator_type,OLD.locator,OLD.raw_hash,OLD.created_at) IS DISTINCT FROM ROW(NEW.artifact_id,NEW.locator_type,NEW.locator,NEW.raw_hash,NEW.created_at) THEN RAISE EXCEPTION 'EvidenceLocator identity is immutable'; END IF;
 IF OLD.verified AND NOT NEW.verified THEN RAISE EXCEPTION 'verified evidence cannot become unverified in place'; END IF;
 RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS evidence_locators_immutable ON evidence_locators;
CREATE TRIGGER evidence_locators_immutable BEFORE UPDATE ON evidence_locators FOR EACH ROW EXECUTE FUNCTION enforce_locator_immutability();

CREATE OR REPLACE FUNCTION enforce_artifact_version_immutability() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'data artifact versions are immutable; insert a new version'; END $$;
DROP TRIGGER IF EXISTS data_artifacts_immutable ON data_artifacts;
CREATE TRIGGER data_artifacts_immutable BEFORE UPDATE ON data_artifacts FOR EACH ROW EXECUTE FUNCTION enforce_artifact_version_immutability();

CREATE OR REPLACE FUNCTION enforce_assertion_acceptance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE verified_count INTEGER; source_count INTEGER;
BEGIN
  IF NEW.status = 'accepted' AND (TG_OP='INSERT' OR OLD.status IS DISTINCT FROM NEW.status) THEN
    IF btrim(NEW.derivation_method)='' OR btrim(NEW.derivation_version)='' THEN RAISE EXCEPTION 'accepted assertion requires derivation method and version'; END IF;
    SELECT count(*) INTO verified_count FROM assertion_evidence ae JOIN evidence_locators el ON el.id=ae.evidence_locator_id WHERE ae.assertion_id=NEW.id AND el.verified;
    SELECT count(*) INTO source_count FROM assertion_derivations ad WHERE ad.assertion_id=NEW.id;
    IF NEW.epistemic_basis IN ('model_hypothesis','source_explicit','controller_assigned') AND verified_count=0 THEN RAISE EXCEPTION '% assertion requires verified evidence before acceptance',NEW.epistemic_basis; END IF;
    IF NEW.epistemic_basis='deterministic_derivation' AND verified_count=0 AND source_count=0 THEN RAISE EXCEPTION 'deterministic derivation requires verified evidence or source assertions'; END IF;
  END IF;
  IF NEW.status='superseded' AND (TG_OP='INSERT' OR OLD.status IS DISTINCT FROM NEW.status) AND NOT EXISTS(SELECT 1 FROM assertions replacement WHERE replacement.supersedes_assertion_id=NEW.id) THEN
    RAISE EXCEPTION 'superseded assertion requires a replacement assertion';
  END IF;
  RETURN NEW;
END $$;
