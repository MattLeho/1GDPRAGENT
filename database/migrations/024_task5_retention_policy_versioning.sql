-- Task 5 Wave 5: allow immutable versions under one logical policy UUID.

DO $$
BEGIN
  IF EXISTS(SELECT 1 FROM pg_constraint WHERE conname='retention_decisions_policy_id_policy_version_fkey') THEN
    ALTER TABLE retention_decisions DROP CONSTRAINT retention_decisions_policy_id_policy_version_fkey;
  END IF;
  IF EXISTS(SELECT 1 FROM pg_constraint WHERE conname='deletion_plans_policy_id_policy_version_fkey') THEN
    ALTER TABLE deletion_plans DROP CONSTRAINT deletion_plans_policy_id_policy_version_fkey;
  END IF;
  IF EXISTS(SELECT 1 FROM pg_constraint WHERE conname='retention_policies_pkey') THEN
    ALTER TABLE retention_policies DROP CONSTRAINT retention_policies_pkey;
  END IF;
END $$;

ALTER TABLE retention_policies
    ADD CONSTRAINT retention_policies_pkey PRIMARY KEY(id,policy_version);

ALTER TABLE retention_decisions
    ADD CONSTRAINT retention_decisions_policy_id_policy_version_fkey
    FOREIGN KEY(policy_id,policy_version) REFERENCES retention_policies(id,policy_version) ON DELETE RESTRICT;

ALTER TABLE deletion_plans
    ADD CONSTRAINT deletion_plans_policy_id_policy_version_fkey
    FOREIGN KEY(policy_id,policy_version) REFERENCES retention_policies(id,policy_version) ON DELETE RESTRICT;
