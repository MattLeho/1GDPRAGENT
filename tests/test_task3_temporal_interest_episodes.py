from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from ingestion.models import ActionClass, ActivityEvent, TemporalPrecision
from temporal.episodes import (
    EvidenceSignalPoint,
    RecurrenceClass,
    apply_exponential_decay,
    decay_evidence_signal,
    detect_change_points_pelt,
    detect_project_episode_candidates,
    detect_topic_cluster_episode_candidates,
    past_only_recurrence_history,
    recurrence_metrics,
    rolling_robust_baseline,
)
from temporal.interest import (
    INTEREST_DIMENSIONS,
    aggregate_interest_states,
    derive_weighted_interest_view,
)
from temporal.models import EpisodeKind, TopicAssignment


UTC = timezone.utc
START = datetime(2025, 1, 1, tzinfo=UTC)


def _event(day: int, *, service: str = "search", domain: str = "research", event_type: str = "query") -> ActivityEvent:
    event_id = uuid4()
    return ActivityEvent(
        event_id=event_id,
        record_signature=event_id.hex * 2,
        subject_id="subject-1",
        export_snapshot_id=uuid4(),
        artifact_id=uuid4(),
        service=service,
        data_domain=domain,
        event_type=event_type,
        action_class=ActionClass.SEARCHED,
        occurred_at=START + timedelta(days=day),
        temporal_precision=TemporalPrecision.SECOND,
        parser_id="fixture",
        parser_version="1",
        source_locator_id=uuid4(),
    )


def test_interest_state_rolls_up_hierarchy_and_keeps_exact_evidence() -> None:
    events = (
        _event(0),
        _event(2, service="video", event_type="watch"),
        _event(3, service="search"),
    )
    assignment = TopicAssignment(
        topic_id="topic:python",
        topic_path=("technology", "programming", "python"),
        source_event_ids=tuple(event.event_id for event in events),
        assignment_method="reviewed-rule",
        assignment_version="1",
        confidence=1,
    )

    states = aggregate_interest_states(
        events, (assignment,), subject_id="subject-1", window_start=START,
        window_end=START + timedelta(days=4), previously_seen_event_ids=(events[0].event_id,),
    )

    assert [state.topic_path for state in states] == [
        ("technology",), ("technology", "programming"), ("technology", "programming", "python")
    ]
    leaf = states[-1]
    assert leaf.topic_id == "topic:python"
    assert leaf.evidence_event_ids == tuple(event.event_id for event in events)
    assert leaf.intensity == pytest.approx(0.75)
    assert leaf.persistence == pytest.approx(0.75)
    assert leaf.recurrence == pytest.approx(0.5)
    assert leaf.breadth == 2
    assert leaf.novelty == pytest.approx(2 / 3)
    assert 0 < leaf.context_dispersion <= 1


def test_interest_ignores_foreign_unknown_and_out_of_window_evidence() -> None:
    valid = _event(0)
    outside = _event(8)
    foreign = _event(1).model_copy(update={"subject_id": "someone-else"})
    assignment = TopicAssignment(
        topic_id="topic:x", topic_path=("x",),
        source_event_ids=(valid.event_id, outside.event_id, foreign.event_id, uuid4()),
        assignment_method="rule", assignment_version="1", confidence=1,
    )
    states = aggregate_interest_states(
        (valid, outside, foreign), (assignment,), subject_id="subject-1",
        window_start=START, window_end=START + timedelta(days=2),
    )
    assert len(states) == 1
    assert states[0].evidence_event_ids == (valid.event_id,)


def test_weighted_view_is_explicit_configured_derivation() -> None:
    event = _event(0)
    assignment = TopicAssignment(
        topic_id="topic:x", topic_path=("x",), source_event_ids=(event.event_id,),
        assignment_method="rule", assignment_version="1", confidence=1,
    )
    state = aggregate_interest_states(
        (event,), (assignment,), subject_id="subject-1", window_start=START,
        window_end=START + timedelta(days=1),
    )[0]
    weights = {name: (2.0 if name == "intensity" else 1.0) for name in INTEREST_DIMENSIONS}
    view = derive_weighted_interest_view(state, weights, configuration_id="ui-default-v1")
    assert view.state is state
    assert view.derived is True
    assert view.configuration_id == "ui-default-v1"
    assert view.weighted_value == pytest.approx(
        sum(getattr(state, name) * weights[name] for name in INTEREST_DIMENSIONS) / sum(weights.values())
    )
    with pytest.raises(ValueError, match="exactly six"):
        derive_weighted_interest_view(state, {"intensity": 1}, configuration_id="bad")


def _signal(values: list[float], topics: tuple[str, ...] = ()) -> tuple[EvidenceSignalPoint, ...]:
    return tuple(EvidenceSignalPoint(START + timedelta(days=index), value, (uuid4(),), topics)
                 for index, value in enumerate(values))


def test_rolling_median_mad_has_no_lookahead_and_detects_burst() -> None:
    result = rolling_robust_baseline(_signal([1, 1, 1, 1, 20]), lookback=4, minimum_history=3)
    assert all(item.baseline_median is None for item in result[:3])
    assert result[3].is_burst is False
    assert result[4].baseline_median == 1
    assert result[4].baseline_mad == 0
    assert result[4].is_burst is True


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([True, True, True], RecurrenceClass.CONTINUOUS),
        ([True, False, True, False, True], RecurrenceClass.RECURRENT),
        ([False, True, False], RecurrenceClass.ONE_OFF),
        ([False, False], RecurrenceClass.ONE_OFF),
    ],
)
def test_recurrence_classification(values: list[bool], expected: RecurrenceClass) -> None:
    assert recurrence_metrics(values).classification is expected


def test_recurrence_metrics_are_complete_and_prefix_history_is_past_only() -> None:
    active = [True, False, False, True, True, False]
    intensities = [2, 0, 0, 4, 6, 0]
    metric = recurrence_metrics(active, intensity_values=intensities)
    assert metric.active_periods == 3
    assert metric.dormant_periods == 3
    assert metric.mean_dormancy == 2
    assert metric.return_count == 1
    assert metric.return_intensity == 5
    history = past_only_recurrence_history(active, intensity_values=intensities)
    extended = past_only_recurrence_history(active + [True, False], intensity_values=intensities + [9, 0])
    assert history == extended[:len(history)]
    assert history == tuple(
        recurrence_metrics(active[:end], intensity_values=intensities[:end])
        for end in range(1, len(active) + 1)
    )


def test_pelt_finds_deterministic_univariate_and_multivariate_regime_shift() -> None:
    scalar = [0.0] * 10 + [12.0] * 10
    vector = [[0.0, 1.0]] * 10 + [[12.0, 8.0]] * 10
    assert detect_change_points_pelt(scalar, penalty=2, minimum_segment_size=3) == (10,)
    assert detect_change_points_pelt(vector, penalty=2, minimum_segment_size=3) == (10,)
    assert detect_change_points_pelt([0.0] * 8 + [100.0] + [0.0] * 8,
                                     penalty=2, minimum_segment_size=3) == ()


def test_decay_preserves_input_and_historical_evidence() -> None:
    values = [8.0, 0.0, 0.0]
    decayed = apply_exponential_decay(values, half_life_periods=1)
    assert values == [8.0, 0.0, 0.0]
    assert decayed == pytest.approx((8.0, 4.0, 2.0))
    points = _signal(values)
    summary = decay_evidence_signal(points, half_life_periods=1)
    assert summary.historical_values == tuple(values)
    assert summary.historical_peak == 8
    assert summary.current_signal == pytest.approx(2)
    assert set(summary.evidence_event_ids) == {
        event_id for point in points for event_id in point.evidence_event_ids
    }


def test_episode_candidates_are_deterministic_evidence_linked_and_unlabelled() -> None:
    project_points = _signal([1, 1, 1, 1, 20, 22])
    first = detect_project_episode_candidates(
        project_points, subject_id="subject-1", lookback=4, minimum_history=3
    )
    second = detect_project_episode_candidates(
        project_points, subject_id="subject-1", lookback=4, minimum_history=3
    )
    assert len(first) == 1
    assert first == second
    assert first[0].episode_kind is EpisodeKind.PROJECT
    assert first[0].machine_label is None
    assert set(first[0].evidence_event_ids) == {
        *project_points[4].evidence_event_ids, *project_points[5].evidence_event_ids,
    }
    isolated = _signal([1, 1, 1, 20])
    assert detect_project_episode_candidates(
        isolated, subject_id="subject-1", lookback=3, minimum_history=3
    ) == ()
    assert len(detect_project_episode_candidates(
        isolated, subject_id="subject-1", lookback=3, minimum_history=3,
        minimum_evidence_events=1,
    )) == 1

    cluster_points = _signal([0, 2, 3, 0], topics=("topic:a", "topic:b"))
    clusters = detect_topic_cluster_episode_candidates(cluster_points, subject_id="subject-1")
    assert len(clusters) == 1
    assert clusters[0].episode_kind is EpisodeKind.TOPIC_CLUSTER
    assert clusters[0].start_at == cluster_points[1].occurred_at
    assert clusters[0].end_at == cluster_points[2].occurred_at
    assert clusters[0].machine_label is None
