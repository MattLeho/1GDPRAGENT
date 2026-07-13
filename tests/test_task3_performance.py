from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID, uuid4, uuid5

import pytest

from benchmark.performance import (
    BENCHMARK_NAMESPACE,
    MemoryCheckpointBoundary,
    SemanticCountingBoundary,
    run_performance_benchmark,
)
from ingestion.fingerprints import fingerprint_json
from ingestion.models import (
    ActionClass,
    ActivityEvent,
    FeatureCandidate,
    FeatureCandidateStatus,
    PipelineStage,
    TemporalPrecision,
)


def _event(index: int, *, analysis_run_id: UUID) -> ActivityEvent:
    canonical = json.dumps(
        {"subject": "fixture-subject", "event_type": "fixture.view", "index": index},
        sort_keys=True,
        separators=(",", ":"),
    )
    signature = hashlib.sha256(canonical.encode()).hexdigest()
    return ActivityEvent(
        event_id=uuid5(BENCHMARK_NAMESPACE, signature),
        record_signature=signature,
        subject_id="fixture-subject",
        export_snapshot_id=uuid5(BENCHMARK_NAMESPACE, f"snapshot:{analysis_run_id}"),
        artifact_id=uuid5(BENCHMARK_NAMESPACE, f"event-artifact:{index}"),
        service="synthetic",
        product="performance-fixture",
        data_domain="activity",
        event_type="fixture.view",
        action_class=ActionClass.CONSUMED,
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        occurred_at_original="2026-01-01T00:00:00Z",
        temporal_precision=TemporalPrecision.SECOND,
        timezone="UTC",
        timezone_evidence="explicit_offset",
        object_type="fixture-record",
        object_id=str(index),
        object_value={"index": index},
        parser_id="fixture.parser",
        parser_version="1",
        source_locator_id=uuid5(BENCHMARK_NAMESPACE, f"locator:{index}"),
    )


class OneResidueDetector:
    detector_id = "fixture.residue"
    detector_version = "1"

    def detect(self, events):
        yield FeatureCandidate(
            feature_type="fixture_ambiguous_cluster",
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            source_event_ids=tuple(event.event_id for event in events[:10]),
            calculated_values={"bounded_event_count": min(10, len(events))},
            confidence=0.5,
            candidate_status=FeatureCandidateStatus.AMBIGUOUS,
        )


def _write_corpus(root, *, records_per_file: int = 1000):
    root.mkdir()
    rows = [
        {
            "subject": "fixture-subject",
            "timestamp": "2026-01-01T00:00:00Z",
            "object": {"id": index},
        }
        for index in range(records_per_file)
    ]
    raw = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    (root / "unknown-a.json").write_text(raw, encoding="utf-8")
    # Same structure fingerprint, different bytes: schema interpretation must
    # still be requested only once per fingerprint.
    rows[-1]["object"]["id"] = records_per_file + 1
    (root / "unknown-b.json").write_text(
        json.dumps(rows, sort_keys=True, separators=(",", ":")), encoding="utf-8"
    )
    (root / "approved.json").write_text(raw, encoding="utf-8")
    return rows


def test_performance_benchmark_proves_call_reduction_and_measures_local_pipeline(tmp_path):
    corpus = tmp_path / "corpus"
    rows = _write_corpus(corpus)
    analysis_run_id = uuid4()
    events = tuple(_event(index, analysis_run_id=analysis_run_id) for index in range(2000))
    approved_fingerprint = fingerprint_json(rows).fingerprint_id
    counter = SemanticCountingBoundary()
    checkpoints = MemoryCheckpointBoundary()

    report = run_performance_benchmark(
        corpus,
        tmp_path / "event-lake",
        events,
        analysis_run_id=analysis_run_id,
        # All three fixture files deliberately share this approved shape in
        # this case, proving approved schemas bypass interpretation entirely.
        approved_fingerprint_ids={approved_fingerprint},
        detectors=(OneResidueDetector(),),
        semantic_boundary=counter,
        checkpoint_boundary=checkpoints,
    )

    assert report.files_processed == 3
    assert report.bytes_inventoried == sum(path.stat().st_size for path in corpus.iterdir())
    assert report.records_processed == 3000
    assert report.events_written == 2000
    assert report.semantic_calls == 1  # one bounded adjudication bundle only
    assert report.semantic_call_to_record_ratio == pytest.approx(1 / 3000)
    assert report.semantic_calls_avoided == 2999
    assert report.model_call_reduction_fraction == pytest.approx(2999 / 3000)
    assert report.materially_lower_model_calls
    assert report.provider_invocations == report.network_invocations == 0
    assert report.parquet_partition_count == 2
    assert report.parquet_row_count == 4000  # logical events plus observations
    assert report.parquet_total_bytes > 0
    assert report.peak_memory_bytes is not None and report.peak_memory_bytes > 0
    assert report.restart_items_skipped == 3
    assert report.restart_items_reprocessed == 0
    assert report.restart_recovery_seconds >= 0
    assert {metric.stage for metric in report.stage_throughput} == {
        "inventory",
        "deterministic_file_pipeline",
        "event_lake_write",
        "feature_extraction",
        "restart_recovery",
    }
    assert all(metric.elapsed_seconds >= 0 for metric in report.stage_throughput)
    assert [(item.task_key, item.residue_key) for item in report.semantic_observations] == [
        ("semantic.adjudication", "adjudication:0")
    ]


def test_unknown_fingerprint_is_sampled_once_and_boundary_never_calls_provider(tmp_path):
    corpus = tmp_path / "corpus"
    _write_corpus(corpus, records_per_file=100)
    analysis_run_id = uuid4()
    counter = SemanticCountingBoundary()
    report = run_performance_benchmark(
        corpus,
        tmp_path / "event-lake",
        tuple(_event(index, analysis_run_id=analysis_run_id) for index in range(100)),
        analysis_run_id=analysis_run_id,
        semantic_boundary=counter,
    )

    schema_calls = [
        item for item in report.semantic_observations if item.task_key == "schema.interpretation"
    ]
    assert len(schema_calls) == 1
    assert schema_calls[0].residue_key.startswith("fingerprint:")
    assert schema_calls[0].payload_bytes < 40_000
    assert report.semantic_calls == 1
    assert report.semantic_call_to_record_ratio == pytest.approx(1 / 300)
    assert report.materially_lower_model_calls
    assert counter.provider_invocations == counter.network_invocations == 0


def test_checkpoint_boundary_uses_parser_version_and_content_hash():
    boundary = MemoryCheckpointBoundary()
    values = {
        "stage": PipelineStage.FAMILY_EXTRACTION,
        "item_key": "events.json",
        "content_hash": "a" * 64,
        "parser_version": "1",
    }
    boundary.mark_completed(**values)
    assert boundary.completed(**values)
    assert not boundary.completed(**(values | {"parser_version": "2"}))
    assert not boundary.completed(**(values | {"content_hash": "b" * 64}))


def test_benchmark_rejects_non_event_and_invalid_threshold(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "one.json").write_text("[{}]", encoding="utf-8")
    with pytest.raises(ValueError, match="normalised fixture event"):
        run_performance_benchmark(corpus, tmp_path / "out", (), analysis_run_id=uuid4())
    with pytest.raises(ValueError, match="threshold"):
        run_performance_benchmark(
            corpus,
            tmp_path / "out",
            (_event(0, analysis_run_id=uuid4()),),
            analysis_run_id=uuid4(),
            material_reduction_threshold=0,
        )
