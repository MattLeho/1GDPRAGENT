from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from connectors.lifecycle import (
    ConnectorLifecycleError, RetryPolicy, connector_health, disconnect,
    mark_degraded, next_retry_at, pause, reconnect, request_backfill,
    request_sync_now, require_authentication, resume, retry_delay, with_sync_times,
)
from connectors.models import (
    ConnectorInstance, ConnectorMode, ConnectorStatus, SourceConnectorDefinition,
    SyncRunKind,
)
from connectors.synthetic import SyntheticConnector, SyntheticRecord


NOW = datetime(2026, 7, 13, 9, tzinfo=timezone.utc)


def _definition(**changes) -> SourceConnectorDefinition:
    values = dict(
        key="test.synthetic", version="1", display_name="Synthetic",
        provider="test", connector_type="synthetic",
        modes=(ConnectorMode.INCREMENTAL_POLL,), data_classes=("synthetic_event",),
        permissions=(), supports_backfill=True, supports_incremental=True,
    )
    values.update(changes)
    return SourceConnectorDefinition(**values)


def _instance(**changes) -> ConnectorInstance:
    values = dict(
        id=uuid4(), definition_key="test.synthetic", definition_version="1",
        display_name="Synthetic", status=ConnectorStatus.CONNECTED,
        created_at=NOW, updated_at=NOW,
    )
    values.update(changes)
    return ConnectorInstance(**values)


def test_pause_blocks_sync_and_resume_preserves_cursor():
    definition, instance = _definition(), _instance()
    source = SyntheticConnector(instance.id, [
        SyntheticRecord("one", {"value": 1}), SyntheticRecord("two", {"value": 2}),
    ], observed_at=NOW)
    first = source.read(limit=1)

    paused = pause(instance, at=NOW + timedelta(seconds=1))
    assert paused.status is ConnectorStatus.PAUSED and paused.next_sync_at is None
    with pytest.raises(ConnectorLifecycleError, match="paused"):
        request_sync_now(definition, paused, cursor=first.cursor_after)

    resumed = resume(paused, at=NOW + timedelta(seconds=2))
    request = request_sync_now(definition, resumed, cursor=first.cursor_after, requested_at=NOW)
    second = source.read(first.cursor_after, limit=1)
    assert request.cursor_position == {"offset": 1}
    assert [record.source_record_id for record in second.records] == ["two"]


def test_disconnect_and_reconnect_do_not_erase_history_or_cursor():
    definition, instance = _definition(), _instance()
    records = [SyntheticRecord("one", {"value": 1}), SyntheticRecord("two", {"value": 2})]
    source = SyntheticConnector(instance.id, records, observed_at=NOW)
    cursor = source.read(limit=1).cursor_after

    offline = disconnect(instance, at=NOW)
    assert source.historical_records == tuple(records)
    with pytest.raises(ConnectorLifecycleError, match="disconnected"):
        request_sync_now(definition, offline, cursor=cursor)

    online = reconnect(offline, at=NOW + timedelta(seconds=1))
    assert request_sync_now(definition, online, cursor=cursor).cursor_position == {"offset": 1}
    assert source.read(cursor).records[0].source_record_id == "two"


def test_sync_now_and_backfill_are_validated_requests_not_a_second_scheduler():
    instance = _instance()
    assert request_sync_now(_definition(), instance, requested_at=NOW).kind is SyncRunKind.SYNC
    assert request_backfill(_definition(), instance, requested_at=NOW).kind is SyncRunKind.BACKFILL
    with pytest.raises(ConnectorLifecycleError, match="backfill"):
        request_backfill(_definition(supports_backfill=False), instance)
    with pytest.raises(ConnectorLifecycleError, match="incremental"):
        request_sync_now(_definition(
            supports_incremental=False, modes=(ConnectorMode.SNAPSHOT_IMPORT,),
        ), instance)


def test_retry_backoff_is_exponential_capped_and_bounded():
    policy = RetryPolicy(
        max_attempts=5, initial_delay=timedelta(seconds=2),
        maximum_delay=timedelta(seconds=5), multiplier=2,
    )
    assert [retry_delay(n, policy) for n in range(1, 6)] == [
        timedelta(seconds=2), timedelta(seconds=4), timedelta(seconds=5),
        timedelta(seconds=5), None,
    ]
    assert next_retry_at(2, failed_at=NOW, policy=policy) == NOW + timedelta(seconds=4)


def test_health_and_last_next_sync_dtos_cover_degraded_and_authentication_required():
    scheduled = with_sync_times(
        _instance(), last_sync_at=NOW, next_sync_at=NOW + timedelta(hours=1), at=NOW,
    )
    health = connector_health(mark_degraded(scheduled, at=NOW), consecutive_failures=2)
    assert health.degraded and health.sync_available and not health.healthy
    assert health.last_sync_at == NOW and health.next_sync_at == NOW + timedelta(hours=1)

    auth = connector_health(require_authentication(scheduled, at=NOW), detail="credential expired")
    assert auth.authentication_required and not auth.sync_available


def test_synthetic_duplicates_are_byte_for_byte_deterministic_and_cursor_advances():
    instance = _instance()
    duplicate = SyntheticRecord("same", {"b": 2, "a": 1})
    source = SyntheticConnector(instance.id, [duplicate, duplicate], observed_at=NOW)
    batch = source.read(limit=2)
    assert len(batch.records) == 2 and batch.exhausted
    assert batch.records[0].payload == batch.records[1].payload == b'{"a":1,"b":2}'
    assert batch.records[0].record_signature == batch.records[1].record_signature
    assert batch.cursor_after.position == {"offset": 2}
