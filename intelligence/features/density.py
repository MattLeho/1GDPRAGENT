"""Deterministic ActivityEvent density and cross-domain co-occurrence.

The functions return aggregate FeatureCandidates only.  Identifier values are
represented by stable hashes, data classes must be explicit inputs, and this
module has no graph write path.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from statistics import fmean, pstdev
from typing import Any, Iterable, Mapping, Sequence
from uuid import UUID

from ingestion.models import (
    ActivityEvent,
    FeatureCandidate,
    FeatureCandidateStatus,
    PrivacyDataClass,
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str, allow_nan=False)


def _uuid(value: Any, *, field: str) -> UUID | None:
    if value in (None, ""):
        return None
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a UUID") from exc


def _datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _mapping(value: Any) -> Mapping[str, Any]:
    if value in (None, ""):
        return {}
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        if isinstance(parsed, Mapping):
            return parsed
    raise ValueError("expected an object mapping")


def _classes(value: Any) -> tuple[str, ...]:
    if value in (None, ""):
        return ()
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            decoded = value
        value = decoded
    values = value if isinstance(value, (list, tuple, set, frozenset)) else (value,)
    result: set[str] = set()
    allowed = {item.value for item in PrivacyDataClass}
    for item in values:
        normalised = str(item).strip().upper()
        if normalised not in allowed:
            raise ValueError(f"unsupported explicit data class: {item!r}")
        result.add(normalised)
    return tuple(sorted(result))


@dataclass(frozen=True, slots=True)
class _EventView:
    event_id: UUID | None
    artifact_id: UUID | None
    subject_id: str
    event_type: str
    data_domain: str
    occurred_at: datetime | None
    object_id: Any
    object_value: Any
    identifiers: Mapping[str, Any]
    data_classes: tuple[str, ...]


def _view(
    event: ActivityEvent | Mapping[str, Any],
    explicit_classes: Mapping[UUID | str, Iterable[str]] | None,
) -> _EventView:
    if isinstance(event, ActivityEvent):
        event_id, artifact_id = event.event_id, event.artifact_id
        supplied = () if explicit_classes is None else explicit_classes.get(event_id, explicit_classes.get(str(event_id), ()))
        return _EventView(
            event_id=event_id, artifact_id=artifact_id, subject_id=event.subject_id,
            event_type=event.event_type, data_domain=event.data_domain,
            occurred_at=event.occurred_at, object_id=event.object_id,
            object_value=event.object_value, identifiers=event.identifiers,
            data_classes=_classes(tuple(supplied)),
        )
    event_id = _uuid(event.get("event_id"), field="event_id")
    artifact_id = _uuid(event.get("artifact_id"), field="artifact_id")
    if event_id is None and artifact_id is None:
        raise ValueError("partition rows require event_id or artifact_id grounding")
    supplied = event.get("data_classes", event.get("data_class"))
    if explicit_classes is not None and event_id is not None:
        supplied = explicit_classes.get(event_id, explicit_classes.get(str(event_id), supplied))
    return _EventView(
        event_id=event_id, artifact_id=artifact_id,
        subject_id=str(event.get("subject_id") or "unknown"),
        event_type=str(event.get("event_type") or "UNKNOWN"),
        data_domain=str(event.get("data_domain") or "UNKNOWN"),
        occurred_at=_datetime(event.get("occurred_at")),
        object_id=event.get("object_id"), object_value=event.get("object_value"),
        identifiers=_mapping(event.get("identifiers")), data_classes=_classes(supplied),
    )


def _sources(rows: Sequence[_EventView]) -> tuple[tuple[UUID, ...], tuple[UUID, ...]]:
    return (
        tuple(sorted({row.event_id for row in rows if row.event_id is not None}, key=str)),
        tuple(sorted({row.artifact_id for row in rows if row.artifact_id is not None}, key=str)),
    )


def _deduplicate(rows: Sequence[_EventView]) -> tuple[_EventView, ...]:
    """Collapse repeated logical rows while rejecting conflicting event IDs."""
    by_event: dict[UUID, _EventView] = {}
    unkeyed: list[_EventView] = []
    for row in rows:
        if row.event_id is None:
            unkeyed.append(row)
            continue
        previous = by_event.get(row.event_id)
        if previous is not None and previous != row:
            raise ValueError(f"conflicting rows for event_id {row.event_id}")
        by_event[row.event_id] = row
    return tuple(sorted(by_event.values(), key=lambda item: str(item.event_id))) + tuple(unkeyed)


def _burstiness(times: Sequence[datetime]) -> float | None:
    gaps = [(right - left).total_seconds() for left, right in zip(times, times[1:])]
    if len(gaps) < 2:
        return None
    mean, deviation = fmean(gaps), pstdev(gaps)
    denominator = deviation + mean
    return 0.0 if denominator == 0 else (deviation - mean) / denominator


def _periodicity(times: Sequence[datetime]) -> dict[str, float | int | None]:
    gaps = [(right - left).total_seconds() for left, right in zip(times, times[1:])]
    if len(gaps) < 2:
        return {"dominant_interval_seconds": None, "periodicity_score": None}
    rounded = [int(round(gap)) for gap in gaps]
    frequencies = Counter(rounded)
    dominant, count = sorted(frequencies.items(), key=lambda item: (-item[1], item[0]))[0]
    mean = fmean(gaps)
    variation = 0.0 if mean == 0 else pstdev(gaps) / mean
    return {
        "dominant_interval_seconds": dominant,
        "periodicity_score": 1.0 / (1.0 + variation),
        "dominant_interval_support": count / len(gaps),
    }


def _object_key(row: _EventView) -> str | None:
    value = row.object_id if row.object_id not in (None, "") else row.object_value
    if value in (None, "", {}, []):
        return None
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _density_candidates(rows: Sequence[_EventView], detector_id: str, detector_version: str) -> list[FeatureCandidate]:
    grouped: dict[tuple[str, str], list[_EventView]] = defaultdict(list)
    for row in rows:
        grouped[(row.subject_id, row.event_type)].append(row)
    results: list[FeatureCandidate] = []
    for (subject_id, event_type), members in sorted(grouped.items()):
        timed = sorted((row.occurred_at for row in members if row.occurred_at is not None))
        by_day = Counter(value.date().isoformat() for value in timed)
        by_hour = Counter(value.strftime("%Y-%m-%dT%H:00:00Z") for value in timed)
        hour_of_day = Counter(f"{value.hour:02d}" for value in timed)
        event_ids, artifact_ids = _sources(members)
        values: dict[str, Any] = {
            "subject_id": subject_id,
            "event_type": event_type,
            "event_count": len(members),
            "events_by_day": dict(sorted(by_day.items())),
            "events_by_hour": dict(sorted(by_hour.items())),
            "hour_of_day_distribution": dict(sorted(hour_of_day.items())),
            "unique_object_count": len({value for row in members if (value := _object_key(row)) is not None}),
            "burstiness": _burstiness(timed),
            **_periodicity(timed),
            "first_seen": timed[0].isoformat() if timed else None,
            "last_seen": timed[-1].isoformat() if timed else None,
            "timestamped_event_count": len(timed),
        }
        results.append(FeatureCandidate(
            feature_type="activity.density",
            detector_id=detector_id,
            detector_version=detector_version,
            source_event_ids=event_ids,
            source_artifact_ids=artifact_ids,
            calculated_values=values,
            confidence=1.0,
            rule_result=True,
            candidate_status=FeatureCandidateStatus.DETERMINISTIC,
        ))
    return results


def _cooccurrence_candidates(rows: Sequence[_EventView], detector_id: str, detector_version: str) -> list[FeatureCandidate]:
    identifiers: dict[tuple[str, str], list[_EventView]] = defaultdict(list)
    data_classes: dict[str, list[_EventView]] = defaultdict(list)
    for row in rows:
        for identifier_type, value in sorted(row.identifiers.items()):
            values = value if isinstance(value, (list, tuple, set, frozenset)) else (value,)
            unique_values = {_canonical(item): item for item in values if item not in (None, "")}
            for canonical_value in sorted(unique_values):
                item = unique_values[canonical_value]
                if item in (None, ""):
                    continue
                token_hash = hashlib.sha256(_canonical(item).encode()).hexdigest()
                identifiers[(str(identifier_type), token_hash)].append(row)
        for data_class in row.data_classes:
            data_classes[data_class].append(row)

    results: list[FeatureCandidate] = []
    for (identifier_type, token_hash), members in sorted(identifiers.items()):
        domains = sorted({row.data_domain for row in members})
        if len(domains) < 2:
            continue
        event_ids, artifact_ids = _sources(members)
        results.append(FeatureCandidate(
            feature_type="identifier.cross_domain_cooccurrence",
            detector_id=detector_id, detector_version=detector_version,
            source_event_ids=event_ids, source_artifact_ids=artifact_ids,
            calculated_values={
                "identifier_type": identifier_type,
                "token_hash": token_hash,
                "domains": domains,
                "domain_count": len(domains),
                "event_count": len(members),
            },
            confidence=1.0, rule_result=True,
            candidate_status=FeatureCandidateStatus.DETERMINISTIC,
        ))
    for data_class, members in sorted(data_classes.items()):
        domains = sorted({row.data_domain for row in members})
        if len(domains) < 2:
            continue
        event_ids, artifact_ids = _sources(members)
        results.append(FeatureCandidate(
            feature_type="data_class.cross_domain_cooccurrence",
            detector_id=detector_id, detector_version=detector_version,
            source_event_ids=event_ids, source_artifact_ids=artifact_ids,
            calculated_values={
                "data_class": data_class,
                "domains": domains,
                "domain_count": len(domains),
                "event_count": len(members),
            },
            confidence=1.0, rule_result=True,
            candidate_status=FeatureCandidateStatus.DETERMINISTIC,
        ))
    return results


def aggregate_density_features(
    events_or_rows: Iterable[ActivityEvent | Mapping[str, Any]], *,
    data_classes_by_event: Mapping[UUID | str, Iterable[str]] | None = None,
    detector_id: str = "task3.density_cooccurrence",
    detector_version: str = "1.0.0",
) -> tuple[FeatureCandidate, ...]:
    rows = _deduplicate(tuple(_view(event, data_classes_by_event) for event in events_or_rows))
    if not rows:
        return ()
    candidates = _density_candidates(rows, detector_id, detector_version)
    candidates.extend(_cooccurrence_candidates(rows, detector_id, detector_version))
    return tuple(sorted(candidates, key=lambda item: (
        item.feature_type,
        _canonical(item.calculated_values),
        tuple(str(value) for value in item.source_event_ids),
    )))


@dataclass(frozen=True, slots=True)
class DensityCooccurrenceDetector:
    detector_id: str = "task3.density_cooccurrence"
    detector_version: str = "1.0.0"
    data_classes_by_event: Mapping[UUID | str, Iterable[str]] | None = None

    def detect(self, events: tuple[ActivityEvent, ...]) -> Iterable[FeatureCandidate]:
        return aggregate_density_features(
            events,
            data_classes_by_event=self.data_classes_by_event,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
        )
