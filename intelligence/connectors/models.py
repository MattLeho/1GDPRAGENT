"""Frozen cross-connector contracts.

These models describe source acquisition and lifecycle only.  They do not
represent graph truth, inferred interests, importance, or retention outcomes.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


_SECRET_KEYS = {"password", "secret", "token", "api_key", "access_token", "refresh_token", "credential"}


def _assert_public_configuration(configuration: dict[str, Any]) -> None:
    unsafe = {str(key).casefold() for key in configuration} & _SECRET_KEYS
    if unsafe:
        raise ValueError(f"connector secrets must use encrypted credential storage: {sorted(unsafe)}")


class ConnectorMode(str, Enum):
    SNAPSHOT_IMPORT = "snapshot_import"
    INCREMENTAL_POLL = "incremental_poll"
    EVENT_STREAM = "event_stream"
    WEBHOOK_PUSH = "webhook_push"
    FOLDER_WATCH = "folder_watch"


class ConnectorStatus(str, Enum):
    CONNECTED = "connected"
    PAUSED = "paused"
    DEGRADED = "degraded"
    AUTHENTICATION_REQUIRED = "authentication_required"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class SyncRunKind(str, Enum):
    SYNC = "sync"
    BACKFILL = "backfill"


class SyncRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PermissionAccess(str, Enum):
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    NOT_READ = "not_read"


class ConnectorPermission(FrozenModel):
    key: str = Field(min_length=1)
    access: PermissionAccess
    data_class: str = Field(min_length=1)
    description: str = Field(min_length=1)
    required: bool = False
    enabled_by_default: bool = False

    @model_validator(mode="after")
    def denied_permissions_cannot_be_enabled(self):
        if self.access is PermissionAccess.NOT_READ and (self.required or self.enabled_by_default):
            raise ValueError("not_read permissions cannot be required or enabled")
        return self


class SourceConnectorDefinition(FrozenModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]+$")
    version: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    connector_type: str = Field(min_length=1)
    modes: tuple[ConnectorMode, ...]
    data_classes: tuple[str, ...]
    permissions: tuple[ConnectorPermission, ...]
    supports_backfill: bool = False
    supports_incremental: bool = False
    supports_source_delete: bool = False
    supports_remote_delete_request: bool = False
    configuration_schema: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def capabilities_match_modes(self):
        if not self.modes:
            raise ValueError("at least one connector mode is required")
        if self.supports_incremental and not any(mode in self.modes for mode in (
            ConnectorMode.INCREMENTAL_POLL, ConnectorMode.EVENT_STREAM,
            ConnectorMode.WEBHOOK_PUSH, ConnectorMode.FOLDER_WATCH,
        )):
            raise ValueError("incremental capability requires an incremental mode")
        return self


class ConnectorInstance(FrozenModel):
    id: UUID
    definition_key: str
    definition_version: str
    profile_id: UUID | None = None
    account_key: str = "default"
    display_name: str
    status: ConnectorStatus
    enabled_permissions: tuple[str, ...] = ()
    configuration: dict[str, Any] = Field(default_factory=dict)
    credential_id: UUID | None = None
    last_sync_at: datetime | None = None
    next_sync_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def configuration_is_non_secret(self):
        _assert_public_configuration(self.configuration)
        return self


class ConnectorCursor(FrozenModel):
    connector_instance_id: UUID
    cursor_key: str = "default"
    version: int = Field(default=1, ge=1)
    position: dict[str, Any] = Field(default_factory=dict)
    source_watermark: str | None = None
    updated_at: datetime


class ConnectorRawRecord(FrozenModel):
    connector_instance_id: UUID
    source_record_id: str = Field(min_length=1)
    source_record_version: str = "1"
    record_signature: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_class: str = Field(min_length=1)
    occurred_at: datetime | None = None
    observed_at: datetime
    media_type: str
    payload: bytes = Field(repr=False, exclude=True)
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    required_permissions: tuple[str, ...] = ()


class ConnectorSyncRun(FrozenModel):
    id: UUID
    connector_instance_id: UUID
    analysis_run_id: UUID
    kind: SyncRunKind
    status: SyncRunStatus
    cursor_before: dict[str, Any] = Field(default_factory=dict)
    cursor_after: dict[str, Any] = Field(default_factory=dict)
    artefacts_discovered: int = Field(default=0, ge=0)
    events_produced: int = Field(default=0, ge=0)
    duplicates_skipped: int = Field(default=0, ge=0)
    errors: int = Field(default=0, ge=0)
    started_at: datetime
    completed_at: datetime | None = None


class EmailTransport(FrozenModel):
    key: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    supports_draft: bool = True
    supports_review: bool = True
    supports_send: bool = True
    credential_id: UUID
    configuration: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def configuration_is_non_secret(self):
        _assert_public_configuration(self.configuration)
        return self
