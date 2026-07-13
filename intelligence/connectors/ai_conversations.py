"""Deterministic snapshot connector for known AI conversation export shapes."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from .definitions import AI_CONVERSATION_DEFINITION
from .models import ConnectorInstance, ConnectorRawRecord
from .registry import ConnectorSyncBatch, ConnectorSyncRequest
from .signatures import canonical_json, connector_record_signature


class AIExportConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    paths: tuple[str, ...]
    service: str = "auto"
    max_file_bytes: int = Field(default=128 * 1024 * 1024, ge=1, le=512 * 1024 * 1024)


class AIConversationSnapshotConnector:
    definition = AI_CONVERSATION_DEFINITION

    def __init__(self, instance: ConnectorInstance) -> None:
        self.instance = instance
        self.config = AIExportConfiguration.model_validate(instance.configuration)

    def acquire(self, request: ConnectorSyncRequest) -> ConnectorSyncBatch:
        before = dict(request.cursor.position.get("exports") or {}) if request.cursor else {}
        after: dict[str, str] = {}
        records: list[ConnectorRawRecord] = []
        for value in self.config.paths:
            path = Path(value).expanduser().resolve(strict=True)
            if not path.is_file() or path.suffix.casefold() != ".json":
                raise ValueError(f"AI conversation export must be an existing JSON file: {path}")
            if path.stat().st_size > self.config.max_file_bytes:
                raise ValueError(f"AI conversation export exceeds configured size: {path}")
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            key = hashlib.sha256(str(path).casefold().encode()).hexdigest()[:20]
            after[key] = digest
            if before.get(key) == digest:
                continue
            document = json.loads(raw)
            service, turns = parse_ai_export(document, service_hint=self.config.service)
            records.append(self._export_record(path, key, digest, raw, service))
            records.extend(self._turn_records(key, digest, service, turns))
        return ConnectorSyncBatch(
            records=tuple(records), cursor_position={"exports": after},
            source_watermark=hashlib.sha256(canonical_json(after)).hexdigest(),
        )

    def _export_record(self, path, key, digest, raw, service):
        metadata = {"file_name": path.name, "path": path.name, "export_key": key, "service": service, "content_sha256": digest}
        source_id = f"export:{key}"
        signature = connector_record_signature(
            source_record_id=source_id, source_record_version=digest, payload=raw,
            data_class="ai.conversation_export", media_type="application/json",
            source_metadata=metadata,
        )
        return ConnectorRawRecord(
            connector_instance_id=self.instance.id, source_record_id=source_id,
            source_record_version=digest, record_signature=signature,
            data_class="ai.conversation_export", observed_at=datetime.now(timezone.utc),
            media_type="application/json", payload=raw, source_metadata=metadata,
            required_permissions=("conversations.read",),
        )

    def _turn_records(self, key, digest, service, turns):
        result = []
        for turn in turns:
            payload = canonical_json(turn)
            source_id = f"turn:{key}:{turn['conversation_id']}:{turn['turn_id']}"
            metadata = {
                "export_key": key, "export_sha256": digest, "service": service,
                "conversation_id": turn["conversation_id"], "turn_id": turn["turn_id"],
                "source_pointer": turn["source_pointer"],
            }
            occurred = _datetime(turn.get("timestamp"))
            signature = connector_record_signature(
                source_record_id=source_id, source_record_version=digest, payload=payload,
                data_class="ai.conversation_turn", occurred_at=occurred,
                media_type="application/json", source_metadata=metadata,
            )
            result.append(ConnectorRawRecord(
                connector_instance_id=self.instance.id, source_record_id=source_id,
                source_record_version=digest, record_signature=signature,
                data_class="ai.conversation_turn", occurred_at=occurred,
                observed_at=datetime.now(timezone.utc), media_type="application/json",
                payload=payload, source_metadata=metadata,
                required_permissions=("conversations.read",),
            ))
        return result


def _role(value: Any) -> str:
    role = str(value or "unknown").casefold()
    role = {"human": "user", "bot": "assistant"}.get(role, role)
    return role if role in {"user", "assistant", "system", "tool"} else "unknown"


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if item is not None)
    if isinstance(value, dict):
        return str(value.get("text") or value.get("content") or "")
    return str(value or "")


def _datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc)
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)
    except (ValueError, TypeError, OSError, OverflowError):
        return None


def parse_ai_export(document: Any, *, service_hint: str = "auto") -> tuple[str, tuple[dict[str, Any], ...]]:
    if not isinstance(document, list):
        raise ValueError("AI conversation export must contain a conversation list")
    if service_hint == "chatgpt" or (document and isinstance(document[0], dict) and "mapping" in document[0]):
        return "chatgpt", tuple(_chatgpt_turns(document))
    if service_hint == "claude" or (document and isinstance(document[0], dict) and "chat_messages" in document[0]):
        return "claude", tuple(_claude_turns(document))
    if service_hint in {"auto", "generic"}:
        return "generic", tuple(_generic_turns(document))
    raise ValueError("unsupported AI conversation export service")


def _chatgpt_turns(conversations):
    for ci, conversation in enumerate(conversations):
        conversation_id = str(conversation.get("id") or conversation.get("conversation_id") or ci)
        for node_id, node in (conversation.get("mapping") or {}).items():
            message = node.get("message") if isinstance(node, dict) else None
            if not isinstance(message, dict):
                continue
            content = message.get("content") or {}
            yield {
                "conversation_id": conversation_id, "turn_id": str(message.get("id") or node_id),
                "role": _role((message.get("author") or {}).get("role")),
                "timestamp": message.get("create_time"), "service": "chatgpt",
                "model": (message.get("metadata") or {}).get("model_slug"),
                "title": conversation.get("title"), "text": _text(content.get("parts") or content.get("text")),
                "source_pointer": f"/{ci}/mapping/{str(node_id).replace('~','~0').replace('/','~1')}/message",
            }


def _claude_turns(conversations):
    for ci, conversation in enumerate(conversations):
        conversation_id = str(conversation.get("uuid") or conversation.get("id") or ci)
        for ti, message in enumerate(conversation.get("chat_messages") or []):
            yield {
                "conversation_id": conversation_id, "turn_id": str(message.get("uuid") or message.get("id") or ti),
                "role": _role(message.get("sender") or message.get("role")),
                "timestamp": message.get("created_at"), "service": "claude",
                "model": message.get("model"), "title": conversation.get("name") or conversation.get("title"),
                "text": _text(message.get("text") or message.get("content")),
                "source_pointer": f"/{ci}/chat_messages/{ti}",
            }


def _generic_turns(conversations):
    for ci, conversation in enumerate(conversations):
        if not isinstance(conversation, dict):
            continue
        conversation_id = str(conversation.get("id") or ci)
        for ti, message in enumerate(conversation.get("messages") or conversation.get("turns") or []):
            yield {
                "conversation_id": conversation_id, "turn_id": str(message.get("id") or ti),
                "role": _role(message.get("role")), "timestamp": message.get("timestamp") or message.get("created_at"),
                "service": str(conversation.get("service") or "unknown"), "model": message.get("model"),
                "title": conversation.get("title"), "text": _text(message.get("content") or message.get("text")),
                "source_pointer": f"/{ci}/{('messages' if 'messages' in conversation else 'turns')}/{ti}",
            }
