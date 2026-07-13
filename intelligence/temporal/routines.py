"""Deterministic routine distributions and distribution drift.

Routine dimensions come only from event fields and evidence-linked topic
assignments.  No bucket is interpreted as a lifestyle, personality, or social
relationship label.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from ingestion.models import ActivityEvent
from temporal.models import RoutineDistribution, RoutineDrift, TopicAssignment


DETECTOR_ID = "task3.routine_distribution"
DETECTOR_VERSION = "1.0.0"
DRIFT_DETECTOR_ID = "task3.routine_drift"
DRIFT_DETECTOR_VERSION = "1.0.0"

_DIMENSIONS = ("hour", "day", "service", "event", "topic")
_DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
_UNKNOWN = "UNKNOWN"


def _validate_window(window_start: datetime, window_end: datetime) -> None:
    if window_end <= window_start:
        raise ValueError("window_end must be later than window_start")
    if (window_start.tzinfo is None) != (window_end.tzinfo is None):
        raise ValueError("window boundaries must use compatible timezone awareness")


def _deduplicate(events: Iterable[ActivityEvent]) -> tuple[ActivityEvent, ...]:
    by_id: dict[UUID, ActivityEvent] = {}
    for event in events:
        previous = by_id.get(event.event_id)
        if previous is not None and previous != event:
            raise ValueError(f"conflicting duplicate event_id: {event.event_id}")
        by_id[event.event_id] = event
    return tuple(by_id[key] for key in sorted(by_id, key=str))


def _topics_by_event(assignments: Iterable[TopicAssignment]) -> dict[UUID, tuple[str, ...]]:
    topic_ids: dict[UUID, set[str]] = defaultdict(set)
    for assignment in assignments:
        for event_id in assignment.source_event_ids:
            topic_ids[event_id].add(assignment.topic_id)
    return {event_id: tuple(sorted(topics)) for event_id, topics in topic_ids.items()}


def build_routine_distributions(
    events: Iterable[ActivityEvent],
    *,
    window_start: datetime,
    window_end: datetime,
    topic_assignments: Iterable[TopicAssignment] = (),
) -> tuple[RoutineDistribution, ...]:
    """Build five routine dimensions for each evidenced subject.

    The time window is half-open.  Events without an occurrence time cannot be
    placed in a routine window and are excluded.  Missing service or topic
    evidence is preserved in an explicit ``UNKNOWN`` bucket.
    """

    _validate_window(window_start, window_end)
    event_topics = _topics_by_event(topic_assignments)
    buckets: dict[tuple[str, str, str], set[UUID]] = defaultdict(set)
    totals: dict[tuple[str, str], int] = defaultdict(int)

    for event in _deduplicate(events):
        occurred_at = event.occurred_at
        if occurred_at is None:
            continue
        if (occurred_at.tzinfo is None) != (window_start.tzinfo is None):
            raise ValueError("event and window must use compatible timezone awareness")
        if not window_start <= occurred_at < window_end:
            continue
        values = {
            "hour": (f"{occurred_at.hour:02d}",),
            "day": (_DAY_NAMES[occurred_at.weekday()],),
            "service": ((event.service or _UNKNOWN).strip() or _UNKNOWN,),
            "event": ((event.event_type or _UNKNOWN).strip() or _UNKNOWN,),
            "topic": event_topics.get(event.event_id, (_UNKNOWN,)),
        }
        for dimension in _DIMENSIONS:
            dimension_buckets = tuple(sorted(set(values[dimension])))
            for bucket in dimension_buckets:
                buckets[(event.subject_id, dimension, bucket)].add(event.event_id)
                totals[(event.subject_id, dimension)] += 1

    result = []
    for (subject_id, dimension, bucket), evidence_ids in sorted(buckets.items()):
        total = totals[(subject_id, dimension)]
        result.append(RoutineDistribution(
            subject_id=subject_id,
            window_start=window_start,
            window_end=window_end,
            dimension=dimension,
            bucket=bucket,
            event_count=len(evidence_ids),
            proportion=len(evidence_ids) / total,
            evidence_event_ids=tuple(sorted(evidence_ids, key=str)),
            detector_id=DETECTOR_ID,
            detector_version=DETECTOR_VERSION,
        ))
    return tuple(result)


def _distribution_map(
    distributions: Iterable[RoutineDistribution],
) -> dict[tuple[str, str], tuple[dict[str, float], set[UUID], datetime, datetime]]:
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for item in distributions:
        key = (item.subject_id, item.dimension)
        current = grouped.setdefault(key, {
            "values": {}, "evidence": set(), "start": item.window_start, "end": item.window_end,
        })
        if current["start"] != item.window_start or current["end"] != item.window_end:
            raise ValueError("each subject/dimension distribution must describe one window")
        values = current["values"]
        assert isinstance(values, dict)
        if item.bucket in values:
            raise ValueError(f"duplicate routine bucket: {key!r} / {item.bucket!r}")
        values[item.bucket] = item.proportion
        evidence = current["evidence"]
        assert isinstance(evidence, set)
        evidence.update(item.evidence_event_ids)
    return {
        key: (data["values"], data["evidence"], data["start"], data["end"])
        for key, data in grouped.items()
    }


def build_routine_drift(
    baseline: Iterable[RoutineDistribution],
    current: Iterable[RoutineDistribution],
) -> tuple[RoutineDrift, ...]:
    """Compare matched subject/dimensions using total-variation distance."""

    baseline_map = _distribution_map(baseline)
    current_map = _distribution_map(current)
    result = []
    for subject_id, dimension in sorted(set(baseline_map) & set(current_map)):
        baseline_values, baseline_evidence, baseline_start, baseline_end = baseline_map[(subject_id, dimension)]
        current_values, current_evidence, current_start, current_end = current_map[(subject_id, dimension)]
        buckets = set(baseline_values) | set(current_values)
        distance = 0.5 * sum(
            abs(baseline_values.get(bucket, 0.0) - current_values.get(bucket, 0.0))
            for bucket in buckets
        )
        result.append(RoutineDrift(
            subject_id=subject_id,
            dimension=dimension,
            baseline_start=baseline_start,
            baseline_end=baseline_end,
            current_start=current_start,
            current_end=current_end,
            baseline_distribution=dict(sorted(baseline_values.items())),
            current_distribution=dict(sorted(current_values.items())),
            total_variation_distance=min(1.0, max(0.0, distance)),
            evidence_event_ids=tuple(sorted(baseline_evidence | current_evidence, key=str)),
            detector_id=DRIFT_DETECTOR_ID,
            detector_version=DRIFT_DETECTOR_VERSION,
        ))
    return tuple(result)

