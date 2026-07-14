from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import json
from uuid import uuid4

import asyncpg
import pytest

from db.postgres import PostgresClient
from evidence.ledger import EvidenceLedger
from retention.evaluation import RetentionEvaluationService, build_email_retention_input
from retention.models import RetentionAction, RetentionClass, RetentionPolicy
from retention.policy import RetentionRepository
from test_task1_database_integration import migrated_database


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def _mail(subject: str, *, list_mail: bool = False) -> bytes:
    message = EmailMessage()
    message["Date"] = "Sat, 09 Mar 2024 16:00:00 +0000"
    message["From"] = "Updates <updates@example.test>"
    message["To"] = "User <user@example.test>"
    message["Subject"] = subject
    if list_mail:
        message["List-Id"] = "weekly.example.test"
        message["List-Unsubscribe"] = "<mailto:leave@example.test>"
    message.set_content("A bounded source body.")
    return message.as_bytes()


def test_canonical_message_conversion_is_deterministic_and_metadata_bounded():
    value = build_email_retention_input(
        payload=_mail("Weekly offers", list_mail=True), media_type="message/rfc822",
        source_metadata={"flags": ["\\Flagged"], "direction": "inbound", "reply_rate": 0},
        occurred_at=NOW - timedelta(days=400), observed_at=NOW, as_of=NOW,
    )
    assert value.starred and value.newsletter_candidate and value.bulk_candidate
    assert value.subject == "Weekly offers" and value.inactive_days == 400


@pytest.mark.asyncio
async def test_live_retention_evaluation_uses_canonical_artifacts_and_preserves_unsure(
    tmp_path, migrated_database,
):
    url, _, _ = migrated_database
    client = PostgresClient(url)
    ledger = EvidenceLedger(client)
    connection = await asyncpg.connect(url)
    try:
        profile_id = await connection.fetchval(
            "INSERT INTO profiles(identity_name) VALUES('Retention evaluation fixture') RETURNING id"
        )
        source_run = await connection.fetchval(
            """INSERT INTO analysis_runs(run_type,profile_id,status,pipeline_version,started_at)
               VALUES('connector_sync',$1,'completed','task5-fixture',NOW()) RETURNING id""", profile_id,
        )
        await connection.execute(
            """INSERT INTO source_connector_definitions
               (connector_key,definition_version,display_name,provider,connector_type,modes,data_classes,permissions)
               VALUES('email.imap','1','IMAP','Fixture','email','["snapshot_import"]',
                      '["email.message"]','[]')"""
        )
        instance_id = await connection.fetchval(
            """INSERT INTO connector_instances
               (connector_key,definition_version,profile_id,account_key,display_name,status)
               VALUES('email.imap','1',$1,'primary','Fixture mailbox','connected') RETURNING id""", profile_id,
        )
        sync_run_id = await connection.fetchval(
            """INSERT INTO connector_sync_runs(connector_instance_id,analysis_run_id,run_kind,status)
               VALUES($1,$2,'sync','completed') RETURNING id""", instance_id, source_run,
        )
    finally:
        await connection.close()

    snapshot_id = await ledger.create_export_snapshot(
        source_run, "manual_import", profile_id=profile_id,
        metadata={"connector_instance_id": str(instance_id)},
    )
    records = (
        ("weekly", _mail("Weekly offers", list_mail=True), {
            "mailbox": "INBOX", "direction": "inbound", "repeated_template": True,
            "reply_rate": 0, "observed_link_engagement": False,
        }),
        ("ambiguous", _mail("Hello"), {"mailbox": "INBOX", "direction": "inbound"}),
    )
    connection = await asyncpg.connect(url)
    try:
        for key, payload, metadata in records:
            path = tmp_path / f"{key}.eml"
            path.write_bytes(payload)
            _, artifact_id = await ledger.record_source_artifact(
                snapshot_id, payload, storage_uri=path.resolve().as_uri(),
                original_path=f"mail/{key}.eml", file_name=f"{key}.eml",
                declared_mime="message/rfc822",
            )
            await connection.execute(
                """INSERT INTO connector_raw_records
                   (connector_instance_id,sync_run_id,source_record_id,record_signature,data_class,
                    occurred_at,observed_at,media_type,source_metadata,source_artifact_id,ingestion_status)
                   VALUES($1,$2,$3,$4,'email.message',$5,$6,'message/rfc822',$7::jsonb,$8,'ingested')""",
                instance_id, sync_run_id, key, hashlib.sha256(key.encode()).hexdigest(),
                NOW - timedelta(days=400), NOW, json.dumps(metadata), artifact_id,
            )
    finally:
        await connection.close()

    repository = RetentionRepository(client)
    matching = RetentionPolicy(
        id=uuid4(), version=1, profile_id=profile_id, name="Old inbox mail",
        scope={"mailbox": "INBOX"}, connector_keys=("email.imap",),
        data_classes=("email.message",), minimum_age=timedelta(days=180),
        eligibility_threshold=.8, action=RetentionAction.REVIEW_ONLY,
    )
    await repository.save_policy(matching)
    await repository.save_policy(matching.model_copy(update={"id": uuid4(), "enabled": False}))

    try:
        result = await RetentionEvaluationService(client).evaluate(profile_id=profile_id, as_of=NOW)
        assert result.policies_evaluated == 1 and result.artifacts_considered == 2
        assert {item.classification for item in result.decisions} == {
            RetentionClass.LOW_VALUE_BULK, RetentionClass.UNSURE,
        }
        assert all(item.semantic_adjudication is None for item in result.decisions)
        connection = await asyncpg.connect(url)
        try:
            run = await connection.fetchrow("SELECT * FROM analysis_runs WHERE id=$1", result.analysis_run_id)
            assert run["status"] == "completed" and run["profile_id"] == profile_id
            assert await connection.fetchval(
                "SELECT count(*) FROM retention_decisions WHERE analysis_run_id=$1", result.analysis_run_id,
            ) == 2
        finally:
            await connection.close()
    finally:
        await client.close()
