-- Approved parser versions and provenance catalogues are append-only.
CREATE OR REPLACE FUNCTION prevent_approved_parser_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.review_status='approved' THEN
    IF TG_OP='UPDATE' AND NEW.review_status='deprecated'
       AND (to_jsonb(NEW)-'review_status')=(to_jsonb(OLD)-'review_status') THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'approved parser versions are immutable';
  END IF;
  RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;

DROP TRIGGER IF EXISTS trg_approved_parser_immutable ON declarative_parser_specs;
CREATE TRIGGER trg_approved_parser_immutable
BEFORE UPDATE OR DELETE ON declarative_parser_specs
FOR EACH ROW EXECUTE FUNCTION prevent_approved_parser_mutation();

CREATE OR REPLACE FUNCTION require_approved_parser_binding()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.review_status='approved' AND NOT EXISTS(
    SELECT 1 FROM declarative_parser_specs
    WHERE id=NEW.parser_spec_id AND review_status='approved'
  ) THEN
    RAISE EXCEPTION 'registry approval requires an approved parser version';
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_registry_requires_approved_parser ON schema_registry_entries;
CREATE TRIGGER trg_registry_requires_approved_parser
BEFORE INSERT OR UPDATE ON schema_registry_entries
FOR EACH ROW EXECUTE FUNCTION require_approved_parser_binding();

CREATE OR REPLACE FUNCTION prevent_approved_registry_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.review_status='approved' THEN
    IF TG_OP='UPDATE' AND NEW.review_status='deprecated'
       AND (to_jsonb(NEW)-'review_status')=(to_jsonb(OLD)-'review_status') THEN
      RETURN NEW;
    END IF;
    RAISE EXCEPTION 'approved schema registry entries are immutable';
  END IF;
  RETURN CASE WHEN TG_OP='DELETE' THEN OLD ELSE NEW END;
END $$;

DROP TRIGGER IF EXISTS trg_approved_registry_immutable ON schema_registry_entries;
CREATE TRIGGER trg_approved_registry_immutable
BEFORE UPDATE OR DELETE ON schema_registry_entries
FOR EACH ROW EXECUTE FUNCTION prevent_approved_registry_mutation();

CREATE OR REPLACE FUNCTION prevent_task3_provenance_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END $$;

DROP TRIGGER IF EXISTS trg_event_observation_append_only ON activity_event_observations;
CREATE TRIGGER trg_event_observation_append_only
BEFORE UPDATE OR DELETE ON activity_event_observations
FOR EACH ROW EXECUTE FUNCTION prevent_task3_provenance_mutation();

DROP TRIGGER IF EXISTS trg_event_partition_append_only ON event_partitions;
CREATE TRIGGER trg_event_partition_append_only
BEFORE UPDATE OR DELETE ON event_partitions
FOR EACH ROW EXECUTE FUNCTION prevent_task3_provenance_mutation();

CREATE TABLE IF NOT EXISTS logical_event_signatures (
  record_signature CHAR(64) PRIMARY KEY CHECK(record_signature ~ '^[0-9a-f]{64}$'),
  event_id UUID NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(record_signature,event_id)
);

DO $$ BEGIN
  IF NOT EXISTS(SELECT 1 FROM pg_constraint WHERE conname='activity_event_observations_signature_event_fk') THEN
    ALTER TABLE activity_event_observations ADD CONSTRAINT activity_event_observations_signature_event_fk
    FOREIGN KEY(record_signature,event_id) REFERENCES logical_event_signatures(record_signature,event_id) ON DELETE RESTRICT;
  END IF;
END $$;

DROP TRIGGER IF EXISTS trg_logical_event_signature_append_only ON logical_event_signatures;
CREATE TRIGGER trg_logical_event_signature_append_only
BEFORE UPDATE OR DELETE ON logical_event_signatures
FOR EACH ROW EXECUTE FUNCTION prevent_task3_provenance_mutation();
