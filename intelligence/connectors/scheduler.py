"""Recurring connector scheduling and persisted health derivation.

This is an adapter for the existing Celery execution path, not a second task
runner.  PostgreSQL atomically claims due instances before their existing
``intelligence.connectors.sync`` task is enqueued.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol
from uuid import UUID

from db.postgres import PostgresClient, get_postgres_client

from .lifecycle import ConnectorHealth, connector_health
from .models import ConnectorInstance


class EnqueuedTask(Protocol):
    id: str


EnqueueSync = Callable[[dict[str, str]], EnqueuedTask]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("scheduler times must be timezone-aware")
    return value.astimezone(timezone.utc)


def _decoded_error(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def derive_failure_health(
    instance: ConnectorInstance,
    history: Sequence[Mapping[str, object]],
) -> ConnectorHealth:
    """Derive a public health DTO from newest-first persisted sync history."""

    failures = 0
    detail: str | None = None
    for row in history:
        status = str(row.get("status", ""))
        if status in {"pending", "running"}:
            continue
        if status != "failed":
            break
        failures += 1
        if detail is None:
            error = _decoded_error(row.get("error"))
            message = error.get("message")
            error_type = error.get("type")
            if isinstance(message, str) and message.strip():
                detail = message.strip()
            elif isinstance(error_type, str) and error_type.strip():
                detail = error_type.strip()
            else:
                detail = "connector sync failed"
    return connector_health(instance, consecutive_failures=failures, detail=detail)


class ConnectorScheduler:
    """Atomically claim due connector instances and enqueue canonical sync tasks."""

    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()

    async def claim_due(
        self,
        *,
        now: datetime,
        limit: int = 100,
        claim_lease: timedelta = timedelta(minutes=5),
    ) -> list[UUID]:
        if not 1 <= limit <= 1_000:
            raise ValueError("scheduler limit must be between 1 and 1000")
        if claim_lease <= timedelta(0):
            raise ValueError("claim lease must be positive")
        claimed_at = _utc(now)
        lease_until = claimed_at + claim_lease
        rows = await self.postgres.execute(
            """WITH due AS (
                 SELECT ci.id,ci.next_sync_at
                 FROM connector_instances ci
                 WHERE ci.status IN ('connected','degraded')
                   AND ci.next_sync_at IS NOT NULL AND ci.next_sync_at <= $1
                   AND NOT EXISTS (
                     SELECT 1 FROM connector_sync_runs csr
                     WHERE csr.connector_instance_id=ci.id
                       AND csr.status IN ('pending','running')
                   )
                 ORDER BY ci.next_sync_at,ci.id
                 FOR UPDATE OF ci SKIP LOCKED
                 LIMIT $2
               ), claimed AS (
                 UPDATE connector_instances ci
                 SET next_sync_at=$3,updated_at=$1
                 FROM due WHERE ci.id=due.id
                 RETURNING ci.id,due.next_sync_at
               )
               SELECT id,next_sync_at FROM claimed ORDER BY next_sync_at,id""",
            claimed_at, limit, lease_until,
        )
        return [row["id"] for row in rows]

    async def release_claim(self, instance_id: UUID, *, now: datetime) -> None:
        """Make a failed enqueue immediately eligible without altering run history."""

        await self.postgres.execute(
            """UPDATE connector_instances SET next_sync_at=$2,updated_at=$2
               WHERE id=$1 AND status IN ('connected','degraded')
                 AND NOT EXISTS (
                   SELECT 1 FROM connector_sync_runs csr
                   WHERE csr.connector_instance_id=$1
                     AND csr.status IN ('pending','running')
                 )""",
            instance_id, _utc(now),
        )

    async def enqueue_due(
        self,
        enqueue: EnqueueSync,
        *,
        now: datetime,
        limit: int = 100,
    ) -> dict[str, object]:
        due = await self.claim_due(now=now, limit=limit)
        queued: list[dict[str, str]] = []
        errors: list[dict[str, str]] = []
        for instance_id in due:
            payload = {
                "connector_instance_id": str(instance_id),
                "kind": "sync",
                "cursor_key": "default",
            }
            try:
                task = enqueue(payload)
                queued.append({"connector_instance_id": str(instance_id), "task_id": str(task.id)})
            except Exception as exc:  # the claim must not strand a due instance
                await self.release_claim(instance_id, now=now)
                errors.append({
                    "connector_instance_id": str(instance_id),
                    "error_type": type(exc).__name__,
                })
        return {"claimed": len(due), "queued": queued, "errors": errors}

    async def health_for(self, instance: ConnectorInstance, *, history_limit: int = 100) -> ConnectorHealth:
        if not 1 <= history_limit <= 1_000:
            raise ValueError("history limit must be between 1 and 1000")
        rows = await self.postgres.execute(
            """SELECT status,error FROM connector_sync_runs
               WHERE connector_instance_id=$1
               ORDER BY started_at DESC,id DESC LIMIT $2""",
            instance.id, history_limit,
        )
        return derive_failure_health(instance, rows)
