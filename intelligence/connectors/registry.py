"""Connector definition registry and provider-neutral dispatch.

The registry describes acquisition capabilities only.  It deliberately has no
dependency on the graph, evidence semantics, or connector credentials.
"""
from __future__ import annotations

from dataclasses import dataclass
from inspect import isawaitable
from typing import Awaitable, Callable, Iterable, Protocol

from .models import (
    ConnectorInstance,
    ConnectorPermission,
    ConnectorRawRecord,
    ConnectorCursor,
    PermissionAccess,
    SourceConnectorDefinition,
    SyncRunKind,
)


class ConnectorRegistryError(ValueError):
    """Base class for deterministic registry validation failures."""


class ConnectorNotRegisteredError(ConnectorRegistryError):
    pass


class ConnectorAlreadyRegisteredError(ConnectorRegistryError):
    pass


class ConnectorPermissionError(ConnectorRegistryError):
    pass


_CREDENTIAL_WORDS = {
    "password", "secret", "token", "api_key", "access_token",
    "refresh_token", "credential", "credentials",
}


@dataclass(frozen=True, slots=True)
class ConnectorSyncRequest:
    instance: ConnectorInstance
    kind: SyncRunKind
    cursor: ConnectorCursor | None


@dataclass(frozen=True, slots=True)
class ConnectorSyncBatch:
    """A finite provider acquisition result.

    Acquisition adapters return opaque source records only.  Event counts are
    deliberately absent: only the canonical ingestion bridge may produce
    ActivityEvents.
    """

    records: tuple[ConnectorRawRecord, ...] = ()
    cursor_position: dict[str, object] | None = None
    source_watermark: str | None = None
    errors: int = 0

    def __post_init__(self) -> None:
        if self.errors < 0:
            raise ValueError("connector batch metrics must be non-negative")


class SourceConnector(Protocol):
    definition: SourceConnectorDefinition

    def acquire(
        self, request: ConnectorSyncRequest
    ) -> ConnectorSyncBatch | Awaitable[ConnectorSyncBatch]: ...


ConnectorFactory = Callable[[ConnectorInstance], SourceConnector]


def _schema_contains_credentials(value: object, *, parent: str = "") -> bool:
    if isinstance(value, dict):
        for key, child in value.items():
            folded = str(key).casefold()
            # JSON Schema's property names live below ``properties``.
            if parent == "properties" and folded in _CREDENTIAL_WORDS:
                return True
            if _schema_contains_credentials(child, parent=folded):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_schema_contains_credentials(child, parent=parent) for child in value)
    return False


def validate_definition(definition: SourceConnectorDefinition) -> None:
    """Apply cross-field rules intentionally kept outside frozen contracts."""

    permission_keys = [permission.key for permission in definition.permissions]
    if len(permission_keys) != len(set(permission_keys)):
        raise ConnectorRegistryError("connector permission keys must be unique")
    if len(definition.data_classes) != len(set(definition.data_classes)):
        raise ConnectorRegistryError("connector data classes must be unique")
    declared_classes = set(definition.data_classes)
    for permission in definition.permissions:
        if permission.data_class not in declared_classes:
            raise ConnectorRegistryError(
                f"permission {permission.key!r} references undeclared data class "
                f"{permission.data_class!r}"
            )
    schema = definition.configuration_schema
    if schema and schema.get("type", "object") != "object":
        raise ConnectorRegistryError("connector configuration schema must describe an object")
    if _schema_contains_credentials(schema):
        raise ConnectorRegistryError(
            "connector configuration schemas cannot declare credentials; use encrypted credential storage"
        )


def validate_enabled_permissions(
    definition: SourceConnectorDefinition, enabled_permissions: Iterable[str]
) -> tuple[str, ...]:
    """Enforce the definition as the maximum permission grant."""

    enabled = tuple(dict.fromkeys(enabled_permissions))
    declared = {permission.key: permission for permission in definition.permissions}
    unknown = set(enabled) - declared.keys()
    denied = {
        key for key in enabled
        if declared.get(key) and declared[key].access is PermissionAccess.NOT_READ
    }
    required = {
        permission.key for permission in definition.permissions
        if permission.required and permission.access is not PermissionAccess.NOT_READ
    }
    missing = required - set(enabled)
    if unknown:
        raise ConnectorPermissionError(f"undeclared connector permissions: {sorted(unknown)}")
    if denied:
        raise ConnectorPermissionError(f"permissions declared not_read cannot be enabled: {sorted(denied)}")
    if missing:
        raise ConnectorPermissionError(f"required connector permissions are missing: {sorted(missing)}")
    return enabled


def validate_record_permissions(
    definition: SourceConnectorDefinition,
    enabled_permissions: Iterable[str],
    record: ConnectorRawRecord,
) -> None:
    enabled = set(validate_enabled_permissions(definition, enabled_permissions))
    if record.data_class not in definition.data_classes:
        raise ConnectorPermissionError(
            f"record data class {record.data_class!r} is not declared by {definition.key!r}"
        )
    required = set(record.required_permissions)
    undeclared = required - {permission.key for permission in definition.permissions}
    unavailable = required - enabled
    if undeclared:
        raise ConnectorPermissionError(f"record requires undeclared permissions: {sorted(undeclared)}")
    if unavailable:
        raise ConnectorPermissionError(f"record exceeds enabled permissions: {sorted(unavailable)}")


class ConnectorRegistry:
    def __init__(self) -> None:
        self._definitions: dict[tuple[str, str], SourceConnectorDefinition] = {}
        self._factories: dict[tuple[str, str], ConnectorFactory] = {}

    def register(self, definition: SourceConnectorDefinition, factory: ConnectorFactory) -> None:
        validate_definition(definition)
        key = (definition.key, definition.version)
        if key in self._definitions:
            raise ConnectorAlreadyRegisteredError(
                f"connector {definition.key!r} version {definition.version!r} is already registered"
            )
        self._definitions[key] = definition
        self._factories[key] = factory

    def get_definition(self, key: str, version: str) -> SourceConnectorDefinition:
        try:
            return self._definitions[(key, version)]
        except KeyError as exc:
            raise ConnectorNotRegisteredError(
                f"connector {key!r} version {version!r} is not registered"
            ) from exc

    def definitions(self) -> tuple[SourceConnectorDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions))

    async def dispatch(
        self, instance: ConnectorInstance, kind: SyncRunKind, cursor: ConnectorCursor | None
    ) -> ConnectorSyncBatch:
        definition = self.get_definition(instance.definition_key, instance.definition_version)
        validate_enabled_permissions(definition, instance.enabled_permissions)
        if kind is SyncRunKind.BACKFILL and not definition.supports_backfill:
            raise ConnectorRegistryError(f"connector {definition.key!r} does not support backfill")
        if kind is SyncRunKind.SYNC and not definition.supports_incremental:
            raise ConnectorRegistryError(f"connector {definition.key!r} does not support incremental sync")
        connector = self._factories[(definition.key, definition.version)](instance)
        result = connector.acquire(ConnectorSyncRequest(instance=instance, kind=kind, cursor=cursor))
        if isawaitable(result):
            result = await result
        if not isinstance(result, ConnectorSyncBatch):
            raise TypeError("connector acquire() must return ConnectorSyncBatch")
        return result
