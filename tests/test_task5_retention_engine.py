from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import pytest
from pydantic import ValidationError

from db.postgres import PostgresClient
from evidence.ledger import EvidenceLedger
from retention.adjudication import (
    RetentionAdjudicationResult, build_retention_adjudication_bundle,
)
from retention.features import EmailRetentionInput, extract_email_retention_features
from retention.models import RetentionAction, RetentionClass, RetentionPolicy
from retention.policy import RetentionCandidate, RetentionRepository, evaluate_candidate
from test_task1_database_integration import migrated_database


NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)


def _policy(*, threshold=0.8, minimum_age=timedelta(days=180), version=1, policy_id=None):
    return RetentionPolicy(
        id=policy_id or uuid4(), version=version, name="Low-value mail",
        scope={"mailbox": "INBOX"}, connector_keys=("email.imap",),
        data_classes=("email.message",), minimum_age=minimum_age,
        eligibility_threshold=threshold, action=RetentionAction.REVIEW_ONLY,
        grace_period=timedelta(days=30),
    )


def _candidate(features, artifact_id=None):
    return RetentionCandidate(
        source_artifact_id=artifact_id or uuid4(), profile_id=None,
        connector_key="email.imap", data_class="email.message",
        occurred_at=NOW - timedelta(days=365), observed_at=NOW - timedelta(days=364),
        attributes={"mailbox": "INBOX"}, features=features,
    )


def test_important_low_value_and_uncertain_mail_are_conservative_and_interest_free():
    financial = extract_email_retention_features(EmailRetentionInput(
        subject="Invoice and payment receipt", has_attachment=True,
        inactive_days=500, bulk_candidate=True,
    ))
    assert financial.classification is RetentionClass.KEEP_FINANCIAL
    assert "financial" in financial.protective_signals

    low = extract_email_retention_features(EmailRetentionInput(
        subject="Weekly offers", bulk_candidate=True, newsletter_candidate=True,
        repeated_template=True, reply_rate=0, inactive_days=400,
    ))
    assert low.classification is RetentionClass.LOW_VALUE_BULK
    assert low.confidence >= 0.8

    uncertain = extract_email_retention_features(EmailRetentionInput(subject="Hello"))
    assert uncertain.classification is RetentionClass.UNSURE
    policy = _policy()
    classification, confidence, semantic, _ = evaluate_candidate(
        policy, _candidate(uncertain), as_of=NOW,
    )
    assert classification is RetentionClass.UNSURE and confidence == 0 and semantic is None

    # Interest strength is not accepted by the retention feature contract.
    with pytest.raises(ValidationError):
        EmailRetentionInput(subject="Hello", interest_strength=1.0)


def test_semantic_bundle_is_minimal_strict_local_and_abstains_safely():
    uncertain = extract_email_retention_features(EmailRetentionInput(subject="Ambiguous record"))
    bundle = build_retention_adjudication_bundle(
        uuid4(), uncertain, subject_excerpt="Ambiguous record with a bounded excerpt" * 20,
        processing_mode="strict_local",
    )
    assert bundle.task_key == "email.retention_adjudication"
    assert bundle.local_only and len(bundle.subject_excerpt) <= 300
    assert "interest" not in str(bundle.model_dump()).casefold()

    abstained = RetentionAdjudicationResult(confidence=0, reasons=("insufficient evidence",), abstained=True)
    classification, confidence, semantic, _ = evaluate_candidate(
        _policy(), _candidate(uncertain), as_of=NOW, adjudication=abstained,
    )
    assert classification is RetentionClass.UNSURE and confidence == 0
    assert semantic["abstained"] is True

    resolved = RetentionAdjudicationResult(
        classification=RetentionClass.KEEP_PERSONAL_SIGNIFICANCE,
        confidence=0.82, reasons=("bounded excerpt indicates personal correspondence",),
    )
    classification, confidence, semantic, _ = evaluate_candidate(
        _policy(), _candidate(uncertain), as_of=NOW, adjudication=resolved,
    )
    assert classification is RetentionClass.KEEP_PERSONAL_SIGNIFICANCE
    assert confidence == 0.82 and semantic

    with pytest.raises(ValueError, match="only allowed for unresolved"):
        build_retention_adjudication_bundle(
            uuid4(), extract_email_retention_features(EmailRetentionInput(subject="Bank statement")),
            subject_excerpt="Bank statement", processing_mode="local_first",
        )


def test_active_university_and_project_correspondence_are_protected():
    university = extract_email_retention_features(EmailRetentionInput(
        subject="University course enrolment and tuition timetable",
        thread_message_count=4, user_replied=True, inactive_days=14,
    ))
    assert university.classification is RetentionClass.KEEP_PROJECT_RECORD
    assert "education" in university.protective_signals

    project = extract_email_retention_features(EmailRetentionInput(
        subject="Weekly project coordination", active_project_linkage=True,
        known_human_correspondent=True, thread_message_count=6, inactive_days=5,
    ))
    assert project.classification is RetentionClass.KEEP_PROJECT_RECORD
    assert "active_project_linkage" in project.protective_signals


@pytest.mark.asyncio
async def test_policy_versions_and_decisions_are_immutable_idempotent(tmp_path, migrated_database):
    url, _, _ = migrated_database
    client = PostgresClient(url); ledger = EvidenceLedger(client)
    connection = await asyncpg.connect(url)
    try:
        run_id = await connection.fetchval(
            "INSERT INTO analysis_runs(run_type,status,pipeline_version,started_at) VALUES('retention','running','task5-retention-v1',NOW()) RETURNING id"
        )
    finally:
        await connection.close()
    snapshot_id = await ledger.create_export_snapshot(run_id, "manual_import")
    _, artifact_id = await ledger.record_source_artifact(
        snapshot_id, b"old weekly newsletter", storage_uri="fixture://retention-mail",
        original_path="mail/weekly.eml", file_name="weekly.eml", declared_mime="message/rfc822",
    )
    features = extract_email_retention_features(EmailRetentionInput(
        subject="Weekly offers", bulk_candidate=True, newsletter_candidate=True,
        repeated_template=True, reply_rate=0, inactive_days=400,
    ))
    repository = RetentionRepository(client)
    policy_id = uuid4()
    v1 = _policy(policy_id=policy_id, version=1)
    v2 = _policy(policy_id=policy_id, version=2, threshold=0.9)
    await repository.save_policy(v1); await repository.save_policy(v2)
    candidate = _candidate(features, artifact_id)
    first = await repository.record_decision(v1, candidate, analysis_run_id=run_id, as_of=NOW)
    repeated = await repository.record_decision(v1, candidate, analysis_run_id=run_id, as_of=NOW)
    assert repeated.id == first.id
    assert first.classification is RetentionClass.LOW_VALUE_BULK
    assert "interest" not in str(first.deterministic_evidence).casefold()

    connection = await asyncpg.connect(url)
    try:
        counts = await connection.fetchrow(
            """SELECT
              (SELECT COUNT(*) FROM retention_policies WHERE id=$1) versions,
              (SELECT COUNT(*) FROM retention_decisions WHERE source_artifact_id=$2) decisions""",
            policy_id, artifact_id,
        )
        assert dict(counts) == {"versions": 2, "decisions": 1}
    finally:
        await connection.close(); await client.close()
