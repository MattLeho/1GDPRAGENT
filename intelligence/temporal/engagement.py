"""Deterministic engagement profiles grounded in canonical action classes.

The five dimensions are transparent event counts.  Each canonical action class
maps to at most one dimension, and actions without a defensible mapping are
ignored.  This module does not infer motivation, personality, or intent.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime

from ingestion.models import ActionClass, ActivityEvent
from temporal.models import EngagementProfile


ACTION_DIMENSION: dict[ActionClass, str] = {
    ActionClass.CONSUMED: "consumption",
    ActionClass.VISITED: "consumption",
    ActionClass.PURCHASED: "consumption",
    ActionClass.SEARCHED: "investigation",
    ActionClass.CREATED: "creation",
    ActionClass.PUBLISHED: "creation",
    ActionClass.EDITED: "implementation",
    ActionClass.CODED: "implementation",
    ActionClass.COMMUNICATED: "communication",
}

_DIMENSIONS = (
    "consumption",
    "investigation",
    "creation",
    "implementation",
    "communication",
)


def _validate_window(window_start: datetime, window_end: datetime) -> None:
    if window_end <= window_start:
        raise ValueError("window_end must be later than window_start")
    if (window_start.tzinfo is None) != (window_end.tzinfo is None):
        raise ValueError("window boundaries must use compatible timezone awareness")


def _deduplicate(events: Iterable[ActivityEvent]) -> tuple[ActivityEvent, ...]:
    by_id: dict[object, ActivityEvent] = {}
    for event in events:
        previous = by_id.get(event.event_id)
        if previous is not None and previous != event:
            raise ValueError(f"conflicting duplicate event_id: {event.event_id}")
        by_id[event.event_id] = event
    return tuple(by_id[key] for key in sorted(by_id, key=str))


def _in_window(event: ActivityEvent, start: datetime, end: datetime) -> bool:
    if event.occurred_at is None:
        return False
    if (event.occurred_at.tzinfo is None) != (start.tzinfo is None):
        raise ValueError("event and window must use compatible timezone awareness")
    return start <= event.occurred_at < end


def build_engagement_profile(
    events: Iterable[ActivityEvent],
    *,
    subject_id: str,
    window_start: datetime,
    window_end: datetime,
) -> EngagementProfile | None:
    """Build one subject profile for a half-open time window.

    ``None`` means there is no dimension-bearing evidence in the requested
    window; a fabricated all-zero profile would not satisfy the frozen
    contract's evidence requirement.
    """

    _validate_window(window_start, window_end)
    counts = {dimension: 0.0 for dimension in _DIMENSIONS}
    evidence_ids = []
    for event in _deduplicate(events):
        if event.subject_id != subject_id or not _in_window(event, window_start, window_end):
            continue
        dimension = ACTION_DIMENSION.get(event.action_class)
        if dimension is None:
            continue
        counts[dimension] += 1.0
        evidence_ids.append(event.event_id)
    if not evidence_ids:
        return None
    return EngagementProfile(
        subject_id=subject_id,
        window_start=window_start,
        window_end=window_end,
        evidence_event_ids=tuple(sorted(evidence_ids, key=str)),
        **counts,
    )


def build_engagement_profiles(
    events: Iterable[ActivityEvent],
    *,
    window_start: datetime,
    window_end: datetime,
) -> tuple[EngagementProfile, ...]:
    """Build profiles for every evidenced subject in deterministic order."""

    materialised = _deduplicate(events)
    subjects: dict[str, list[ActivityEvent]] = defaultdict(list)
    for event in materialised:
        subjects[event.subject_id].append(event)
    profiles = (
        build_engagement_profile(
            subject_events,
            subject_id=subject_id,
            window_start=window_start,
            window_end=window_end,
        )
        for subject_id, subject_events in sorted(subjects.items())
    )
    return tuple(profile for profile in profiles if profile is not None)

