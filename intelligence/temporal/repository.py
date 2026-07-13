"""Append-only PostgreSQL catalogue for Task 3 temporal histories."""
from __future__ import annotations

from datetime import datetime
import json
from typing import Iterable
from uuid import UUID

from ingestion.models import HistoryType, TemporalAggregate, TemporalState


def _decode_state(row) -> TemporalState:
    values = dict(row)
    for field in ("dimensions", "evidence_event_ids"):
        if isinstance(values.get(field), str):
            values[field] = json.loads(values[field])
    return TemporalState.model_validate(values)


class TemporalStateRepository:
    def __init__(self, connection) -> None:
        self.connection = connection

    async def append_state(self, analysis_run_id: UUID, state: TemporalState) -> UUID:
        return await self.connection.fetchval(
            """INSERT INTO temporal_states
            (analysis_run_id,subject_id,history_type,state_type,state_key,occurred_at,
             valid_from,valid_to,controller_observed_from,controller_observed_to,
             exported_at,ingested_at,system_asserted_at,superseded_at,dimensions,
             evidence_event_ids,detector_id,detector_version)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15::jsonb,$16::jsonb,$17,$18)
            RETURNING id""",
            analysis_run_id, state.subject_id, state.history_type.value,
            state.state_type, state.state_key, state.occurred_at,
            state.valid_from, state.valid_to, state.controller_observed_from,
            state.controller_observed_to, state.exported_at, state.ingested_at,
            state.system_asserted_at, state.superseded_at,
            json.dumps(state.dimensions, sort_keys=True),
            json.dumps([str(value) for value in state.evidence_event_ids]),
            state.detector_id, state.detector_version,
        )

    async def supersede(self, previous_id: UUID, analysis_run_id: UUID, replacement: TemporalState) -> UUID:
        async with self.connection.transaction():
            result = await self.connection.execute(
                "UPDATE temporal_states SET superseded_at=$2 WHERE id=$1 AND superseded_at IS NULL",
                previous_id, replacement.system_asserted_at,
            )
            if result != "UPDATE 1":
                raise ValueError("temporal state is missing or already superseded")
            return await self.append_state(analysis_run_id, replacement)

    async def as_of(
        self, subject_id: str, *, valid_as_of: datetime, system_as_of: datetime,
        history_type: HistoryType | None = None,
    ) -> tuple[TemporalState, ...]:
        rows = await self.connection.fetch(
            """SELECT subject_id,history_type,state_type,state_key,occurred_at,valid_from,valid_to,
            controller_observed_from,controller_observed_to,exported_at,ingested_at,
            system_asserted_at,superseded_at,dimensions,evidence_event_ids,detector_id,detector_version
            FROM temporal_states_as_of($1,$2,$3,$4)""",
            subject_id, valid_as_of, system_as_of,
            history_type.value if history_type else None,
        )
        return tuple(_decode_state(row) for row in rows)

    async def current(self, subject_id: str, *, history_type: HistoryType | None = None) -> tuple[TemporalState, ...]:
        rows = await self.connection.fetch(
            """SELECT subject_id,history_type,state_type,state_key,occurred_at,valid_from,valid_to,
            controller_observed_from,controller_observed_to,exported_at,ingested_at,
            system_asserted_at,superseded_at,dimensions,evidence_event_ids,detector_id,detector_version
            FROM current_temporal_states WHERE subject_id=$1 AND ($2::text IS NULL OR history_type=$2)
            ORDER BY history_type,state_type,state_key,system_asserted_at""",
            subject_id, history_type.value if history_type else None,
        )
        return tuple(_decode_state(row) for row in rows)

    async def append_aggregate(self, analysis_run_id: UUID, aggregate: TemporalAggregate) -> UUID:
        return await self.connection.fetchval(
            """INSERT INTO temporal_aggregates
            (analysis_run_id,subject_id,history_type,aggregate_type,aggregate_key,window_start,window_end,
             values,source_event_count,detector_id,detector_version)
            VALUES($1,$2,$3,$4,$5,$6,$7,$8::jsonb,$9,$10,$11) RETURNING id""",
            analysis_run_id, aggregate.subject_id, aggregate.history_type.value,
            aggregate.aggregate_type, aggregate.aggregate_key,
            aggregate.window_start, aggregate.window_end,
            json.dumps(aggregate.values, sort_keys=True), aggregate.source_event_count,
            aggregate.detector_id, aggregate.detector_version,
        )
