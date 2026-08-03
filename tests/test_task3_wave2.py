from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

import pytest
import asyncpg

from ingestion.checkpoints import CheckpointStore, checkpoint_key
from ingestion.events import catalogue_observations, deduplicate_events, write_activity_events
from ingestion.models import (
    ActionClass, ActivityEvent, CheckpointStatus, DeclarativeParserSpec,
    PipelineStage, StructureFingerprint, TemporalPrecision,
)
from ingestion.parser_runtime import LocatedRecord, ParserSpecError, execute_parser, select, validate_parser_spec
from ingestion.sampling import build_schema_interpretation_bundle, representative_samples
from ingestion.schema_registry import SchemaRegistry
from test_task1_database_integration import migrated_database
from db.postgres import PostgresClient
from evidence.ledger import EvidenceLedger
from evidence.models import EvidenceLocatorCreate, LocatorType


def _spec(**overrides):
    values = dict(
        parser_id="fixture.activity", parser_version="1.0.0", file_family="json",
        event_type="search.performed", data_domain="search_history",
        timestamp_selector="/time", subject_selector="/subject/id",
        identifier_selectors={"id": "/id"}, object_selectors={"value": "/query"},
        temporal_precision=TemporalPrecision.SECOND, action_class=ActionClass.SEARCHED,
        service="Fixture Search", object_type="query",
    )
    values.update(overrides)
    return DeclarativeParserSpec(**values)


def test_selector_runtime_is_constrained_and_non_executable():
    value = {"a": [{"b": 3}], "a/b": {"~key": 4}}
    assert select(value, "$.a[0].b") == 3
    assert select(value, "/a~1b/~0key") == 4
    for selector in ("$..password", "$.items[*]", "$[?(@.x)]", "__import__('os')", "$.x[0:4]"):
        with pytest.raises(ParserSpecError):
            validate_parser_spec(_spec(subject_selector=selector))


def test_approved_style_spec_executes_deterministically_with_exact_field_locators():
    artifact, snapshot = uuid4(), uuid4()
    source = uuid4()
    locators = {selector: uuid4() for selector in ("/time", "/subject/id", "/id", "/query")}
    record = LocatedRecord(
        value={"time": "2024-01-02T03:04:05Z", "subject": {"id": "person-1"}, "id": "r-1", "query": "privacy"},
        source_locator_id=source, field_locator_ids=locators,
    )
    first = execute_parser(_spec(), [record], artifact_id=artifact, export_snapshot_id=snapshot)
    second = execute_parser(_spec(), [record], artifact_id=artifact, export_snapshot_id=uuid4())
    assert first.records_seen == first.events_emitted == 1 and first.rejected_records == 0
    assert first.events[0].record_signature == second.events[0].record_signature
    assert first.events[0].event_id == second.events[0].event_id
    assert first.events[0].field_locator_ids == {
        "occurred_at": locators["/time"], "subject_id": locators["/subject/id"],
        "identifier.id": locators["/id"], "object.value": locators["/query"],
    }


def test_record_without_exact_field_locator_is_rejected_not_partially_grounded():
    record = LocatedRecord(
        value={"time": "2024-01-02T03:04:05Z", "subject": {"id": "p"}, "id": "1", "query": "x"},
        source_locator_id=uuid4(), field_locator_ids={"/subject/id": uuid4()},
    )
    result = execute_parser(_spec(), [record], artifact_id=uuid4(), export_snapshot_id=uuid4())
    assert result.events_emitted == 0 and result.rejected_records == 1
    assert "exact field locator missing" in result.warnings[0]


def test_parser_preserves_date_only_without_inventing_midnight_utc():
    locators = {selector: uuid4() for selector in ("/time", "/subject/id", "/id", "/query")}
    record = LocatedRecord(
        value={"time": "2024-01-02", "subject": {"id": "p"}, "id": "1", "query": "x"},
        source_locator_id=uuid4(), field_locator_ids=locators,
    )
    result = execute_parser(
        _spec(temporal_precision=TemporalPrecision.DAY), [record],
        artifact_id=uuid4(), export_snapshot_id=uuid4(),
    )
    event = result.events[0]
    assert event.occurred_at is None
    assert event.occurred_at_original == "2024-01-02"
    assert event.temporal_precision is TemporalPrecision.DAY
    assert event.timezone is None and event.timezone_evidence == "not_applicable_date_only"


def test_representative_sampling_is_deterministic_and_bounded():
    records = [
        {"id": 1},
        {"id": 2, "name": "middle"},
        {"id": 3, "a": 1, "b": 2, "c": 3},
        {"id": 4, "nested": {"deeper": {"value": True}}},
        {"id": 5, "rare": [1, 2, 3]},
    ]
    first = representative_samples(records)
    assert first == representative_samples(records)
    assert records[0] in first
    assert records[2] in first  # maximum key coverage
    assert records[3] in first  # maximum depth
    bundle = build_schema_interpretation_bundle(
        records, analysis_run_id=uuid4(), source_artifact_ids=(uuid4(),),
        fingerprint_id="a" * 64, maximum_sample_bytes=180,
    )
    encoded = json.dumps(bundle.samples, sort_keys=True, separators=(",", ":")).encode()
    assert len(encoded) <= bundle.maximum_sample_bytes
    assert 0 < len(bundle.samples) < len(records)
    assert bundle.task_key == "schema.interpretation"


def _event(*, snapshot=None, artifact=None, locator=None):
    signature = "b" * 64
    from ingestion.parser_runtime import EVENT_NAMESPACE
    from uuid import uuid5
    return ActivityEvent(
        event_id=uuid5(EVENT_NAMESPACE, signature), record_signature=signature,
        subject_id="person-1", export_snapshot_id=snapshot or uuid4(),
        artifact_id=artifact or uuid4(), service="Fixture", data_domain="activity",
        event_type="fixture.event", occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        parser_id="fixture", parser_version="1", source_locator_id=locator or uuid4(),
    )


def test_logical_events_deduplicate_across_exports_and_keep_observations(tmp_path):
    first, second = _event(), _event()
    logical, observations = deduplicate_events([first, second], observed_at=datetime(2024, 2, 1, tzinfo=timezone.utc))
    assert len(logical) == 1 and len(observations) == 2
    result = write_activity_events(tmp_path, [first, second], analysis_run_id=uuid4(), partition_key="fixture")
    assert result.event_partition.row_count == 1
    assert result.observation_partition.row_count == 2
    assert result.event_partition.path.endswith(".parquet")


def test_checkpoint_key_includes_stage_content_and_parser_version():
    base = checkpoint_key(stage=PipelineStage.PARSING, item_key="artifact:1", content_hash="c" * 64, parser_version="1")
    assert base == checkpoint_key(stage=PipelineStage.PARSING, item_key="artifact:1", content_hash="c" * 64, parser_version="1")
    assert base != checkpoint_key(stage=PipelineStage.PARSING, item_key="artifact:1", content_hash="c" * 64, parser_version="2")
    assert base != checkpoint_key(stage=PipelineStage.HASHING, item_key="artifact:1", content_hash="c" * 64, parser_version="1")


def test_unknown_schema_route_uses_task2_router_and_never_auto_approves():
    route = (Path(__file__).resolve().parents[1] / "frontend/app/api/ingestion/schema-interpretation/route.ts").read_text(encoding="utf-8")
    helper = (Path(__file__).resolve().parents[1] / "frontend/lib/execution/task3.ts").read_text(encoding="utf-8")
    assert "executeTask3Bundle(manifest,authority.profileId)" in route
    assert "executeTask({" in helper and "taskKey:bundle.task_key" in helper
    assert "maximum_sample_bytes" in route and "Buffer.byteLength" in route
    assert "review_status:'proposed'" in route
    assert "review_status:'approved'" not in route
    assert "GoogleGenAI" not in route and "generateContent" not in route


@pytest.mark.asyncio
async def test_registry_approval_and_checkpoint_restart_invariants(migrated_database):
    url, request_id, _file_id = migrated_database
    connection = await asyncpg.connect(url)
    try:
        run_id = await connection.fetchval(
            "INSERT INTO analysis_runs(run_type,request_id,status,pipeline_version) VALUES('task3-wave2',$1,'running','task3-v1') RETURNING id",
            request_id,
        )
        registry = SchemaRegistry(connection)
        fingerprint = await registry.ensure_fingerprint(
            fingerprint_hash="d" * 64, family="json", provider_id="fixture",
            provider_version="1", canonical_shape={"keys": ["id", "time"]}, sample_count=5,
        )
        assert await registry.approved_match("d" * 64) is None
        bundle = build_schema_interpretation_bundle(
            [{"id": "1", "time": "2024-01-01", "subject": {"id": "p"}, "query": "x"}],
            analysis_run_id=run_id, source_artifact_ids=(uuid4(),), fingerprint_id="d" * 64,
        )
        first_request = await registry.ensure_interpretation_request(
            analysis_run_id=run_id, structure_fingerprint_id=fingerprint,
            interpretation_version="1", bundle=bundle,
        )
        second_request = await registry.ensure_interpretation_request(
            analysis_run_id=run_id, structure_fingerprint_id=fingerprint,
            interpretation_version="1", bundle=bundle,
        )
        assert first_request.request_id == second_request.request_id
        assert first_request.created and not second_request.created

        parser_id = await registry.propose(_spec())
        assert await registry.approved_match("d" * 64) is None  # proposal is not approval
        await registry.approve(parser_spec_id=parser_id, approved_by="fixture-reviewer")
        await registry.bind(
            structure_fingerprint_id=fingerprint, parser_spec_id=parser_id,
            source_service="Fixture Search", data_domain="search_history",
            file_family="json", normalised_event_type="search.performed",
        )
        match = await registry.approved_match("d" * 64)
        assert match is not None and match.executable and match.spec.parser_id == "fixture.activity"
        resolved = await registry.resolve(
            StructureFingerprint(
                fingerprint_id="d" * 64, family="json", provider_id="fixture",
                provider_version="1", canonical_shape={"keys": ["id", "time"]}, sample_count=5,
            ), [{"ignored": "known schemas do not create interpretation work"}],
            analysis_run_id=run_id, source_artifact_ids=(uuid4(),),
        )
        assert resolved.outcome == "known" and resolved.interpretation is None
        assert await connection.fetchval("SELECT count(*) FROM schema_interpretation_requests WHERE structure_fingerprint_id=$1", fingerprint) == 1
        with pytest.raises(asyncpg.PostgresError, match="immutable"):
            await connection.execute("UPDATE declarative_parser_specs SET spec=spec||'{\"changed\":true}'::jsonb WHERE id=$1", parser_id)

        checkpoints = CheckpointStore(connection)
        started = await checkpoints.begin(
            analysis_run_id=run_id, stage=PipelineStage.PARSING,
            item_key="artifact:fixture", content_hash="e" * 64, parser_version="1.0.0",
        )
        failed = await checkpoints.finish(
            started, status=CheckpointStatus.FAILED,
            progress={"records_seen": 2}, error={"code": "FORCED_INTERRUPTION"},
        )
        resumed = await checkpoints.begin(
            analysis_run_id=run_id, stage=PipelineStage.PARSING,
            item_key="artifact:fixture", content_hash="e" * 64, parser_version="1.0.0",
        )
        assert failed.status is CheckpointStatus.FAILED
        assert resumed.status is CheckpointStatus.RUNNING and resumed.attempt == 2
        completed = await checkpoints.finish(resumed, progress={"records_seen": 5})
        replay = await checkpoints.begin(
            analysis_run_id=run_id, stage=PipelineStage.PARSING,
            item_key="artifact:fixture", content_hash="e" * 64, parser_version="1.0.0",
        )
        assert completed.status is CheckpointStatus.COMPLETED
        assert replay.status is CheckpointStatus.COMPLETED and replay.attempt == 2
        assert len(await checkpoints.progress(run_id)) == 1

        client = PostgresClient(url)
        ledger = EvidenceLedger(client)
        try:
            event_inputs = []
            for ordinal in range(2):
                snapshot = await ledger.create_export_snapshot(run_id, "manual_import", request_id=request_id)
                content = f"fixture observation {ordinal}".encode()
                _blob, artifact = await ledger.record_source_artifact(
                    snapshot, content, storage_uri=f"fixture://wave2/{ordinal}",
                    original_path=f"wave2/{ordinal}.txt", file_name=f"{ordinal}.txt",
                )
                locator = await ledger.create_locator(
                    EvidenceLocatorCreate(
                        artifact_id=artifact, locator_type=LocatorType.TEXT_SPAN,
                        locator={"byte_start": 0, "byte_end": len(content)},
                        expected_text=content.decode(),
                    ), content,
                )
                event_inputs.append(_event(snapshot=snapshot, artifact=artifact, locator=locator))
            logical, observations = deduplicate_events(event_inputs)
            await catalogue_observations(
                connection, observations,
                {event.event_id: event.record_signature for event in logical},
            )
            assert await connection.fetchval("SELECT count(*) FROM logical_event_signatures") == 1
            assert await connection.fetchval("SELECT count(*) FROM activity_event_observations") == 2
            with pytest.raises(asyncpg.PostgresError, match="append-only"):
                await connection.execute("UPDATE activity_event_observations SET observed_at=NOW()")
        finally:
            await client.close()
    finally:
        await connection.close()
