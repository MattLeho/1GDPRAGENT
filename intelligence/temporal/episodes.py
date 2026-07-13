"""Robust deterministic time-series and episode-candidate detection."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import exp, isfinite, log
from statistics import median
from typing import Sequence
from uuid import UUID, uuid5

import numpy as np
import ruptures as rpt

from ingestion.models import HistoryType

from .models import EpisodeCandidate, EpisodeKind


EPISODE_NAMESPACE = UUID("f409a5d9-4ba6-45b5-8f7a-b6357fb4f26b")


@dataclass(frozen=True)
class EvidenceSignalPoint:
    occurred_at: datetime
    value: float
    evidence_event_ids: tuple[UUID, ...]
    topic_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.evidence_event_ids:
            raise ValueError("signal points require evidence_event_ids")


@dataclass(frozen=True)
class BaselinePoint:
    occurred_at: datetime
    value: float
    baseline_median: float | None
    baseline_mad: float | None
    robust_z_score: float | None
    is_burst: bool


class RecurrenceClass(str, Enum):
    CONTINUOUS = "continuous"
    RECURRENT = "recurrent"
    ONE_OFF = "one-off"


@dataclass(frozen=True)
class RecurrenceMetrics:
    active_periods: int
    dormant_periods: int
    span_periods: int
    active_fraction: float
    mean_dormancy: float
    return_count: int
    return_intensity: float
    longest_run: int
    classification: RecurrenceClass


@dataclass(frozen=True)
class DecayedSignal:
    """A display signal that retains its complete historical values and evidence."""

    historical_values: tuple[float, ...]
    decayed_values: tuple[float, ...]
    historical_peak: float
    current_signal: float
    decay_rate: float
    evidence_event_ids: tuple[UUID, ...]


def rolling_robust_baseline(
    points: Sequence[EvidenceSignalPoint], *, lookback: int = 7, z_threshold: float = 3.5,
    minimum_history: int = 3, minimum_absolute_increase: float = 0.0,
) -> tuple[BaselinePoint, ...]:
    """Median/MAD baseline using only earlier points (no look-ahead leakage)."""

    if lookback < 1 or minimum_history < 1:
        raise ValueError("lookback and minimum_history must be positive")
    if z_threshold < 0 or minimum_absolute_increase < 0:
        raise ValueError("thresholds must be non-negative")
    if any(not isfinite(point.value) for point in points):
        raise ValueError("signal values must be finite")
    if list(points) != sorted(points, key=lambda point: point.occurred_at):
        raise ValueError("points must be ordered by occurred_at")
    output: list[BaselinePoint] = []
    for index, point in enumerate(points):
        history = [prior.value for prior in points[max(0, index - lookback):index]]
        if len(history) < minimum_history:
            output.append(BaselinePoint(point.occurred_at, point.value, None, None, None, False))
            continue
        centre = float(median(history))
        mad = float(median(abs(value - centre) for value in history))
        increase = point.value - centre
        if mad == 0:
            z_score = float("inf") if increase > 0 else (float("-inf") if increase < 0 else 0.0)
        else:
            z_score = increase / (1.4826 * mad)
        output.append(BaselinePoint(
            point.occurred_at, point.value, centre, mad, z_score,
            increase >= minimum_absolute_increase and increase > 0 and z_score >= z_threshold,
        ))
    return tuple(output)


def recurrence_metrics(
    active_values: Sequence[bool], *, intensity_values: Sequence[float] | None = None,
) -> RecurrenceMetrics:
    """Classify one history available as of its final period.

    ``return_intensity`` is the mean intensity of active periods after the first
    active run. With no explicit intensities, active periods have intensity 1.
    Interior inactive runs determine mean dormancy; inactive leading/trailing
    observation periods remain visible in ``dormant_periods``.
    """

    if intensity_values is not None and len(intensity_values) != len(active_values):
        raise ValueError("intensity_values must align one-to-one with active_values")
    intensities = tuple(float(value) for value in intensity_values) if intensity_values is not None else tuple(
        1.0 if active else 0.0 for active in active_values
    )
    if any(not isfinite(value) or value < 0 for value in intensities):
        raise ValueError("intensity values must be finite and non-negative")

    active_indices = [index for index, active in enumerate(active_values) if active]
    if not active_indices:
        return RecurrenceMetrics(
            0, len(active_values), len(active_values), 0.0, 0.0, 0, 0.0, 0,
            RecurrenceClass.ONE_OFF,
        )
    runs: list[list[int]] = [[active_indices[0]]]
    dormancies: list[int] = []
    for left, right in zip(active_indices, active_indices[1:]):
        if right == left + 1:
            runs[-1].append(right)
        else:
            dormancies.append(right - left - 1)
            runs.append([right])
    return_count = max(0, len(runs) - 1)
    active_fraction = len(active_indices) / len(active_values) if active_values else 0.0
    if return_count:
        classification = RecurrenceClass.RECURRENT
    elif len(active_indices) == 1:
        classification = RecurrenceClass.ONE_OFF
    else:
        classification = RecurrenceClass.CONTINUOUS
    returned_indices = [index for run in runs[1:] for index in run]
    return_intensity = (
        sum(intensities[index] for index in returned_indices) / len(returned_indices)
        if returned_indices else 0.0
    )
    return RecurrenceMetrics(
        active_periods=len(active_indices),
        dormant_periods=len(active_values) - len(active_indices),
        span_periods=len(active_values),
        active_fraction=active_fraction,
        mean_dormancy=sum(dormancies) / len(dormancies) if dormancies else 0.0,
        return_count=return_count,
        return_intensity=return_intensity,
        longest_run=max(len(run) for run in runs),
        classification=classification,
    )


def past_only_recurrence_history(
    active_values: Sequence[bool], *, intensity_values: Sequence[float] | None = None,
) -> tuple[RecurrenceMetrics, ...]:
    """Return an as-of recurrence state for every prefix without future leakage."""

    if intensity_values is not None and len(intensity_values) != len(active_values):
        raise ValueError("intensity_values must align one-to-one with active_values")
    return tuple(
        recurrence_metrics(
            active_values[:end],
            intensity_values=None if intensity_values is None else intensity_values[:end],
        )
        for end in range(1, len(active_values) + 1)
    )


def detect_change_points_pelt(
    values: Sequence[float] | Sequence[Sequence[float]], *, penalty: float = 3.0,
    model: str = "l1", minimum_segment_size: int = 2,
) -> tuple[int, ...]:
    """Return zero-based segment boundaries from deterministic PELT.

    Both scalar and multivariate feature histories are accepted. The terminal
    boundary emitted by ruptures is excluded, leaving actual change indices only.
    """

    if penalty <= 0 or minimum_segment_size < 1:
        raise ValueError("penalty and minimum_segment_size must be positive")
    if len(values) < minimum_segment_size * 2:
        return ()
    signal = [[float(value)] for value in values] if not isinstance(values[0], Sequence) else [
        [float(component) for component in value] for value in values
    ]
    if any(len(row) != len(signal[0]) for row in signal):
        raise ValueError("all feature vectors must have equal width")
    if any(not isfinite(component) for row in signal for component in row):
        raise ValueError("signal values must be finite")
    array = np.asarray(signal, dtype=float)
    boundaries = rpt.Pelt(model=model, min_size=minimum_segment_size, jump=1).fit(array).predict(pen=penalty)
    return tuple(int(boundary) for boundary in boundaries if 0 < boundary < len(values))


def apply_exponential_decay(values: Sequence[float], *, half_life_periods: float) -> tuple[float, ...]:
    """Return a decayed signal copy; historical input is never mutated/deleted."""

    if half_life_periods <= 0:
        raise ValueError("half_life_periods must be positive")
    if any(not isfinite(value) for value in values):
        raise ValueError("signal values must be finite")
    factor = exp(-log(2) / half_life_periods)
    accumulator = 0.0
    output: list[float] = []
    for value in values:
        accumulator = float(value) + factor * accumulator
        output.append(accumulator)
    return tuple(output)


def decay_evidence_signal(
    points: Sequence[EvidenceSignalPoint], *, half_life_periods: float,
) -> DecayedSignal:
    """Derive a current signal while retaining all historical evidence verbatim."""

    if not points:
        raise ValueError("at least one evidence signal point is required")
    if list(points) != sorted(points, key=lambda point: point.occurred_at):
        raise ValueError("points must be ordered by occurred_at")
    historical = tuple(float(point.value) for point in points)
    decayed = apply_exponential_decay(historical, half_life_periods=half_life_periods)
    evidence = tuple(sorted({event_id for point in points for event_id in point.evidence_event_ids}, key=str))
    return DecayedSignal(
        historical_values=historical,
        decayed_values=decayed,
        historical_peak=max(historical),
        current_signal=decayed[-1],
        decay_rate=log(2) / half_life_periods,
        evidence_event_ids=evidence,
    )


def _candidate(
    points: Sequence[EvidenceSignalPoint], indices: Sequence[int], *, kind: EpisodeKind,
    subject_id: str, history_type: HistoryType, detector_id: str, detector_version: str,
) -> EpisodeCandidate:
    selected = [points[index] for index in indices]
    evidence = tuple(sorted({item for point in selected for item in point.evidence_event_ids}, key=str))
    start_at, end_at = selected[0].occurred_at, selected[-1].occurred_at
    material = "|".join([kind.value, subject_id, start_at.isoformat(), end_at.isoformat(),
                         *(str(value) for value in evidence)])
    return EpisodeCandidate(
        episode_id=uuid5(EPISODE_NAMESPACE, material), episode_kind=kind, subject_id=subject_id,
        history_type=history_type, start_at=start_at, end_at=end_at, evidence_event_ids=evidence,
        detector_id=detector_id, detector_version=detector_version, machine_label=None,
    )


def detect_project_episode_candidates(
    points: Sequence[EvidenceSignalPoint], *, subject_id: str, lookback: int = 7,
    z_threshold: float = 3.5, minimum_history: int = 3, minimum_absolute_increase: float = 0.0,
    max_gap_periods: int = 0, minimum_evidence_events: int = 2,
    history_type: HistoryType = HistoryType.PERSONAL_BEHAVIOURAL,
    detector_id: str = "episodes.project.median-mad", detector_version: str = "1.0.0",
) -> tuple[EpisodeCandidate, ...]:
    """Group statistically detected burst periods into project candidates."""

    if max_gap_periods < 0 or minimum_evidence_events < 1:
        raise ValueError("max_gap_periods must be non-negative and minimum_evidence_events positive")
    baseline = rolling_robust_baseline(points, lookback=lookback, z_threshold=z_threshold,
                                       minimum_history=minimum_history,
                                       minimum_absolute_increase=minimum_absolute_increase)
    burst_indices = [index for index, item in enumerate(baseline) if item.is_burst]
    if not burst_indices:
        return ()
    groups: list[list[int]] = [[burst_indices[0]]]
    for index in burst_indices[1:]:
        if index - groups[-1][-1] <= max_gap_periods + 1:
            groups[-1].append(index)
        else:
            groups.append([index])
    candidates = tuple(_candidate(points, group, kind=EpisodeKind.PROJECT, subject_id=subject_id,
                                  history_type=history_type, detector_id=detector_id,
                                  detector_version=detector_version) for group in groups)
    return tuple(candidate for candidate in candidates
                 if len(candidate.evidence_event_ids) >= minimum_evidence_events)


def detect_topic_cluster_episode_candidates(
    points: Sequence[EvidenceSignalPoint], *, subject_id: str, minimum_topics: int = 2,
    value_threshold: float = 1.0, history_type: HistoryType = HistoryType.PERSONAL_BEHAVIOURAL,
    detector_id: str = "episodes.topic-cluster.threshold", detector_version: str = "1.0.0",
) -> tuple[EpisodeCandidate, ...]:
    """Group contiguous periods where multiple evidence-linked topics co-occur."""

    if minimum_topics < 2:
        raise ValueError("minimum_topics must be at least two")
    active = [index for index, point in enumerate(points)
              if point.value >= value_threshold and len(set(point.topic_ids)) >= minimum_topics]
    if not active:
        return ()
    groups: list[list[int]] = [[active[0]]]
    for index in active[1:]:
        if index == groups[-1][-1] + 1:
            groups[-1].append(index)
        else:
            groups.append([index])
    return tuple(_candidate(points, group, kind=EpisodeKind.TOPIC_CLUSTER, subject_id=subject_id,
                            history_type=history_type, detector_id=detector_id,
                            detector_version=detector_version) for group in groups)
