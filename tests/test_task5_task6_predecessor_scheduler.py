from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from connectors.models import ConnectorInstance, ConnectorStatus
from connectors.scheduler import ConnectorScheduler, derive_failure_health


NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _instance(**changes) -> ConnectorInstance:
    values = dict(
        id=uuid4(), definition_key="test.synthetic", definition_version="1",
        display_name="Fixture", status=ConnectorStatus.DEGRADED,
        last_sync_at=NOW - timedelta(hours=1), next_sync_at=NOW,
        created_at=NOW - timedelta(days=1), updated_at=NOW,
    )
    values.update(changes)
    return ConnectorInstance(**values)


@pytest.mark.asyncio
async def test_due_claim_is_atomic_deterministic_and_excludes_active_runs():
    first, second = uuid4(), uuid4()
    postgres = SimpleNamespace(execute=AsyncMock(return_value=[
        {"id": first, "next_sync_at": NOW - timedelta(minutes=2)},
        {"id": second, "next_sync_at": NOW - timedelta(minutes=1)},
    ]))

    claimed = await ConnectorScheduler(postgres).claim_due(now=NOW, limit=2)

    assert claimed == [first, second]
    query, claimed_at, limit, lease_until = postgres.execute.await_args.args
    assert "ORDER BY ci.next_sync_at,ci.id" in query
    assert "FOR UPDATE OF ci SKIP LOCKED" in query
    assert "csr.status IN ('pending','running')" in query
    assert (claimed_at, limit, lease_until) == (NOW, 2, NOW + timedelta(minutes=5))


@pytest.mark.asyncio
async def test_enqueue_due_reuses_canonical_sync_payload_and_releases_failed_claim():
    succeeds, fails = uuid4(), uuid4()
    postgres = SimpleNamespace(execute=AsyncMock(return_value=[]))
    scheduler = ConnectorScheduler(postgres)
    scheduler.claim_due = AsyncMock(return_value=[succeeds, fails])
    scheduler.release_claim = AsyncMock()
    enqueue = Mock(side_effect=[SimpleNamespace(id="task-1"), OSError("broker unavailable")])

    result = await scheduler.enqueue_due(enqueue, now=NOW)

    assert enqueue.call_args_list[0].args[0] == {
        "connector_instance_id": str(succeeds), "kind": "sync", "cursor_key": "default",
    }
    assert result["queued"] == [{
        "connector_instance_id": str(succeeds), "task_id": "task-1",
    }]
    assert result["errors"] == [{
        "connector_instance_id": str(fails), "error_type": "OSError",
    }]
    scheduler.release_claim.assert_awaited_once_with(fails, now=NOW)


def test_health_derives_consecutive_failures_and_non_secret_detail_from_history():
    instance = _instance()
    health = derive_failure_health(instance, [
        {"status": "running", "error": None},
        {"status": "failed", "error": {"type": "TimeoutError", "message": "timed out"}},
        {"status": "failed", "error": {"type": "OSError", "message": "offline"}},
        {"status": "completed", "error": None},
        {"status": "failed", "error": {"message": "old failure"}},
    ])

    assert health.status is ConnectorStatus.DEGRADED
    assert health.consecutive_failures == 2
    assert health.detail == "timed out"
    assert health.last_sync_at == instance.last_sync_at
    assert health.next_sync_at == instance.next_sync_at


@pytest.mark.asyncio
async def test_health_history_query_has_stable_newest_first_order():
    instance = _instance(status=ConnectorStatus.CONNECTED)
    postgres = SimpleNamespace(execute=AsyncMock(return_value=[]))

    health = await ConnectorScheduler(postgres).health_for(instance)

    assert health.healthy and health.consecutive_failures == 0
    query, instance_id, limit = postgres.execute.await_args.args
    assert "ORDER BY started_at DESC,id DESC" in query
    assert (instance_id, limit) == (instance.id, 100)


def test_scheduler_task_is_registered_as_periodic_adapter_to_existing_sync_task():
    from tasks import app, connector_schedule_due, connector_sync

    assert connector_sync.name == "intelligence.connectors.sync"
    assert connector_schedule_due.name == "intelligence.connectors.schedule_due"
    entry = app.conf.beat_schedule["connector-recurring-sync"]
    assert entry["task"] == connector_schedule_due.name
    assert entry["schedule"] == 60.0
