"""Grounded interaction-state metrics from source-explicit directions only."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from datetime import datetime
import hashlib
import json
import math
import re
from statistics import median, pstdev
from typing import Any
from uuid import UUID

from ingestion.models import ActivityEvent
from temporal.models import InteractionState


_INBOUND = "RECEIVED_FROM"
_OUTBOUND = "SENT_TO"
_DIRECTION_KEYS = {_INBOUND, _OUTBOUND}


def _normalise_key(value: Any) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(value).strip())
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_").upper()


def _normalise_target(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip().casefold()
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("counterpart values must be finite")
        return value
    if isinstance(value, UUID):
        return {"uuid": str(value)}
    if isinstance(value, datetime):
        return {"datetime": value.isoformat()}
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, Mapping):
        return {
            str(key).strip().casefold(): _normalise_target(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalise_target(item) for item in value]
    if isinstance(value, (set, frozenset)):
        encoded = {
            json.dumps(_normalise_target(item), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for item in value
        }
        return {"unordered": sorted(encoded)}
    raise ValueError(f"unsupported counterpart value type: {type(value).__name__}")


def _canonical_target(value: Any) -> str:
    return json.dumps(
        _normalise_target(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )


def counterpart_hash(value: Any) -> str:
    """Hash a canonical counterpart value so state output does not expose it."""

    return hashlib.sha256(_canonical_target(value).encode("utf-8")).hexdigest()


def _explicit_interactions(event: ActivityEvent) -> tuple[tuple[str, str], ...]:
    observations: set[tuple[str, str]] = set()
    for key, value in event.relationships.items():
        direct = _normalise_key(key)
        if direct in _DIRECTION_KEYS and value not in (None, "", [], {}):
            observations.add((direct, counterpart_hash(value)))
        if not isinstance(value, Mapping):
            continue
        declared = value.get("action", value.get("relationship_action"))
        direction = _normalise_key(declared) if declared is not None else ""
        if direction not in _DIRECTION_KEYS:
            continue
        target = next(
            (value[name] for name in ("target", "party", "object", "identifier", "value") if name in value),
            None,
        )
        if target not in (None, "", [], {}):
            observations.add((direction, counterpart_hash(target)))
    return tuple(sorted(observations))


def _deduplicate(events: Iterable[ActivityEvent]) -> tuple[ActivityEvent, ...]:
    by_id: dict[object, ActivityEvent] = {}
    for event in events:
        previous = by_id.get(event.event_id)
        if previous is not None and previous != event:
            raise ValueError(f"conflicting duplicate event_id: {event.event_id}")
        by_id[event.event_id] = event
    return tuple(by_id[key] for key in sorted(by_id, key=str))


def _response_interval(observations: list[tuple[ActivityEvent, str]]) -> float | None:
    timed = sorted(
        ((event.occurred_at, direction, str(event.event_id)) for event, direction in observations if event.occurred_at),
        key=lambda item: (item[0], item[2]),
    )
    pending_inbound: datetime | None = None
    intervals: list[float] = []
    for occurred_at, direction, _ in timed:
        if direction == _INBOUND:
            pending_inbound = occurred_at
        elif pending_inbound is not None:
            seconds = (occurred_at - pending_inbound).total_seconds()
            if seconds >= 0:
                intervals.append(seconds)
            pending_inbound = None
    return float(median(intervals)) if intervals else None


def _burstiness(observations: list[tuple[ActivityEvent, str]]) -> float | None:
    timestamps = sorted({event.occurred_at for event, _ in observations if event.occurred_at})
    if len(timestamps) < 3:
        return None
    intervals = [(right - left).total_seconds() for left, right in zip(timestamps, timestamps[1:])]
    mean = sum(intervals) / len(intervals)
    deviation = pstdev(intervals)
    denominator = deviation + mean
    return None if denominator == 0 else (deviation - mean) / denominator


def _validate_timestamp_awareness(observations: list[tuple[ActivityEvent, str]]) -> None:
    awareness = {
        event.occurred_at.tzinfo is not None
        for event, _ in observations
        if event.occurred_at is not None
    }
    if len(awareness) > 1:
        raise ValueError("interaction timestamps must use compatible timezone awareness")


def build_interaction_states(events: Iterable[ActivityEvent]) -> tuple[InteractionState, ...]:
    """Aggregate only explicit inbound/outbound observations per subject/counterpart."""

    grouped: dict[tuple[str, str], list[tuple[ActivityEvent, str]]] = defaultdict(list)
    for event in _deduplicate(events):
        for direction, target_hash in _explicit_interactions(event):
            grouped[(event.subject_id, target_hash)].append((event, direction))

    states: list[InteractionState] = []
    for (subject_id, target_hash), observations in sorted(grouped.items()):
        _validate_timestamp_awareness(observations)
        inbound = sum(direction == _INBOUND for _, direction in observations)
        outbound = sum(direction == _OUTBOUND for _, direction in observations)
        maximum = max(inbound, outbound)
        reciprocity = None if maximum == 0 else min(inbound, outbound) / maximum
        dated = {event.occurred_at.date() for event, _ in observations if event.occurred_at}
        services = {event.service.strip().casefold() for event, _ in observations if event.service and event.service.strip()}
        states.append(InteractionState(
            subject_id=subject_id,
            counterpart_hash=target_hash,
            inbound=inbound,
            outbound=outbound,
            reciprocity_ratio=reciprocity,
            response_interval_seconds=_response_interval(observations),
            active_days=len(dated),
            service_count=len(services),
            burstiness=_burstiness(observations),
            evidence_event_ids=tuple(sorted({event.event_id for event, _ in observations}, key=str)),
        ))
    return tuple(states)
