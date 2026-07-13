"""Deterministic connector/cursor source used by connector acceptance tests."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import UUID

from .models import ConnectorCursor, ConnectorRawRecord
from .signatures import connector_record_signature


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class SyntheticRecord:
    source_record_id: str
    payload: dict[str, Any]
    occurred_at: datetime | None = None
    source_record_version: str = "1"
    data_class: str = "synthetic_event"
    media_type: str = "application/json"
    source_metadata: dict[str, Any] | None = None
    required_permissions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SyntheticBatch:
    records: tuple[ConnectorRawRecord, ...]
    cursor_after: ConnectorCursor
    exhausted: bool


class SyntheticConnector:
    """A no-I/O source whose offset cursor survives lifecycle state changes.

    Records are retained verbatim and duplicates are intentional: equal logical
    records produce equal signatures so the canonical ingestion layer can prove
    its idempotency behavior.
    """

    def __init__(
        self,
        connector_instance_id: UUID,
        records: Iterable[SyntheticRecord],
        *,
        observed_at: datetime | None = None,
    ) -> None:
        self.connector_instance_id = connector_instance_id
        self._records = tuple(records)
        self.observed_at = observed_at or datetime(2026, 1, 1, tzinfo=timezone.utc)

    @property
    def historical_records(self) -> tuple[SyntheticRecord, ...]:
        return self._records

    def initial_cursor(self, *, updated_at: datetime | None = None) -> ConnectorCursor:
        return ConnectorCursor(
            connector_instance_id=self.connector_instance_id,
            position={"offset": 0},
            updated_at=updated_at or self.observed_at,
        )

    def read(
        self,
        cursor: ConnectorCursor | None = None,
        *,
        limit: int = 100,
        updated_at: datetime | None = None,
    ) -> SyntheticBatch:
        if limit < 1:
            raise ValueError("limit must be at least one")
        cursor = cursor or self.initial_cursor(updated_at=updated_at)
        if cursor.connector_instance_id != self.connector_instance_id:
            raise ValueError("cursor belongs to a different connector instance")
        offset = cursor.position.get("offset", 0)
        if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
            raise ValueError("synthetic cursor offset must be a non-negative integer")
        selected = self._records[offset : offset + limit]
        raw = tuple(self._to_raw(record) for record in selected)
        next_offset = offset + len(selected)
        next_cursor = ConnectorCursor(
            connector_instance_id=self.connector_instance_id,
            cursor_key=cursor.cursor_key,
            version=cursor.version,
            position={"offset": next_offset},
            source_watermark=str(next_offset),
            updated_at=updated_at or self.observed_at,
        )
        return SyntheticBatch(
            records=raw,
            cursor_after=next_cursor,
            exhausted=next_offset >= len(self._records),
        )

    def _to_raw(self, record: SyntheticRecord) -> ConnectorRawRecord:
        payload = _canonical_json(record.payload)
        metadata = dict(record.source_metadata or {})
        return ConnectorRawRecord(
            connector_instance_id=self.connector_instance_id,
            source_record_id=record.source_record_id,
            source_record_version=record.source_record_version,
            record_signature=connector_record_signature(
                source_record_id=record.source_record_id,
                source_record_version=record.source_record_version,
                payload=payload, data_class=record.data_class,
                occurred_at=record.occurred_at, media_type=record.media_type,
                source_metadata=metadata,
            ),
            data_class=record.data_class,
            occurred_at=record.occurred_at,
            observed_at=self.observed_at,
            media_type=record.media_type,
            payload=payload,
            source_metadata=metadata,
            required_permissions=record.required_permissions,
        )
