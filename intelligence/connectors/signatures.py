"""Canonical, provider-neutral connector record signatures."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Mapping
from uuid import UUID


def canonical_json(value: Any) -> bytes:
    def default(item: Any) -> Any:
        if isinstance(item, datetime):
            normalised = item if item.tzinfo else item.replace(tzinfo=timezone.utc)
            return normalised.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        if isinstance(item, UUID):
            return str(item)
        raise TypeError(f"unsupported signature value: {type(item).__name__}")

    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False, default=default,
    ).encode("utf-8")


def connector_record_signature(
    *, source_record_id: str, payload: bytes,
    source_record_version: str = "1", data_class: str,
    occurred_at: datetime | None = None, media_type: str,
    source_metadata: Mapping[str, Any] | None = None,
) -> str:
    """Sign immutable source identity and content, excluding observation/run time."""

    if not source_record_id:
        raise ValueError("source_record_id must not be empty")
    if not isinstance(payload, bytes):
        raise TypeError("payload must be bytes")
    descriptor = {
        "data_class": data_class,
        "media_type": media_type.casefold(),
        "occurred_at": occurred_at,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "source_metadata": dict(source_metadata or {}),
        "source_record_id": source_record_id,
        "source_record_version": source_record_version,
    }
    return hashlib.sha256(canonical_json(descriptor)).hexdigest()
