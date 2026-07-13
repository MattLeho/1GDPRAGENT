from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4, uuid5

import pytest

from features.pipeline import extract_features, extract_partition_features
from ingestion.events import write_activity_events
from ingestion.models import (
    ActivityEvent, FeatureCandidate, FeatureCandidateStatus,
)
from ingestion.parser_runtime import EVENT_NAMESPACE


def _events(count: int) -> tuple[ActivityEvent, ...]:
    result = []
    for index in range(count):
        signature = hashlib.sha256(f"event:{index}".encode()).hexdigest()
        result.append(ActivityEvent(
            event_id=uuid5(EVENT_NAMESPACE, signature), record_signature=signature,
            subject_id="person", export_snapshot_id=uuid4(), artifact_id=uuid4(),
            data_domain="fixture", event_type="fixture.event",
            occurred_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            parser_id="fixture", parser_version="1", source_locator_id=uuid4(),
        ))
    return tuple(result)


class FixtureDetector:
    detector_id = "fixture.detector"
    detector_version = "1"

    def detect(self, events):
        for index, event in enumerate(events):
            yield FeatureCandidate(
                feature_type="fixture.signal", detector_id=self.detector_id,
                detector_version=self.detector_version, source_event_ids=(event.event_id,),
                calculated_values={"ordinal": index}, rule_result=True,
                candidate_status=(FeatureCandidateStatus.AMBIGUOUS if index in {10, 20} else FeatureCandidateStatus.DETERMINISTIC),
            )


def test_deterministic_partition_features_batch_only_small_residue():
    events = _events(1000)
    result = extract_features(
        events, [FixtureDetector()], analysis_run_id=uuid4(),
        maximum_sample_bytes=4096, maximum_candidates_per_bundle=64,
    )
    assert len(result.candidates) == 1000
    assert result.model_invocation_count == 1
    assert result.model_invocation_count < result.event_count / 100
    bundle = result.adjudication_bundles[0]
    assert len(bundle.samples) == 2
    assert len(json.dumps(bundle.samples, separators=(",", ":")).encode()) <= bundle.maximum_sample_bytes
    assert len(bundle.source_artifact_ids) == 2


def test_deterministic_candidates_never_create_model_work():
    class DeterministicOnly(FixtureDetector):
        def detect(self, events):
            for event in events:
                yield FeatureCandidate(
                    feature_type="fixture.rule", detector_id=self.detector_id,
                    detector_version=self.detector_version, source_event_ids=(event.event_id,),
                    calculated_values={"matched": True}, rule_result=True,
                    candidate_status=FeatureCandidateStatus.DETERMINISTIC,
                )
    result = extract_features(_events(50), [DeterministicOnly()], analysis_run_id=uuid4())
    assert result.model_invocation_count == 0


def test_detector_cannot_smuggle_ungrounded_or_misidentified_output():
    events = _events(1)
    class BadDetector(FixtureDetector):
        def detect(self, _events):
            yield FeatureCandidate(
                feature_type="bad", detector_id="different.detector", detector_version="1",
                source_event_ids=(uuid4(),), calculated_values={}, rule_result=False,
                candidate_status=FeatureCandidateStatus.UNKNOWN,
            )
    with pytest.raises(ValueError, match="identity"):
        extract_features(events, [BadDetector()], analysis_run_id=uuid4())


def test_feature_extraction_runs_over_real_event_parquet_partition(tmp_path):
    run_id = uuid4()
    written = write_activity_events(
        tmp_path, _events(100), analysis_run_id=run_id, partition_key="feature-fixture",
    )
    result = extract_partition_features(
        written.event_partition.path, [FixtureDetector()],
        analysis_run_id=run_id, maximum_sample_bytes=4096,
    )
    assert result.event_count == 100 and len(result.candidates) == 100
    assert result.model_invocation_count == 1
