"""Canonical persistence/materialisation sink for already-grounded ActivityEvents."""
from __future__ import annotations

from typing import Iterable
from uuid import UUID

from db.postgres import PostgresClient

from .events import catalogue_observations, catalogue_partition, write_activity_events
from .materialization import OperationalTemporalMaterializer
from .models import ActivityEvent
from .storage import StorageRoots


async def persist_grounded_events(
    postgres: PostgresClient, roots: StorageRoots, events: Iterable[ActivityEvent], *,
    analysis_run_id: UUID, partition_key: str,
) -> int:
    """Write the Task 3 event lake, observation catalogue and derived materialisation."""

    values = tuple(events)
    if not values:
        return 0
    written = write_activity_events(
        roots.event_lake, values, analysis_run_id=analysis_run_id,
        partition_key=partition_key,
    )
    signatures = {event.event_id: event.record_signature for event in written.events}
    pool = await postgres._get_pool()
    async with pool.acquire() as connection, connection.transaction():
        await catalogue_partition(
            connection, written.event_partition, partition_key=f"events/{partition_key}",
        )
        await catalogue_partition(
            connection, written.observation_partition, partition_key=f"observations/{partition_key}",
        )
        await catalogue_observations(connection, written.observations, signatures)
        await OperationalTemporalMaterializer(connection).materialize(
            analysis_run_id=analysis_run_id,
            partition_file_hash=written.event_partition.file_hash,
            events=written.events,
            artifact_paths={event.artifact_id: partition_key for event in written.events},
        )
    return len(written.events)
