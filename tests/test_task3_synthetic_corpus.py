"""Fixture-driven Task 3 synthetic-corpus and restart acceptance tests."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import uuid4
import zipfile

import pytest

from features.geospatial import (
    GeospatialPrecision,
    extract_explicit_interactions,
    extract_geospatial_features,
)
from features.identifiers import IdentifierObservation, analyze_opaque_identifiers
from ingestion.checkpoints import CheckpointStore
from ingestion.file_types import classify_file_type
from ingestion.hashing import canonical_hash, raw_file_sha256
from ingestion.inventory import ArchiveSafetyPolicy, inspect_archive
from ingestion.models import (
    ActivityEvent,
    CheckpointStatus,
    DeclarativeParserSpec,
    FileTypeEvidence,
    FileTypeTruthValue,
    HistoryType,
    PipelineStage,
    TemporalPrecision,
    TemporalState,
)
from ingestion.parser_runtime import LocatedRecord, execute_parser
from ingestion.sampling import build_schema_interpretation_bundle
from ingestion.events import deduplicate_events
from temporal.episodes import (
    EvidenceSignalPoint,
    RecurrenceClass,
    detect_change_points_pelt,
    detect_project_episode_candidates,
    recurrence_metrics,
)
from temporal.views import current_temporal_view


CORPUS_ROOT = Path(__file__).parent / "fixtures" / "task3_corpus"


@pytest.fixture(scope="module")
def corpus() -> dict:
    return json.loads((CORPUS_ROOT / "corpus.json").read_text(encoding="utf-8"))


def _read_json(relative_path: str):
    return json.loads((CORPUS_ROOT / relative_path).read_text(encoding="utf-8"))


def _located(record: dict) -> LocatedRecord:
    selectors = ("/occurred_at", "/subject/id", "/event_id", "/query")
    return LocatedRecord(
        value=record,
        source_locator_id=uuid4(),
        field_locator_ids={selector: uuid4() for selector in selectors},
    )


def _event(*, locations=None, relationships=None) -> ActivityEvent:
    event_id = uuid4()
    return ActivityEvent(
        event_id=event_id,
        record_signature=event_id.hex * 2,
        subject_id="synthetic-subject",
        export_snapshot_id=uuid4(),
        artifact_id=uuid4(),
        service="synthetic-service",
        data_domain="synthetic-domain",
        event_type="synthetic.event",
        occurred_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        parser_id="synthetic.parser",
        parser_version="1.0.0",
        source_locator_id=uuid4(),
        locations=locations or {},
        relationships=relationships or {},
    )


def test_repeated_snapshots_and_logical_events_keep_two_observations(corpus):
    spec = DeclarativeParserSpec(**corpus["approved_parser"])
    first_record = _read_json(corpus["snapshots"][0])[0]
    second_record = _read_json(corpus["snapshots"][1])[0]
    artifact_id = uuid4()

    first = execute_parser(
        spec, [_located(first_record)], artifact_id=artifact_id,
        export_snapshot_id=uuid4(),
    ).events[0]
    second = execute_parser(
        spec, [_located(second_record)], artifact_id=artifact_id,
        export_snapshot_id=uuid4(),
    ).events[0]
    logical, observations = deduplicate_events((first, second))

    assert first.record_signature == second.record_signature
    assert first.event_id == second.event_id
    assert len(logical) == 1
    assert len(observations) == 2
    assert len({item.export_snapshot_id for item in observations}) == 2


def test_duplicate_paths_reuse_raw_hash_and_reordered_keys_reuse_canonical_hash(corpus):
    duplicate_paths = [CORPUS_ROOT / item for item in corpus["duplicate_paths"]]
    reordered_paths = [CORPUS_ROOT / item for item in corpus["reordered_json"]]

    assert duplicate_paths[0] != duplicate_paths[1]
    assert raw_file_sha256(duplicate_paths[0]) == raw_file_sha256(duplicate_paths[1])
    assert canonical_hash(reordered_paths[0].read_bytes(), "json") == canonical_hash(
        reordered_paths[1].read_bytes(), "json"
    )
    assert reordered_paths[0].read_bytes() != reordered_paths[1].read_bytes()


def test_malformed_json_is_rejected_and_mime_extension_mismatch_is_explicit(corpus):
    malformed = CORPUS_ROOT / corpus["malformed_json"]
    with pytest.raises((ValueError, json.JSONDecodeError)):
        canonical_hash(malformed.read_bytes(), "json")

    mismatch = corpus["mime_mismatch"]
    path = CORPUS_ROOT / mismatch["path"]
    truth = classify_file_type(
        path,
        declared_mime=mismatch["declared_mime"],
        data=path.read_bytes(),
        parser_probe_evidence=(
            FileTypeEvidence(
                source="parser_probe", value="valid JSON",
                candidate_format=mismatch["parser_probe_format"], confidence=1.0,
            ),
        ),
    )
    assert truth.status is FileTypeTruthValue.MISMATCH
    assert truth.detected_format == "json"
    assert "conflicts" in truth.reason


def test_archive_traversal_and_expansion_breach_are_quarantined(tmp_path, corpus):
    settings = corpus["archive_policy"]
    traversal_zip = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal_zip, "w") as archive:
        archive.writestr(settings["traversal_member"], b"must not escape")

    expansion_zip = tmp_path / "expansion.zip"
    with zipfile.ZipFile(expansion_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(settings["expansion_member"], b"A" * settings["expanded_bytes"])

    policy = ArchiveSafetyPolicy(
        workspace_root=tmp_path,
        max_expansion_ratio=settings["maximum_expansion_ratio"],
        max_total_expanded_bytes=settings["expanded_bytes"] * 2,
        max_member_expanded_bytes=settings["expanded_bytes"] * 2,
    )
    traversal = inspect_archive(traversal_zip, uuid4(), policy)
    expansion = inspect_archive(expansion_zip, uuid4(), policy)

    assert not traversal.accepted and "path_traversal" in traversal.violations
    assert traversal.observations[0].traversal_attempt is True
    assert not expansion.accepted and "expansion_ratio_limit" in expansion.violations
    assert expansion.expansion_ratio > settings["maximum_expansion_ratio"]


def test_unknown_schema_creates_one_bounded_bundle_while_approved_parser_executes(corpus):
    unknown = corpus["unknown_schema"]
    run_id, artifact_id = uuid4(), uuid4()
    first = build_schema_interpretation_bundle(
        unknown,
        analysis_run_id=run_id,
        source_artifact_ids=(artifact_id,),
        fingerprint_id="f" * 64,
        maximum_sample_bytes=1024,
    )
    second = build_schema_interpretation_bundle(
        unknown,
        analysis_run_id=run_id,
        source_artifact_ids=(artifact_id,),
        fingerprint_id="f" * 64,
        maximum_sample_bytes=1024,
    )
    assert first == second
    assert first.task_key == "schema.interpretation"
    assert 0 < len(first.samples) <= len(unknown)

    spec = DeclarativeParserSpec(**corpus["approved_parser"])
    record = _read_json(corpus["snapshots"][0])[0]
    parsed = execute_parser(
        spec, [_located(record)], artifact_id=artifact_id,
        export_snapshot_id=uuid4(),
    )
    assert parsed.events_emitted == 1 and parsed.rejected_records == 0
    assert parsed.events[0].parser_id == spec.parser_id


def test_opaque_token_recurs_across_services_without_assigned_meaning(corpus):
    fixture = corpus["opaque_token"]
    observations = tuple(
        IdentifierObservation(
            fixture["value"],
            source_artifact_id=uuid4(),
            service=item["service"],
            domain=item["domain"],
            schema_id=item["schema"],
            seen_at=datetime.fromisoformat(item["seen_at"].replace("Z", "+00:00")),
        )
        for item in fixture["observations"]
    )
    candidate = analyze_opaque_identifiers(observations)[0]

    assert candidate.occurrence_count == 3
    assert candidate.service_count == 2
    assert candidate.cross_schema_count == 2
    assert candidate.cross_domain_count == 2
    assert candidate.assigned_meaning is None
    assert fixture["value"] not in candidate.model_dump_json()


def test_date_only_time_does_not_become_midnight(corpus):
    spec = DeclarativeParserSpec(**corpus["approved_parser"]).model_copy(
        update={"temporal_precision": TemporalPrecision.DAY}
    )
    parsed = execute_parser(
        spec, [_located(corpus["date_only_record"])], artifact_id=uuid4(),
        export_snapshot_id=uuid4(),
    )
    event = parsed.events[0]
    assert event.occurred_at is None
    assert event.occurred_at_original == "2025-03-17"
    assert event.temporal_precision is TemporalPrecision.DAY
    assert event.timezone is None


def test_exact_coordinate_city_and_explicit_interactions_remain_distinct(corpus):
    exact_event = _event(locations=corpus["locations"]["exact"])
    city_event = _event(locations=corpus["locations"]["city"])
    geo = extract_geospatial_features((exact_event, city_event))
    precisions = {item.calculated_values["precision"] for item in geo}

    assert precisions == {
        GeospatialPrecision.EXACT_COORDINATE.value,
        GeospatialPrecision.CITY.value,
    }
    assert all("HOME" not in item.model_dump_json() for item in geo)

    interaction_event = _event(relationships=corpus["interactions"])
    interactions = extract_explicit_interactions((interaction_event,))
    assert {item.calculated_values["action"] for item in interactions} == {
        "SENT_TO", "FOLLOWED",
    }
    assert all(
        label not in item.model_dump_json()
        for item in interactions
        for label in ("FRIEND", "PARTNER", "COLLEAGUE")
    )


def test_controller_interest_is_separate_from_personal_behaviour(corpus):
    fixture = corpus["controller_interest"]
    now = datetime(2025, 6, 1, tzinfo=timezone.utc)
    evidence = uuid4()
    states = (
        TemporalState(
            subject_id="synthetic-subject",
            history_type=HistoryType.CONTROLLER_PROFILE,
            state_type="controller_interest",
            state_key=fixture["controller_state_key"],
            controller_observed_from=now,
            ingested_at=now,
            system_asserted_at=now,
            dimensions={"assigned": 1.0},
            evidence_event_ids=(evidence,),
            detector_id="synthetic.controller",
            detector_version="1.0.0",
        ),
        TemporalState(
            subject_id="synthetic-subject",
            history_type=HistoryType.PERSONAL_BEHAVIOURAL,
            state_type="interest_state",
            state_key=fixture["personal_state_key"],
            valid_from=now,
            ingested_at=now,
            system_asserted_at=now,
            dimensions={"intensity": 0.0},
            evidence_event_ids=(evidence,),
            detector_id="synthetic.behaviour",
            detector_version="1.0.0",
        ),
    )
    view = current_temporal_view(states, now=now + timedelta(days=1))
    by_history = {item.history_type: item for item in view.states}

    assert by_history[HistoryType.CONTROLLER_PROFILE].state_key == fixture["controller_state_key"]
    assert by_history[HistoryType.PERSONAL_BEHAVIOURAL].state_key == fixture["personal_state_key"]
    assert by_history[HistoryType.PERSONAL_BEHAVIOURAL].dimensions["intensity"] == 0.0


def test_project_burst_recurrent_topic_and_regime_shift_are_deterministic(corpus):
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    points = tuple(
        EvidenceSignalPoint(
            occurred_at=start + timedelta(days=index),
            value=value,
            evidence_event_ids=(uuid4(),),
        )
        for index, value in enumerate(corpus["project_burst"])
    )
    projects = detect_project_episode_candidates(
        points, subject_id="synthetic-subject", lookback=4, minimum_history=3
    )

    assert len(projects) == 1
    assert projects[0].machine_label is None
    assert recurrence_metrics(corpus["recurrent_topic"]).classification is RecurrenceClass.RECURRENT
    assert detect_change_points_pelt(
        corpus["regime_shift"], penalty=2, minimum_segment_size=2
    ) == (5,)


class _CheckpointConnection:
    """Small async persistence double that preserves CheckpointStore SQL semantics."""

    def __init__(self):
        self.rows: dict[tuple, dict] = {}

    async def fetchrow(self, _query, *args):
        if len(args) == 6:  # begin
            run_id, stage, item_key, key, content_hash, parser_version = args
            identity = (run_id, stage, item_key, key)
            existing = self.rows.get(identity)
            if existing is None:
                existing = {
                    "analysis_run_id": run_id, "stage": stage,
                    "item_key": item_key, "idempotency_key": key,
                    "content_hash": content_hash, "parser_version": parser_version,
                    "status": "running", "attempt": 1,
                    "progress": {}, "error": None,
                }
                self.rows[identity] = existing
            elif existing["status"] != "completed":
                existing = {**existing, "status": "running", "attempt": existing["attempt"] + 1}
                self.rows[identity] = existing
            return dict(existing)

        run_id, stage, item_key, key, status, progress, error = args
        identity = (run_id, stage, item_key, key)
        if identity not in self.rows:
            return None
        self.rows[identity] = {
            **self.rows[identity],
            "status": status,
            "progress": json.loads(progress),
            "error": json.loads(error) if error else None,
        }
        return dict(self.rows[identity])

    async def fetch(self, _query, run_id):
        return [dict(row) for key, row in self.rows.items() if key[0] == run_id]


@pytest.mark.asyncio
async def test_forced_checkpoint_interruption_resumes_and_completed_replay_is_idempotent(corpus):
    fixture = corpus["checkpoint_restart"]
    run_id = uuid4()
    store = CheckpointStore(_CheckpointConnection())

    started = await store.begin(
        analysis_run_id=run_id,
        stage=PipelineStage.PARSING,
        item_key=fixture["item_key"],
        content_hash=fixture["content_hash"],
        parser_version=fixture["parser_version"],
    )
    interrupted = await store.finish(
        started,
        status=CheckpointStatus.FAILED,
        progress={"records_seen": fixture["partial_records_seen"]},
        error={"code": fixture["error_code"]},
    )
    resumed = await store.begin(
        analysis_run_id=run_id,
        stage=PipelineStage.PARSING,
        item_key=fixture["item_key"],
        content_hash=fixture["content_hash"],
        parser_version=fixture["parser_version"],
    )
    completed = await store.finish(
        resumed,
        progress={"records_seen": fixture["completed_records_seen"]},
    )
    replay = await store.begin(
        analysis_run_id=run_id,
        stage=PipelineStage.PARSING,
        item_key=fixture["item_key"],
        content_hash=fixture["content_hash"],
        parser_version=fixture["parser_version"],
    )

    assert interrupted.status is CheckpointStatus.FAILED
    assert interrupted.progress["records_seen"] == fixture["partial_records_seen"]
    assert resumed.status is CheckpointStatus.RUNNING and resumed.attempt == 2
    assert completed.status is CheckpointStatus.COMPLETED
    assert completed.progress["records_seen"] == fixture["completed_records_seen"]
    assert replay.status is CheckpointStatus.COMPLETED and replay.attempt == 2
    assert len(await store.progress(run_id)) == 1
