"""Pure connector lifecycle helpers.

The module deliberately does not schedule work or perform connector I/O.  It
validates user requests and computes the state that a persistence/runtime layer
may store or enqueue using the existing Task 2 scheduling facilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .models import (
    ConnectorCursor,
    ConnectorInstance,
    ConnectorStatus,
    SourceConnectorDefinition,
    SyncRunKind,
)


class ConnectorLifecycleError(ValueError):
    """Raised when a requested lifecycle operation is not valid."""


class SyncTrigger(str, Enum):
    MANUAL = "manual"
    SCHEDULED = "scheduled"
    RETRY = "retry"


class SyncRequest(BaseModel):
    """A validated request for the existing execution/scheduling layer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    connector_instance_id: UUID
    kind: SyncRunKind
    trigger: SyncTrigger = SyncTrigger.MANUAL
    cursor_key: str = Field(default="default", min_length=1)
    cursor_position: dict[str, object] = Field(default_factory=dict)
    requested_at: datetime


class ConnectorHealth(BaseModel):
    """Public, non-secret connector status DTO."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ConnectorStatus
    healthy: bool
    sync_available: bool
    degraded: bool
    authentication_required: bool
    last_sync_at: datetime | None
    next_sync_at: datetime | None
    consecutive_failures: int = Field(default=0, ge=0)
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounded exponential retry configuration.

    ``max_attempts`` includes the initial attempt.  Consequently, with a value
    of three, delays exist after failed attempts one and two only.
    """

    max_attempts: int = 5
    initial_delay: timedelta = timedelta(seconds=5)
    maximum_delay: timedelta = timedelta(minutes=15)
    multiplier: float = 2.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one")
        if self.initial_delay < timedelta(0) or self.maximum_delay < timedelta(0):
            raise ValueError("retry delays cannot be negative")
        if self.initial_delay > self.maximum_delay:
            raise ValueError("initial_delay cannot exceed maximum_delay")
        if self.multiplier < 1:
            raise ValueError("multiplier must be at least one")


_ALLOWED_TRANSITIONS: dict[ConnectorStatus, frozenset[ConnectorStatus]] = {
    ConnectorStatus.CONNECTED: frozenset({
        ConnectorStatus.PAUSED,
        ConnectorStatus.DEGRADED,
        ConnectorStatus.AUTHENTICATION_REQUIRED,
        ConnectorStatus.ERROR,
        ConnectorStatus.DISCONNECTED,
    }),
    ConnectorStatus.PAUSED: frozenset({
        ConnectorStatus.CONNECTED,
        ConnectorStatus.AUTHENTICATION_REQUIRED,
        ConnectorStatus.DISCONNECTED,
    }),
    ConnectorStatus.DEGRADED: frozenset({
        ConnectorStatus.CONNECTED,
        ConnectorStatus.PAUSED,
        ConnectorStatus.AUTHENTICATION_REQUIRED,
        ConnectorStatus.ERROR,
        ConnectorStatus.DISCONNECTED,
    }),
    ConnectorStatus.AUTHENTICATION_REQUIRED: frozenset({
        ConnectorStatus.CONNECTED,
        ConnectorStatus.DISCONNECTED,
    }),
    ConnectorStatus.ERROR: frozenset({
        ConnectorStatus.CONNECTED,
        ConnectorStatus.PAUSED,
        ConnectorStatus.AUTHENTICATION_REQUIRED,
        ConnectorStatus.DISCONNECTED,
    }),
    ConnectorStatus.DISCONNECTED: frozenset({ConnectorStatus.CONNECTED}),
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def transition(
    instance: ConnectorInstance,
    status: ConnectorStatus,
    *,
    at: datetime | None = None,
) -> ConnectorInstance:
    """Return an updated instance after enforcing the generic state machine."""

    if status is instance.status:
        return instance
    if status not in _ALLOWED_TRANSITIONS[instance.status]:
        raise ConnectorLifecycleError(
            f"cannot transition connector from {instance.status.value} to {status.value}"
        )
    changes: dict[str, object] = {"status": status, "updated_at": at or _utc_now()}
    if status in {
        ConnectorStatus.PAUSED,
        ConnectorStatus.AUTHENTICATION_REQUIRED,
        ConnectorStatus.DISCONNECTED,
    }:
        changes["next_sync_at"] = None
    return instance.model_copy(update=changes)


def pause(instance: ConnectorInstance, *, at: datetime | None = None) -> ConnectorInstance:
    return transition(instance, ConnectorStatus.PAUSED, at=at)


def resume(instance: ConnectorInstance, *, at: datetime | None = None) -> ConnectorInstance:
    if instance.status is not ConnectorStatus.PAUSED:
        raise ConnectorLifecycleError("only a paused connector can be resumed")
    return transition(instance, ConnectorStatus.CONNECTED, at=at)


def disconnect(instance: ConnectorInstance, *, at: datetime | None = None) -> ConnectorInstance:
    """Disconnect operationally; cursors and historical records are untouched."""

    return transition(instance, ConnectorStatus.DISCONNECTED, at=at)


def reconnect(instance: ConnectorInstance, *, at: datetime | None = None) -> ConnectorInstance:
    if instance.status not in {
        ConnectorStatus.DISCONNECTED,
        ConnectorStatus.DEGRADED,
        ConnectorStatus.ERROR,
        ConnectorStatus.AUTHENTICATION_REQUIRED,
    }:
        raise ConnectorLifecycleError("connector is not in a reconnectable state")
    return transition(instance, ConnectorStatus.CONNECTED, at=at)


def mark_degraded(instance: ConnectorInstance, *, at: datetime | None = None) -> ConnectorInstance:
    return transition(instance, ConnectorStatus.DEGRADED, at=at)


def require_authentication(
    instance: ConnectorInstance, *, at: datetime | None = None
) -> ConnectorInstance:
    return transition(instance, ConnectorStatus.AUTHENTICATION_REQUIRED, at=at)


def _request(
    definition: SourceConnectorDefinition,
    instance: ConnectorInstance,
    kind: SyncRunKind,
    *,
    cursor: ConnectorCursor | None,
    requested_at: datetime | None,
    trigger: SyncTrigger,
) -> SyncRequest:
    if instance.definition_key != definition.key or instance.definition_version != definition.version:
        raise ConnectorLifecycleError("connector instance does not match definition")
    if instance.status in {
        ConnectorStatus.PAUSED,
        ConnectorStatus.DISCONNECTED,
        ConnectorStatus.AUTHENTICATION_REQUIRED,
        ConnectorStatus.ERROR,
    }:
        raise ConnectorLifecycleError(f"sync unavailable while connector is {instance.status.value}")
    if kind is SyncRunKind.SYNC and not definition.supports_incremental:
        raise ConnectorLifecycleError("connector does not support incremental sync")
    if kind is SyncRunKind.BACKFILL and not definition.supports_backfill:
        raise ConnectorLifecycleError("connector does not support backfill")
    if cursor is not None and cursor.connector_instance_id != instance.id:
        raise ConnectorLifecycleError("cursor belongs to a different connector instance")
    return SyncRequest(
        connector_instance_id=instance.id,
        kind=kind,
        trigger=trigger,
        cursor_key=cursor.cursor_key if cursor else "default",
        cursor_position=dict(cursor.position) if cursor else {},
        requested_at=requested_at or _utc_now(),
    )


def request_sync_now(
    definition: SourceConnectorDefinition,
    instance: ConnectorInstance,
    *,
    cursor: ConnectorCursor | None = None,
    requested_at: datetime | None = None,
) -> SyncRequest:
    """Validate an immediate incremental request without running it."""

    return _request(
        definition, instance, SyncRunKind.SYNC, cursor=cursor,
        requested_at=requested_at, trigger=SyncTrigger.MANUAL,
    )


def request_backfill(
    definition: SourceConnectorDefinition,
    instance: ConnectorInstance,
    *,
    cursor: ConnectorCursor | None = None,
    requested_at: datetime | None = None,
) -> SyncRequest:
    """Validate an explicit backfill request without resetting a saved cursor."""

    return _request(
        definition, instance, SyncRunKind.BACKFILL, cursor=cursor,
        requested_at=requested_at, trigger=SyncTrigger.MANUAL,
    )


def retry_delay(failed_attempt: int, policy: RetryPolicy = RetryPolicy()) -> timedelta | None:
    """Return a capped delay, or ``None`` once the attempt budget is exhausted."""

    if failed_attempt < 1:
        raise ValueError("failed_attempt must be at least one")
    if failed_attempt >= policy.max_attempts:
        return None
    seconds = policy.initial_delay.total_seconds() * policy.multiplier ** (failed_attempt - 1)
    return min(timedelta(seconds=seconds), policy.maximum_delay)


def next_retry_at(
    failed_attempt: int,
    *,
    failed_at: datetime,
    policy: RetryPolicy = RetryPolicy(),
) -> datetime | None:
    delay = retry_delay(failed_attempt, policy)
    return None if delay is None else failed_at + delay


def with_sync_times(
    instance: ConnectorInstance,
    *,
    last_sync_at: datetime | None = None,
    next_sync_at: datetime | None = None,
    at: datetime | None = None,
) -> ConnectorInstance:
    """Build the public last/next-sync DTO state; no scheduling is performed."""

    if instance.status in {ConnectorStatus.PAUSED, ConnectorStatus.DISCONNECTED} and next_sync_at:
        raise ConnectorLifecycleError("inactive connectors cannot have a next sync")
    return instance.model_copy(update={
        "last_sync_at": last_sync_at,
        "next_sync_at": next_sync_at,
        "updated_at": at or _utc_now(),
    })


def connector_health(
    instance: ConnectorInstance,
    *,
    consecutive_failures: int = 0,
    detail: str | None = None,
) -> ConnectorHealth:
    """Return a stable health/status response suitable for Settings/API use."""

    if consecutive_failures < 0:
        raise ValueError("consecutive_failures cannot be negative")
    available = instance.status in {ConnectorStatus.CONNECTED, ConnectorStatus.DEGRADED}
    return ConnectorHealth(
        status=instance.status,
        healthy=instance.status is ConnectorStatus.CONNECTED,
        sync_available=available,
        degraded=instance.status is ConnectorStatus.DEGRADED,
        authentication_required=instance.status is ConnectorStatus.AUTHENTICATION_REQUIRED,
        last_sync_at=instance.last_sync_at,
        next_sync_at=instance.next_sync_at,
        consecutive_failures=consecutive_failures,
        detail=detail,
    )
