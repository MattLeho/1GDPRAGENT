from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import asyncpg
import pytest

from connectors.imap_delete import ProviderDeleteResult
from db.postgres import PostgresClient
from evidence.ledger import EvidenceLedger
from evidence.models import (
    AssertionCreate, AssertionStatus, DataClass, EpistemicBasis,
    EvidenceLocatorCreate, LocatorType,
)
from evidence.purged import resolve_persisted_locator
from ingestion.storage import StorageRoots, write_raw_blob
from retention.controller_erasure import ControllerErasureService
from retention.deletion_plan import DeletionPlanRepository, build_deletion_plan
from retention.local_purge import LocalPurgeDenied, LocalPurgeService
from retention.models import (
    DeletionItemGroup, DeletionPlanItem, DeletionStage, RetentionAction,
    RetentionClass, RetentionDecision, RetentionPolicy,
)
from retention.source_delete import SourceDeletionService
from retention.staging import DeletionStageError, transition_stage
from test_task1_database_integration import migrated_database


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def _policy(action=RetentionAction.LOCAL_PURGE):
    return RetentionPolicy(
        id=uuid4(), version=1, name="Reviewed deletion", minimum_age=timedelta(days=30),
        action=action, grace_period=timedelta(days=30),
    )


def _decision(policy, classification, *, artifact_id=None):
    return RetentionDecision(
        id=uuid4(), source_artifact_id=artifact_id or uuid4(), classification=classification,
        deterministic_evidence={}, confidence=0.9, policy_id=policy.id,
        policy_version=1, analysis_run_id=uuid4(), created_at=NOW,
    )


def test_plan_and_stage_state_machine_protect_uncertain_and_enforce_grace():
    policy = _policy()
    low = _decision(policy, RetentionClass.LOW_VALUE_BULK)
    protected = _decision(policy, RetentionClass.KEEP_FINANCIAL)
    unsure = _decision(policy, RetentionClass.UNSURE)
    plan, summary = build_deletion_plan(
        policy, (low, protected, unsure), analysis_run_id=uuid4(), created_at=NOW,
    )
    assert plan.dry_run is True
    assert (summary.eligible, summary.protected, summary.uncertain) == (1, 1, 1)
    eligible = plan.items[0]
    reviewed = transition_stage(eligible, DeletionStage.REVIEW, now=NOW)
    quarantined = transition_stage(reviewed, DeletionStage.QUARANTINE, now=NOW)
    with pytest.raises(DeletionStageError, match="not expired"):
        transition_stage(quarantined, DeletionStage.ELIGIBLE_FOR_DELETE, now=NOW + timedelta(days=29))
    assert transition_stage(
        quarantined, DeletionStage.ELIGIBLE_FOR_DELETE, now=NOW + timedelta(days=30),
    ).stage is DeletionStage.ELIGIBLE_FOR_DELETE
    with pytest.raises(DeletionStageError, match="protected"):
        transition_stage(plan.items[1], DeletionStage.QUARANTINE, now=NOW)


@pytest.mark.asyncio
async def test_plan_approval_requires_every_eligible_decision_reviewed(tmp_path, migrated_database):
    url, _, _ = migrated_database
    client, _, _, run_id, artifact_id, _, _ = await _artifact_fixture(url, tmp_path)
    connection = await asyncpg.connect(url)
    try:
        policy_id = await connection.fetchval(
            "INSERT INTO retention_policies(name,action) VALUES('Review gate','local_purge') RETURNING id",
        )
        decision_id = await connection.fetchval(
            """INSERT INTO retention_decisions(source_artifact_id,classification,deterministic_evidence,
               confidence,policy_id,policy_version,analysis_run_id)
               VALUES($1,'LOW_VALUE_BULK','{}',0.9,$2,1,$3) RETURNING id""",
            artifact_id, policy_id, run_id,
        )
        plan_id = await connection.fetchval(
            "INSERT INTO deletion_plans(policy_id,policy_version,analysis_run_id) VALUES($1,1,$2) RETURNING id",
            policy_id, run_id,
        )
        await connection.execute(
            """INSERT INTO deletion_plan_items(deletion_plan_id,source_artifact_id,retention_decision_id,
               item_group,action,reasons) VALUES($1,$2,$3,'eligible','local_purge','[]')""",
            plan_id, artifact_id, decision_id,
        )
    finally:
        await connection.close()
    repository = DeletionPlanRepository(client)
    await repository.review_plan(plan_id, actor="reviewer", confirmation="REVIEW PLAN")
    with pytest.raises(ValueError, match="every eligible decision"):
        await repository.approve_plan(plan_id, actor="reviewer", confirmation="APPROVE DESTRUCTIVE ACTIONS")
    await repository.review_decision(decision_id, actor="reviewer", approved=True)
    await repository.approve_plan(plan_id, actor="reviewer", confirmation="APPROVE DESTRUCTIVE ACTIONS")
    await client.close()


async def _artifact_fixture(url, tmp_path, *, content=b"important excerpt then disposable content"):
    roots = StorageRoots.from_base(tmp_path / "data").ensure()
    blob = write_raw_blob(roots.blobs, content)
    client = PostgresClient(url); ledger = EvidenceLedger(client)
    profiles = await client.execute("SELECT id FROM profiles ORDER BY created_at,id LIMIT 1")
    run_id = await ledger.create_analysis_run(
        "retention", "task5-wave6-v1", profile_id=profiles[0]["id"],
    )
    snapshot_id = await ledger.create_export_snapshot(run_id, "manual_import")
    _, artifact_id = await ledger.record_source_occurrence(
        snapshot_id, blob.sha256, blob.byte_size, storage_uri=blob.path.as_uri(),
        original_path="mail/message.eml", file_name="message.eml",
        declared_mime="message/rfc822", canonical_hash=blob.sha256,
    )
    return client, ledger, roots, run_id, artifact_id, blob, content


async def _approved_item(connection, run_id, artifact_id, action, *, connector_capability=False):
    policy_id = await connection.fetchval(
        """INSERT INTO retention_policies(name,action,minimum_age_seconds,grace_period_seconds)
           VALUES('Reviewed policy',$1,0,0) RETURNING id""", action,
    )
    decision_id = await connection.fetchval(
        """INSERT INTO retention_decisions(
           source_artifact_id,classification,deterministic_evidence,confidence,
           policy_id,policy_version,analysis_run_id,review_status)
           VALUES($1,'LOW_VALUE_BULK','{}',0.95,$2,1,$3,'approved') RETURNING id""",
        artifact_id, policy_id, run_id,
    )
    plan_id = await connection.fetchval(
        """INSERT INTO deletion_plans(policy_id,policy_version,analysis_run_id,dry_run,status,reviewed_at,approved_at)
           VALUES($1,1,$2,FALSE,'approved',NOW(),NOW()) RETURNING id""", policy_id, run_id,
    )
    return await connection.fetchval(
        """INSERT INTO deletion_plan_items(
           deletion_plan_id,source_artifact_id,retention_decision_id,item_group,action,
           reasons,source_delete_capability,stage,quarantine_at,grace_expires_at)
           VALUES($1,$2,$3,'eligible',$4,'["reviewed"]',$5,'eligible_for_delete',NOW(),NOW())
           RETURNING id""", plan_id, artifact_id, decision_id, action, connector_capability,
    )


@pytest.mark.asyncio
async def test_local_purge_preserves_required_evidence_and_refuses_full_source(tmp_path, migrated_database):
    url, _, _ = migrated_database
    client, ledger, roots, run_id, artifact_id, blob, content = await _artifact_fixture(url, tmp_path)
    locator_id = await ledger.create_locator(EvidenceLocatorCreate(
        artifact_id=artifact_id, locator_type=LocatorType.TEXT_BYTE_SPAN,
        locator={"byte_start": 0, "byte_end": 17}, expected_text="important excerpt",
    ), content)
    assertion_id = await ledger.create_assertion(AssertionCreate(
        subject_type="Email", subject_ref=str(artifact_id), predicate="HAS_RETAINED_FACT",
        object_type="literal", object_value="important excerpt", assertion_type="fact",
        data_class=DataClass.DECLARED, status=AssertionStatus.ACCEPTED,
        epistemic_basis=EpistemicBasis.SOURCE_EXPLICIT, confidence=1,
        ingested_at=NOW, derivation_method="fixture", derivation_version="1",
        analysis_run_id=run_id, evidence_locator_ids=(locator_id,),
    ))
    connection = await asyncpg.connect(url)
    try:
        item_id = await _approved_item(connection, run_id, artifact_id, "local_purge")
    finally:
        await connection.close()
    execution = await LocalPurgeService(client, roots=roots).execute(item_id)
    assert execution.evidence_locators_preserved and not blob.path.exists() and assertion_id
    connection = await asyncpg.connect(url)
    try:
        assert await resolve_persisted_locator(connection, locator_id) == b"important excerpt"
        assert await connection.fetchval(
            "SELECT content_purged_at IS NOT NULL FROM content_purge_tombstones WHERE source_artifact_id=$1",
            artifact_id,
        )
    finally:
        await connection.close(); await client.close()

    client, ledger, roots, run_id, artifact_id, blob, content = await _artifact_fixture(
        url, tmp_path / "full", content=b"entire required source",
    )
    locator_id = await ledger.create_locator(EvidenceLocatorCreate(
        artifact_id=artifact_id, locator_type=LocatorType.TEXT_BYTE_SPAN,
        locator={"byte_start": 0, "byte_end": len(content)}, expected_text=content.decode(),
    ), content)
    await ledger.create_assertion(AssertionCreate(
        subject_type="Email", subject_ref=str(artifact_id), predicate="HAS_RETAINED_FACT",
        object_type="literal", object_value="entire required source", assertion_type="fact",
        data_class=DataClass.DECLARED, status=AssertionStatus.ACCEPTED,
        epistemic_basis=EpistemicBasis.SOURCE_EXPLICIT, confidence=1,
        ingested_at=NOW, derivation_method="fixture", derivation_version="1",
        analysis_run_id=run_id, evidence_locator_ids=(locator_id,),
    ))
    connection = await asyncpg.connect(url)
    try: item_id = await _approved_item(connection, run_id, artifact_id, "local_purge")
    finally: await connection.close()
    with pytest.raises(LocalPurgeDenied, match="would not minimise"):
        await LocalPurgeService(client, roots=roots).execute(item_id)
    assert blob.path.exists()
    await client.close()


class _AcknowledgedTrashAdapter:
    async def execute(self, instance, metadata):
        assert metadata == {"mailbox": "INBOX", "uid": 7, "uidvalidity": "42"}
        return ProviderDeleteResult("move_to_trash", True, "COPYUID 42 7 70", "moved_to_trash")


@pytest.mark.asyncio
async def test_source_delete_is_capability_gated_and_audited(tmp_path, migrated_database):
    url, _, _ = migrated_database
    client, _, _, run_id, artifact_id, _, _ = await _artifact_fixture(url, tmp_path)
    connection = await asyncpg.connect(url)
    try:
        await connection.execute(
            """INSERT INTO source_connector_definitions(
               connector_key,definition_version,display_name,provider,connector_type,modes,
               data_classes,permissions,supports_source_delete)
               VALUES('email.imap','1','IMAP','IMAP','email_source','["incremental_poll"]',
               '["email.message"]','[{"key":"mail.source_delete","access":"delete","data_class":"email.message","description":"Move reviewed messages to Trash","required":false,"enabled_by_default":false}]',TRUE)"""
        )
        connector_id = await connection.fetchval(
            """INSERT INTO connector_instances(
               connector_key,definition_version,display_name,status,configuration,enabled_permissions)
               VALUES('email.imap','1','Fixture','connected',$1::jsonb,'["mail.source_delete"]'::jsonb) RETURNING id""",
            json.dumps({"host": "localhost", "username": "fixture", "scope": "metadata_only"}),
        )
        sync_id = await connection.fetchval(
            """INSERT INTO connector_sync_runs(connector_instance_id,analysis_run_id,run_kind,status)
               VALUES($1,$2,'sync','completed') RETURNING id""", connector_id, run_id,
        )
        await connection.execute(
            """INSERT INTO connector_raw_records(
               connector_instance_id,sync_run_id,source_record_id,record_signature,data_class,
               media_type,source_metadata,source_artifact_id,ingestion_status)
               VALUES($1,$2,'42:7',$3,'email.message','message/rfc822',$4::jsonb,$5,'ingested')""",
            connector_id, sync_id, "a" * 64,
            json.dumps({"mailbox": "INBOX", "uid": 7, "uidvalidity": "42"}), artifact_id,
        )
        item_id = await _approved_item(connection, run_id, artifact_id, "source_delete", connector_capability=True)
    finally:
        await connection.close()
    result = await SourceDeletionService(
        client, adapters={"email.imap": _AcknowledgedTrashAdapter()},
    ).execute(item_id)
    assert result.reversible and result.provider_status == "moved_to_trash"
    connection = await asyncpg.connect(url)
    try:
        audit = await connection.fetchrow(
            "SELECT provider_action,provider_status,audit_payload FROM source_deletion_executions WHERE deletion_plan_item_id=$1",
            item_id,
        )
        assert audit["provider_action"] == "move_to_trash"
        assert audit["provider_status"] == "moved_to_trash"
        payload = json.loads(audit["audit_payload"]) if isinstance(audit["audit_payload"], str) else dict(audit["audit_payload"])
        assert payload["acknowledged"] is True
    finally:
        await connection.close(); await client.close()


@pytest.mark.asyncio
async def test_controller_erasure_creates_existing_request_draft_and_never_sends(tmp_path, migrated_database):
    url, _, _ = migrated_database
    client, _, _, run_id, artifact_id, _, _ = await _artifact_fixture(url, tmp_path)
    connection = await asyncpg.connect(url)
    try:
        item_id = await _approved_item(connection, run_id, artifact_id, "controller_erasure_candidate")
    finally:
        await connection.close()
    service = ControllerErasureService(client)
    candidate = await service.create_candidate(item_id, controller_key="example-controller.test")
    assert candidate.existing_request_id is None
    reviewed = await service.review_and_create_draft(
        candidate.id, actor="fixture-reviewer", confirmation="CREATE DRAFT ERASURE REQUEST",
        company_name="Example Controller",
    )
    connection = await asyncpg.connect(url)
    try:
        request = await connection.fetchrow("SELECT * FROM requests WHERE id=$1", reviewed.existing_request_id)
        assert request["status"] == "draft" and request["request_type"] == "erasure"
        assert reviewed.automatic_execution_enabled is False
        assert await connection.fetchval("SELECT COUNT(*) FROM outbound_messages WHERE request_id=$1", request["id"]) == 0
    finally:
        await connection.close(); await client.close()
