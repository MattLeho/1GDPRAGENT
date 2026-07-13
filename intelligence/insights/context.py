"""Deterministic, evidence-constrained contextual correlation candidates."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Iterable, Sequence
from uuid import UUID, uuid5

from .models import (
    ChangeInsight,
    CorrelationStatus,
    EvidenceKind,
    ExternalContextEvent,
    InsightEvidenceRef,
    TemporalCorrelationCandidate,
)


DETECTOR_ID = "task4.contextual_correlation"
DETECTOR_VERSION = "1.0.0"
_NAMESPACE = UUID("9f4be13b-4f2d-4a93-b5b7-bcfde4a23ef2")
_TOKEN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True, slots=True)
class ExposureObservation:
    """Local evidence that the user encountered or discussed event-related material."""

    evidence: InsightEvidenceRef
    occurred_at: datetime
    topics: tuple[str, ...] = ()
    text: str = ""
    relevance: float = 1.0
    direct_user_statement: bool = False
    rejected: bool = False

    def __post_init__(self) -> None:
        if not 0 <= self.relevance <= 1:
            raise ValueError("exposure relevance must be between zero and one")


def _tokens(*values: str) -> set[str]:
    return {token for value in values for token in _TOKEN.findall(value.casefold()) if len(token) > 1}


def semantic_relevance(change: ChangeInsight, event: ExternalContextEvent) -> float:
    """Return a transparent token-overlap score; no model or provider is invoked."""

    # The state key describes the changed subject. The detector's change-type
    # label (for example REGIME_SHIFT) is not event semantics.
    change_tokens = _tokens(change.state_key)
    event_tokens = _tokens(event.title, event.event_type, *event.topics)
    if not change_tokens or not event_tokens:
        return 0.0
    overlap = len(change_tokens & event_tokens)
    return min(1.0, overlap / max(1, min(len(change_tokens), len(event_tokens))))


def temporal_proximity(change: ChangeInsight, event: ExternalContextEvent, window: timedelta) -> float:
    if window.total_seconds() <= 0:
        raise ValueError("correlation window must be positive")
    distance = abs((change.detected_at - event.occurred_at).total_seconds())
    return max(0.0, 1.0 - distance / window.total_seconds())


def resolve_exposure_evidence(
    change: ChangeInsight,
    event: ExternalContextEvent,
    observations: Iterable[ExposureObservation],
    *,
    lookback: timedelta = timedelta(days=90),
    minimum_relevance: float = 0.35,
) -> tuple[ExposureObservation, ...]:
    """Resolve related local evidence that precedes the detected change.

    External events are never queried here. The resolver consumes already-local
    observations and cannot turn post-change activity into preceding exposure.
    """

    if lookback.total_seconds() <= 0:
        raise ValueError("exposure lookback must be positive")
    event_tokens = _tokens(event.title, event.event_type, *event.topics)
    lower = change.detected_at - lookback
    resolved: list[ExposureObservation] = []
    for observation in observations:
        if observation.rejected or not lower <= observation.occurred_at <= change.detected_at:
            continue
        observation_tokens = _tokens(observation.text, *observation.topics)
        related = bool(event_tokens & observation_tokens) if event_tokens and observation_tokens else False
        if related and observation.relevance >= minimum_relevance:
            resolved.append(observation)
    return tuple(sorted(resolved, key=lambda item: (item.occurred_at, str(item.evidence.ref_id))))


def correlate_change(
    change: ChangeInsight,
    external_events: Sequence[ExternalContextEvent],
    exposure_observations: Sequence[ExposureObservation] = (),
    confirmation_evidence: Sequence[InsightEvidenceRef] = (),
    *,
    window: timedelta = timedelta(days=45),
    exposure_lookback: timedelta = timedelta(days=90),
    minimum_semantic_relevance: float = 0.25,
    evidence_supported_relevance: float = 0.5,
    behavioural_persistence: float = 0.0,
    competing_explanations_count: int = 0,
    analysis_run_id: UUID | None = None,
) -> tuple[TemporalCorrelationCandidate, ...]:
    """Match bounded external events starting from one detected ``ChangeInsight``.

    Timing alone always remains a coincidence candidate. Local preceding exposure
    can support a possible/evidence-supported relation, but never a causal claim.
    A direct user statement is represented separately as ``user_confirmed``.
    """

    if behavioural_persistence < 0 or competing_explanations_count < 0:
        raise ValueError("persistence and competing explanation counts cannot be negative")
    candidates: list[TemporalCorrelationCandidate] = []
    for event in external_events:
        proximity = temporal_proximity(change, event, window)
        if proximity <= 0:
            continue
        relevance = semantic_relevance(change, event)
        exposures = resolve_exposure_evidence(
            change, event, exposure_observations, lookback=exposure_lookback
        )
        exposure_evidence = tuple(item.evidence for item in exposures)
        confirmations = tuple(item for item in confirmation_evidence if item.role == "user_confirmation")
        relation_evidence = exposure_evidence + confirmations
        direct_statement = any(item.direct_user_statement for item in exposures) or bool(confirmations)
        preceding = bool(exposures)
        if direct_statement:
            status = CorrelationStatus.USER_CONFIRMED
        elif relevance < minimum_semantic_relevance or not exposure_evidence:
            status = CorrelationStatus.COINCIDENCE_CANDIDATE
        elif relevance >= evidence_supported_relevance and behavioural_persistence > 0:
            status = CorrelationStatus.EVIDENCE_SUPPORTED_RELATION
        else:
            status = CorrelationStatus.POSSIBLE_RELATION
        insight_id = uuid5(_NAMESPACE, f"{change.insight_id}:{event.id}:{DETECTOR_VERSION}")
        candidates.append(TemporalCorrelationCandidate(
            insight_id=insight_id,
            detector_id=DETECTOR_ID,
            detector_version=DETECTOR_VERSION,
            analysis_run_id=analysis_run_id or change.analysis_run_id,
            calculated_features={
                "bounded_window_days": window.total_seconds() / 86400,
                "exposure_count": len(exposure_evidence),
                "classification_rule": status.value,
            },
            evidence=change.evidence + relation_evidence + (InsightEvidenceRef(
                kind=EvidenceKind.EXTERNAL_CONTEXT_EVENT,
                ref_id=event.id,
                role="comparison",
                occurred_at=event.occurred_at,
            ),),
            local_change_id=change.insight_id,
            external_event_id=event.id,
            local_change={
                "change_type": change.change_type,
                "state_key": change.state_key,
                "detected_at": change.detected_at,
                "magnitude": change.magnitude,
            },
            external_event={
                "title": event.title,
                "event_type": event.event_type,
                "occurred_at": event.occurred_at,
                "ended_at": event.ended_at,
                "topics": event.topics,
                "jurisdiction": event.jurisdiction,
                "source_uri": event.source_uri,
            },
            temporal_proximity=proximity,
            semantic_relevance=relevance,
            user_exposure_evidence=relation_evidence,
            direct_user_statement=direct_statement,
            preceding_related_activity=preceding,
            behavioural_persistence=behavioural_persistence,
            competing_explanations_count=competing_explanations_count,
            status=status,
            causal_claim=False,
        ))
    return tuple(sorted(candidates, key=lambda item: (-item.temporal_proximity, str(item.external_event_id))))
