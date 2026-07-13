from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import asyncpg
import pytest

from ingestion.models import HistoryType, TemporalState
from temporal.repository import TemporalStateRepository
from test_task1_database_integration import migrated_database


def _at(year, month, day):
    return datetime(year, month, day, tzinfo=timezone.utc)


def _state(history_type, *, asserted, value, controller_from=None, exported=None):
    return TemporalState(
        subject_id="subject-1", history_type=history_type,
        state_type="fixture", state_key=history_type.value,
        valid_from=_at(2024, 1, 1), controller_observed_from=controller_from,
        exported_at=exported, ingested_at=asserted,
        system_asserted_at=asserted, dimensions={"value": value},
        evidence_event_ids=(uuid4(),), detector_id="fixture.temporal",
        detector_version="1",
    )


@pytest.mark.asyncio
async def test_three_histories_and_bitemporal_as_of_remain_distinct(migrated_database):
    url, request_id, _file_id = migrated_database
    connection = await asyncpg.connect(url)
    try:
        run_id = await connection.fetchval(
            "INSERT INTO analysis_runs(run_type,request_id,status,pipeline_version) VALUES('task3-temporal',$1,'running','task3-v1') RETURNING id",
            request_id,
        )
        repository = TemporalStateRepository(connection)
        personal = _state(HistoryType.PERSONAL_BEHAVIOURAL, asserted=_at(2024, 2, 1), value=1.0)
        controller = _state(
            HistoryType.CONTROLLER_PROFILE, asserted=_at(2024, 2, 2), value=2.0,
            controller_from=_at(2024, 1, 15), exported=_at(2024, 1, 31),
        )
        understanding = _state(HistoryType.SYSTEM_UNDERSTANDING, asserted=_at(2024, 3, 1), value=3.0)
        personal_id = await repository.append_state(run_id, personal)
        await repository.append_state(run_id, controller)
        await repository.append_state(run_id, understanding)

        early = await repository.as_of(
            "subject-1", valid_as_of=_at(2024, 4, 1), system_as_of=_at(2024, 2, 15),
        )
        assert {state.history_type for state in early} == {
            HistoryType.PERSONAL_BEHAVIOURAL, HistoryType.CONTROLLER_PROFILE,
        }
        later = await repository.as_of(
            "subject-1", valid_as_of=_at(2024, 4, 1), system_as_of=_at(2024, 4, 1),
        )
        assert {state.history_type for state in later} == set(HistoryType)
        assert controller.controller_observed_from != controller.system_asserted_at
        assert controller.exported_at != controller.ingested_at

        replacement = _state(
            HistoryType.PERSONAL_BEHAVIOURAL, asserted=_at(2024, 5, 1), value=9.0,
        )
        replacement_id = await repository.supersede(personal_id, run_id, replacement)
        before_revision = await repository.as_of(
            "subject-1", valid_as_of=_at(2024, 4, 1), system_as_of=_at(2024, 4, 15),
            history_type=HistoryType.PERSONAL_BEHAVIOURAL,
        )
        after_revision = await repository.as_of(
            "subject-1", valid_as_of=_at(2024, 4, 1), system_as_of=_at(2024, 6, 1),
            history_type=HistoryType.PERSONAL_BEHAVIOURAL,
        )
        assert before_revision[0].dimensions["value"] == 1.0
        assert after_revision[0].dimensions["value"] == 9.0
        assert replacement_id != personal_id
        current = await repository.current("subject-1")
        assert len(current) == 3
        assert next(state for state in current if state.history_type is HistoryType.PERSONAL_BEHAVIOURAL).dimensions["value"] == 9.0
        with pytest.raises(asyncpg.PostgresError, match="append-only"):
            await connection.execute("UPDATE temporal_states SET dimensions='{\"value\":99}' WHERE id=$1", replacement_id)
    finally:
        await connection.close()
