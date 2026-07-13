"""Pure bitemporal views and export-snapshot comparisons.

The functions in this module never update the supplied source records.  A
``TemporalView`` is an explicitly derived projection over two independent
questions: when a state was valid and when the system knew about it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Literal
from uuid import UUID

from pydantic import Field, model_validator

from ingestion.models import FrozenModel, HistoryType, TemporalState
from temporal.models import DeltaStatus, DriftType, SnapshotDelta


class TemporalView(FrozenModel):
    mode: Literal["NOW", "AS_OF"]
    valid_at: datetime
    known_at: datetime
    states: tuple[TemporalState, ...]
    derived: bool = True


def _at_or_before(value: datetime | None, boundary: datetime) -> bool:
    return value is None or value <= boundary


def _after(value: datetime | None, boundary: datetime) -> bool:
    return value is None or value > boundary


def _known_at(state: TemporalState, known_at: datetime) -> bool:
    # Export time describes the controller's snapshot, not system discovery.
    # Ingestion/assertion time determines what the system could have known.
    if not _at_or_before(state.ingested_at, known_at):
        return False
    if not _at_or_before(state.system_asserted_at, known_at):
        return False
    return _after(state.superseded_at, known_at)


def _valid_at(state: TemporalState, valid_at: datetime) -> bool:
    if state.history_type is HistoryType.PERSONAL_BEHAVIOURAL:
        start = state.valid_from or state.occurred_at
        return _at_or_before(start, valid_at) and _after(state.valid_to, valid_at)
    if state.history_type is HistoryType.CONTROLLER_PROFILE:
        return _at_or_before(state.controller_observed_from, valid_at) and _after(
            state.controller_observed_to, valid_at
        )
    # System-understanding history is governed by known_at.  Applying a
    # behavioural/controller validity axis here would collapse the histories.
    return True


def _recency_key(state: TemporalState) -> tuple[datetime, datetime, str]:
    earliest = datetime.min.replace(tzinfo=timezone.utc)

    def aware_or_min(value: datetime | None) -> datetime:
        if value is None:
            return earliest
        if value.tzinfo is None:
            # Naive timestamps may be valid source evidence.  Keep their wall
            # time deterministic instead of inventing a source timezone.
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if state.history_type is HistoryType.PERSONAL_BEHAVIOURAL:
        effective = state.valid_from or state.occurred_at
    elif state.history_type is HistoryType.CONTROLLER_PROFILE:
        effective = state.controller_observed_from
    else:
        effective = state.system_asserted_at
    discovery = state.system_asserted_at or state.ingested_at
    stable_value = repr(sorted(state.dimensions.items()))
    return aware_or_min(effective), aware_or_min(discovery), stable_value


def query_temporal_view(
    states: Iterable[TemporalState],
    *,
    valid_at: datetime,
    known_at: datetime,
    mode: Literal["NOW", "AS_OF"] = "AS_OF",
) -> TemporalView:
    """Return the latest visible version of each history/entity key.

    ``valid_at`` answers *when the represented state held* while ``known_at``
    answers *what the system had discovered by then*.  Keeping both parameters
    explicit is what permits late imports of older activity to be represented
    without pretending the activity itself is new.
    """

    selected: dict[tuple[str, HistoryType, str, str], TemporalState] = {}
    for state in states:
        if not _known_at(state, known_at) or not _valid_at(state, valid_at):
            continue
        key = (state.subject_id, state.history_type, state.state_type, state.state_key)
        current = selected.get(key)
        if current is None or _recency_key(state) > _recency_key(current):
            selected[key] = state

    visible = tuple(
        sorted(
            selected.values(),
            key=lambda value: (
                value.subject_id,
                value.history_type.value,
                value.state_type,
                value.state_key,
                value.system_asserted_at,
            ),
        )
    )
    return TemporalView(
        mode=mode,
        valid_at=valid_at,
        known_at=known_at,
        states=visible,
    )


def current_temporal_view(
    states: Iterable[TemporalState], *, now: datetime | None = None
) -> TemporalView:
    boundary = now or datetime.now(timezone.utc)
    return query_temporal_view(
        states, valid_at=boundary, known_at=boundary, mode="NOW"
    )


def as_of_temporal_view(
    states: Iterable[TemporalState], *, as_of: datetime
) -> TemporalView:
    return query_temporal_view(
        states, valid_at=as_of, known_at=as_of, mode="AS_OF"
    )


class SnapshotEntityLevel(str, Enum):
    ASSERTION = "assertion"
    SCHEMA = "schema"
    EVENT_OBSERVATION = "event_observation"


class SnapshotEntity(FrozenModel):
    """A logical export member prepared for deterministic comparison."""

    level: SnapshotEntityLevel
    entity_key: str = Field(min_length=1)
    value: Any
    drift_type: DriftType


class ExportDeltaReport(FrozenModel):
    before_snapshot_id: UUID
    after_snapshot_id: UUID
    deltas: tuple[SnapshotDelta, ...]

    @model_validator(mode="after")
    def snapshot_order(self):
        if self.before_snapshot_id == self.after_snapshot_id:
            raise ValueError("export delta requires two distinct snapshots")
        return self

    @property
    def personal_drift(self) -> tuple[SnapshotDelta, ...]:
        return tuple(d for d in self.deltas if d.drift_type is DriftType.PERSONAL)

    @property
    def controller_drift(self) -> tuple[SnapshotDelta, ...]:
        return tuple(d for d in self.deltas if d.drift_type is DriftType.CONTROLLER)

    @property
    def understanding_drift(self) -> tuple[SnapshotDelta, ...]:
        return tuple(d for d in self.deltas if d.drift_type is DriftType.UNDERSTANDING)


_INTERPRETATIONS: dict[DeltaStatus, str] = {
    DeltaStatus.NEW: (
        "newly observed by this system in the later export; controller collection time is not established"
    ),
    DeltaStatus.REMOVED_FROM_EXPORT: (
        "not observed in the later export; controller deletion is not established"
    ),
    DeltaStatus.UNCHANGED: "observed with the same value in both compared exports",
    DeltaStatus.MODIFIED: (
        "observed with different exported values; controller change time is not established"
    ),
}


def _index_entities(
    entities: Iterable[SnapshotEntity], *, side: str
) -> dict[tuple[SnapshotEntityLevel, str], SnapshotEntity]:
    indexed: dict[tuple[SnapshotEntityLevel, str], SnapshotEntity] = {}
    for entity in entities:
        key = (entity.level, entity.entity_key)
        if key in indexed:
            raise ValueError(
                f"duplicate {side} snapshot entity key: {entity.level.value}/{entity.entity_key}"
            )
        indexed[key] = entity
    return indexed


def compare_export_snapshots(
    *,
    before_snapshot_id: UUID,
    after_snapshot_id: UUID,
    before: Iterable[SnapshotEntity],
    after: Iterable[SnapshotEntity],
) -> ExportDeltaReport:
    """Compare assertion, schema and event-observation logical members.

    Drift classification is explicit input, never inferred from presence in an
    export.  In particular, ``NEW`` means newly observed by this system and is
    deliberately not a claim about when a controller collected the data.
    """

    if before_snapshot_id == after_snapshot_id:
        raise ValueError("export delta requires two distinct snapshots")
    old = _index_entities(before, side="before")
    new = _index_entities(after, side="after")
    deltas: list[SnapshotDelta] = []
    for key in sorted(set(old) | set(new), key=lambda item: (item[0].value, item[1])):
        old_item = old.get(key)
        new_item = new.get(key)
        if old_item is None:
            status = DeltaStatus.NEW
            drift_type = new_item.drift_type  # type: ignore[union-attr]
        elif new_item is None:
            status = DeltaStatus.REMOVED_FROM_EXPORT
            drift_type = old_item.drift_type
        else:
            if old_item.drift_type is not new_item.drift_type:
                raise ValueError(
                    f"drift type changed for {key[0].value}/{key[1]}; use a stable logical key or classify the understanding change separately"
                )
            drift_type = new_item.drift_type
            status = (
                DeltaStatus.UNCHANGED
                if old_item.value == new_item.value
                else DeltaStatus.MODIFIED
            )
        deltas.append(
            SnapshotDelta(
                entity_type=key[0].value,
                entity_key=key[1],
                before_snapshot_id=before_snapshot_id,
                after_snapshot_id=after_snapshot_id,
                status=status,
                drift_type=drift_type,
                before_value=None if old_item is None else old_item.value,
                after_value=None if new_item is None else new_item.value,
                interpretation=_INTERPRETATIONS[status],
            )
        )
    return ExportDeltaReport(
        before_snapshot_id=before_snapshot_id,
        after_snapshot_id=after_snapshot_id,
        deltas=tuple(deltas),
    )
