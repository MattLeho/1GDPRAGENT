"""Deterministic, evidence-linked interest-state aggregation."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import ceil, isfinite, log
from typing import Iterable, Mapping, Sequence
from uuid import UUID

from ingestion.models import ActivityEvent, HistoryType

from .models import SixDimensionalInterestState, TopicAssignment, WeightedInterestView


INTEREST_DIMENSIONS = (
    "intensity", "persistence", "recurrence", "breadth", "novelty", "context_dispersion",
)


@dataclass(frozen=True)
class InterestAggregationConfig:
    """Versioned aggregation settings whose values fully determine a state."""

    detector_id: str = "interest.six-dimensional"
    detector_version: str = "1.0.0"
    activity_bin: timedelta = timedelta(days=1)

    def __post_init__(self) -> None:
        if self.activity_bin.total_seconds() <= 0:
            raise ValueError("activity_bin must be positive")
        if not self.detector_id or not self.detector_version:
            raise ValueError("detector identity and version are required")


def _event_context(event: ActivityEvent) -> tuple[str, str, str]:
    return (event.service or "unknown-service", event.data_domain or "unknown-domain", event.event_type or "unknown-event")


def _normalised_entropy(values: Sequence[tuple[str, str, str]]) -> float:
    counts = Counter(values)
    if len(counts) <= 1:
        return 0.0
    total = sum(counts.values())
    entropy = -sum((count / total) * log(count / total) for count in counts.values())
    return entropy / log(len(counts))


def _recurrence_score(active_bins: set[int]) -> float:
    ordered = sorted(active_bins)
    if len(ordered) < 2:
        return 0.0
    returns = sum(right - left > 1 for left, right in zip(ordered, ordered[1:]))
    return returns / (len(ordered) - 1)


def expand_hierarchical_assignment(assignment: TopicAssignment) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Expand a leaf assignment to root-to-leaf keys without semantic invention."""

    expanded: list[tuple[str, tuple[str, ...]]] = []
    for length in range(1, len(assignment.topic_path) + 1):
        path = assignment.topic_path[:length]
        topic_id = assignment.topic_id if length == len(assignment.topic_path) else "path:" + "/".join(
            component.replace("/", "%2F") for component in path
        )
        expanded.append((topic_id, path))
    return tuple(expanded)


def aggregate_interest_states(
    events: Iterable[ActivityEvent],
    assignments: Iterable[TopicAssignment],
    *,
    subject_id: str,
    window_start: datetime,
    window_end: datetime,
    previously_seen_event_ids: Iterable[UUID] = (),
    history_type: HistoryType = HistoryType.PERSONAL_BEHAVIOURAL,
    config: InterestAggregationConfig | None = None,
) -> tuple[SixDimensionalInterestState, ...]:
    """Calculate authoritative state for each evidence-bearing topic and ancestor.

    Intensity is events/window-day; persistence is active-bin coverage; recurrence
    measures returns following inactive bins; breadth counts distinct service,
    domain and event-type contexts; novelty is the unseen-event fraction; context
    dispersion is normalised Shannon entropy. The half-open window is [start,end).
    """

    if window_end <= window_start:
        raise ValueError("window_end must be after window_start")
    config = config or InterestAggregationConfig()
    event_by_id = {
        event.event_id: event for event in events
        if event.subject_id == subject_id and event.occurred_at is not None
        and window_start <= event.occurred_at < window_end
    }
    seen = set(previously_seen_event_ids)
    grouped: dict[tuple[str, tuple[str, ...]], set[UUID]] = {}
    for assignment in assignments:
        valid_ids = set(assignment.source_event_ids) & event_by_id.keys()
        if not valid_ids:
            continue
        for topic_key in expand_hierarchical_assignment(assignment):
            grouped.setdefault(topic_key, set()).update(valid_ids)

    window_seconds = (window_end - window_start).total_seconds()
    bin_seconds = config.activity_bin.total_seconds()
    total_bins = max(1, ceil(window_seconds / bin_seconds))
    duration_days = window_seconds / 86_400
    states: list[SixDimensionalInterestState] = []
    for (topic_id, topic_path), evidence_ids in sorted(grouped.items(), key=lambda item: item[0]):
        topic_events = sorted((event_by_id[value] for value in evidence_ids), key=lambda event: (event.occurred_at, str(event.event_id)))
        contexts = [_event_context(event) for event in topic_events]
        active = {int((event.occurred_at - window_start).total_seconds() // bin_seconds) for event in topic_events}
        ordered_ids = tuple(event.event_id for event in topic_events)
        states.append(SixDimensionalInterestState(
            subject_id=subject_id, history_type=history_type, topic_id=topic_id, topic_path=topic_path,
            window_start=window_start, window_end=window_end,
            intensity=len(topic_events) / duration_days, persistence=len(active) / total_bins,
            recurrence=_recurrence_score(active), breadth=float(len(set(contexts))),
            novelty=sum(value not in seen for value in ordered_ids) / len(ordered_ids),
            context_dispersion=_normalised_entropy(contexts), evidence_event_ids=ordered_ids,
            detector_id=config.detector_id, detector_version=config.detector_version,
        ))
    return tuple(states)


def derive_weighted_interest_view(
    state: SixDimensionalInterestState,
    weights: Mapping[str, float],
    *,
    configuration_id: str,
) -> WeightedInterestView:
    """Create a transparent weighted mean without replacing source dimensions."""

    if set(weights) != set(INTEREST_DIMENSIONS):
        missing = sorted(set(INTEREST_DIMENSIONS) - set(weights))
        extra = sorted(set(weights) - set(INTEREST_DIMENSIONS))
        raise ValueError(f"weights must cover exactly six dimensions; missing={missing}, extra={extra}")
    if any(not isfinite(value) or value < 0 for value in weights.values()):
        raise ValueError("weights must be finite and non-negative")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("at least one weight must be positive")
    weighted_value = sum(getattr(state, name) * weights[name] for name in INTEREST_DIMENSIONS) / total
    return WeightedInterestView(state=state, weights=dict(weights), weighted_value=weighted_value,
                                configuration_id=configuration_id, derived=True)
