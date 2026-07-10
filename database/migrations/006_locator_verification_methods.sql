ALTER TABLE evidence_locators ADD COLUMN IF NOT EXISTS verification_method TEXT NOT NULL DEFAULT 'mechanical_resolution';
ALTER TABLE evidence_locators DROP CONSTRAINT IF EXISTS evidence_locator_verification_method_check;
ALTER TABLE evidence_locators ADD CONSTRAINT evidence_locator_verification_method_check
CHECK (verification_method IN ('mechanical_resolution','exact_quote_match','structured_value_match','human_verified'));

CREATE OR REPLACE FUNCTION enforce_locator_immutability() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF ROW(OLD.artifact_id,OLD.locator_type,OLD.locator,OLD.raw_hash,OLD.verification_method,OLD.created_at) IS DISTINCT FROM ROW(NEW.artifact_id,NEW.locator_type,NEW.locator,NEW.raw_hash,NEW.verification_method,NEW.created_at) THEN RAISE EXCEPTION 'EvidenceLocator identity is immutable'; END IF;
 IF OLD.verified AND NOT NEW.verified THEN RAISE EXCEPTION 'verified evidence cannot become unverified in place'; END IF;
 RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION enforce_assertion_acceptance() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE verified_count INTEGER; model_verified_count INTEGER; source_count INTEGER;
BEGIN
  IF NEW.status='accepted' AND (TG_OP='INSERT' OR OLD.status IS DISTINCT FROM NEW.status) THEN
    IF btrim(NEW.derivation_method)='' OR btrim(NEW.derivation_version)='' THEN RAISE EXCEPTION 'accepted assertion requires derivation method and version'; END IF;
    SELECT count(*),count(*) FILTER(WHERE el.verification_method IN ('exact_quote_match','structured_value_match','human_verified'))
      INTO verified_count,model_verified_count FROM assertion_evidence ae JOIN evidence_locators el ON el.id=ae.evidence_locator_id WHERE ae.assertion_id=NEW.id AND el.verified;
    SELECT count(*) INTO source_count FROM assertion_derivations ad WHERE ad.assertion_id=NEW.id;
    IF NEW.epistemic_basis='model_hypothesis' AND model_verified_count=0 THEN RAISE EXCEPTION 'model hypothesis requires exact or structured verified evidence before acceptance'; END IF;
    IF NEW.epistemic_basis IN ('source_explicit','controller_assigned') AND verified_count=0 THEN RAISE EXCEPTION '% assertion requires verified evidence before acceptance',NEW.epistemic_basis; END IF;
    IF NEW.epistemic_basis='deterministic_derivation' AND verified_count=0 AND source_count=0 THEN RAISE EXCEPTION 'deterministic derivation requires verified evidence or source assertions'; END IF;
  END IF;
  IF NEW.status='superseded' AND (TG_OP='INSERT' OR OLD.status IS DISTINCT FROM NEW.status) AND NOT EXISTS(SELECT 1 FROM assertions replacement WHERE replacement.supersedes_assertion_id=NEW.id) THEN RAISE EXCEPTION 'superseded assertion requires a replacement assertion'; END IF;
  RETURN NEW;
END $$;
