from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import uuid4

import pytest

from ingestion.models import HistoryType, TemporalState
from temporal.eras import (
    EvidenceConstrainedMachineLabel,
    HumanEraLabel,
    MonthlyFeatureVector,
    build_personal_eras,
)
from temporal.models import DeltaStatus, DriftType
from temporal.views import (
    SnapshotEntity,
    SnapshotEntityLevel,
    as_of_temporal_view,
    compare_export_snapshots,
    current_temporal_view,
    query_temporal_view,
)


def _at(year: int, month: int, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def test_monthly_vectors_detect_deterministic_change_and_make_contiguous_eras():
    events = [uuid4() for _ in range(6)]
    vectors = tuple(
        MonthlyFeatureVector(
            month=date(2025, index + 1, 1),
            dimensions={"activity": value, "creation": value / 2},
            evidence_event_ids=(events[index],),
        )
        for index, value in enumerate((0.0, 0.0, 0.0, 10.0, 10.0, 10.0))
    )
    machine = EvidenceConstrainedMachineLabel(
        label="low-activity period",
        evidence_event_ids=(events[0],),
        execution_record_id=uuid4(),
        labelling_method="bounded-evidence-label",
        labelling_version="1",
    )
    result = build_personal_eras(
        vectors,
        subject_id="subject-1",
        machine_labels={0: machine},
        human_labels={1: HumanEraLabel(label="Human-confirmed later period", labelled_by="reviewer-1")},
    )
    repeated = build_personal_eras(
        vectors,
        subject_id="subject-1",
        machine_labels={0: machine},
        human_labels={1: HumanEraLabel(label="Human-confirmed later period", labelled_by="reviewer-1")},
    )

    assert result.change_point_indices == (3,)
    assert len(result.eras) == 2
    assert result.eras[0].end_at == result.eras[1].start_at == _at(2025, 4)
    assert result.eras[0].machine_label == "low-activity period"
    assert result.eras[0].human_label is None
    assert result.eras[1].machine_label is None
    assert result.eras[1].human_label == "Human-confirmed later period"
    assert {item.label_source for item in result.label_assignments} == {"machine", "human"}
    machine_assignment = next(
        item for item in result.label_assignments if item.label_source == "machine"
    )
    human_assignment = next(
        item for item in result.label_assignments if item.label_source == "human"
    )
    assert machine_assignment.execution_record_id is not None
    assert machine_assignment.labelled_by is None
    assert human_assignment.execution_record_id is None
    assert human_assignment.labelled_by == "reviewer-1"
    assert result.eras[0].era_id == repeated.eras[0].era_id
    assert result.eras[1].era_id == repeated.eras[1].era_id


def test_era_machine_labels_are_evidence_constrained_and_gaps_force_boundaries():
    first, second, unrelated = uuid4(), uuid4(), uuid4()
    vectors = (
        MonthlyFeatureVector(
            month=date(2025, 1, 1), dimensions={"activity": 1},
            evidence_event_ids=(first,),
        ),
        MonthlyFeatureVector(
            month=date(2025, 3, 1), dimensions={"activity": 1},
            evidence_event_ids=(second,),
        ),
    )
    result = build_personal_eras(vectors, subject_id="subject-1")
    assert result.change_point_indices == (1,)
    assert len(result.eras) == 2

    label = EvidenceConstrainedMachineLabel(
        label="unsupported label", evidence_event_ids=(unrelated,),
        execution_record_id=uuid4(),
        labelling_method="fixture", labelling_version="1",
    )
    with pytest.raises(ValueError, match="evidence outside"):
        build_personal_eras(vectors, subject_id="subject-1", machine_labels={0: label})


def test_bitemporal_view_distinguishes_valid_time_from_system_discovery():
    locator = uuid4()
    states = (
        TemporalState(
            subject_id="subject-1", state_type="interest_state", state_key="topic:travel",
            history_type=HistoryType.PERSONAL_BEHAVIOURAL,
            dimensions={"intensity": 1}, valid_from=_at(2025, 1),
            ingested_at=_at(2025, 1, 10), system_asserted_at=_at(2025, 1, 10),
            superseded_at=_at(2025, 3), evidence_event_ids=(locator,),
            detector_id="fixture", detector_version="1",
        ),
        TemporalState(
            subject_id="subject-1", state_type="interest_state", state_key="topic:travel",
            history_type=HistoryType.PERSONAL_BEHAVIOURAL,
            dimensions={"intensity": 4}, valid_from=_at(2025, 1),
            ingested_at=_at(2025, 3), system_asserted_at=_at(2025, 3),
            evidence_event_ids=(locator,), detector_id="fixture", detector_version="1",
        ),
        TemporalState(
            subject_id="subject-1", state_type="activity", state_key="event:late",
            history_type=HistoryType.PERSONAL_BEHAVIOURAL,
            dimensions={"event_count": 1}, occurred_at=_at(2024, 12),
            exported_at=_at(2025, 3, 15), ingested_at=_at(2025, 4),
            system_asserted_at=_at(2025, 4), evidence_event_ids=(locator,),
            detector_id="fixture", detector_version="1",
        ),
        TemporalState(
            subject_id="subject-1", state_type="controller_interest", state_key="segment:traveller",
            history_type=HistoryType.CONTROLLER_PROFILE,
            dimensions={"assigned": 1}, controller_observed_from=_at(2025, 2),
            ingested_at=_at(2025, 2, 10), system_asserted_at=_at(2025, 2, 10),
            evidence_event_ids=(locator,), detector_id="fixture", detector_version="1",
        ),
        TemporalState(
            subject_id="subject-1", state_type="schema_understanding", state_key="schema:takeout-v1",
            history_type=HistoryType.SYSTEM_UNDERSTANDING,
            dimensions={"approved": 1}, ingested_at=_at(2025, 2, 5),
            system_asserted_at=_at(2025, 2, 5), evidence_event_ids=(locator,),
            detector_id="fixture", detector_version="1",
        ),
    )

    early = query_temporal_view(
        states, valid_at=_at(2025, 2), known_at=_at(2025, 2, 15)
    )
    corrected = query_temporal_view(
        states, valid_at=_at(2025, 2), known_at=_at(2025, 4, 15)
    )
    late_before_discovery = query_temporal_view(
        states, valid_at=_at(2024, 12, 15), known_at=_at(2025, 2, 15)
    )
    late_after_discovery = query_temporal_view(
        states, valid_at=_at(2024, 12, 15), known_at=_at(2025, 4, 15)
    )

    assert {(item.state_type, item.state_key) for item in early.states} == {
        ("interest_state", "topic:travel"),
        ("controller_interest", "segment:traveller"),
        ("schema_understanding", "schema:takeout-v1"),
    }
    corrected_interest = next(item for item in corrected.states if item.state_key == "topic:travel")
    assert corrected_interest.dimensions["intensity"] == 4
    assert "event:late" not in {item.state_key for item in late_before_discovery.states}
    assert "event:late" in {item.state_key for item in late_after_discovery.states}
    # Derived views retain source identifiers and cannot mutate the frozen input.
    assert corrected.derived is True
    assert states[0].dimensions == {"intensity": 1}
    assert all(item.evidence_event_ids for item in corrected.states)


def test_now_and_as_of_are_explicit_derived_views():
    state = TemporalState(
        subject_id="s", state_type="state", state_key="k",
        history_type=HistoryType.SYSTEM_UNDERSTANDING, dimensions={"value": 1},
        system_asserted_at=_at(2025, 1), ingested_at=_at(2025, 1),
        detector_id="fixture", detector_version="1",
    )
    now_view = current_temporal_view((state,), now=_at(2025, 2))
    old_view = as_of_temporal_view((state,), as_of=_at(2024, 12))
    assert now_view.mode == "NOW" and now_view.derived and len(now_view.states) == 1
    assert old_view.mode == "AS_OF" and old_view.derived and old_view.states == ()


def test_export_delta_covers_all_levels_statuses_and_separate_drift_histories():
    before_id, after_id = uuid4(), uuid4()
    before = (
        SnapshotEntity(
            level=SnapshotEntityLevel.ASSERTION, entity_key="assertion:stable",
            value={"value": 1}, drift_type=DriftType.PERSONAL,
        ),
        SnapshotEntity(
            level=SnapshotEntityLevel.ASSERTION, entity_key="assertion:removed",
            value={"segment": "A"}, drift_type=DriftType.CONTROLLER,
        ),
        SnapshotEntity(
            level=SnapshotEntityLevel.SCHEMA, entity_key="schema:takeout",
            value={"version": 1}, drift_type=DriftType.UNDERSTANDING,
        ),
    )
    after = (
        SnapshotEntity(
            level=SnapshotEntityLevel.ASSERTION, entity_key="assertion:stable",
            value={"value": 1}, drift_type=DriftType.PERSONAL,
        ),
        SnapshotEntity(
            level=SnapshotEntityLevel.SCHEMA, entity_key="schema:takeout",
            value={"version": 2}, drift_type=DriftType.UNDERSTANDING,
        ),
        SnapshotEntity(
            level=SnapshotEntityLevel.EVENT_OBSERVATION, entity_key="event:old-activity",
            value={"occurred_at": "2020-01-01"}, drift_type=DriftType.PERSONAL,
        ),
    )
    report = compare_export_snapshots(
        before_snapshot_id=before_id, after_snapshot_id=after_id,
        before=before, after=after,
    )
    statuses = {delta.entity_key: delta.status for delta in report.deltas}

    assert statuses == {
        "assertion:stable": DeltaStatus.UNCHANGED,
        "assertion:removed": DeltaStatus.REMOVED_FROM_EXPORT,
        "schema:takeout": DeltaStatus.MODIFIED,
        "event:old-activity": DeltaStatus.NEW,
    }
    assert len(report.personal_drift) == 2
    assert len(report.controller_drift) == 1
    assert len(report.understanding_drift) == 1
    assert {delta.entity_type for delta in report.deltas} == {
        "assertion", "schema", "event_observation"
    }
    assert all("newly collected" not in delta.interpretation.lower() for delta in report.deltas)
    newly_seen = next(delta for delta in report.deltas if delta.status is DeltaStatus.NEW)
    assert "newly observed by this system" in newly_seen.interpretation
    assert "controller collection time is not established" in newly_seen.interpretation


def test_export_delta_rejects_ambiguous_duplicate_logical_keys():
    snapshot_a, snapshot_b = uuid4(), uuid4()
    duplicate = SnapshotEntity(
        level=SnapshotEntityLevel.ASSERTION, entity_key="same",
        value=1, drift_type=DriftType.PERSONAL,
    )
    with pytest.raises(ValueError, match="duplicate before"):
        compare_export_snapshots(
            before_snapshot_id=snapshot_a, after_snapshot_id=snapshot_b,
            before=(duplicate, duplicate), after=(),
        )
