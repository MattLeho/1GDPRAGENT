"""Conservative typed-source mapping into grounded Task 3 ActivityEvents."""
from __future__ import annotations

from datetime import datetime
from email import policy
from email.parser import BytesParser
import hashlib
import json
from typing import Any, Mapping
from uuid import UUID, uuid5

from ingestion.models import ActionClass, ActivityEvent, TemporalPrecision

from .models import ConnectorRawRecord


CONNECTOR_EVENT_NAMESPACE = UUID("c374e36e-97f8-44ff-8b79-9248cb69e643")


def _signature(record_signature: str, event_type: str) -> str:
    return hashlib.sha256(f"{record_signature}:{event_type}".encode()).hexdigest()


def _event(
    record: ConnectorRawRecord, context: Mapping[str, Any], *, artifact_id: UUID,
    snapshot_id: UUID, locator_id: UUID, event_type: str, action: ActionClass,
    data_domain: str, object_type: str, object_id: str | None,
    object_value: Any, identifiers: dict[str, Any], relationships: dict[str, Any],
    parser_id: str,
) -> ActivityEvent:
    signature = _signature(record.record_signature, event_type)
    occurred = record.occurred_at
    subject = str(context.get("profile_id") or f"connector:{context['connector_instance_id']}")
    return ActivityEvent(
        event_id=uuid5(CONNECTOR_EVENT_NAMESPACE, signature), record_signature=signature,
        subject_id=subject, export_snapshot_id=snapshot_id, artifact_id=artifact_id,
        service=str(context.get("provider") or context.get("connector_key")),
        product=str(context.get("connector_key")), data_domain=data_domain,
        event_type=event_type, action_class=action, occurred_at=occurred,
        occurred_at_original=occurred.isoformat() if occurred else None,
        temporal_precision=TemporalPrecision.SECOND if occurred else TemporalPrecision.UNKNOWN,
        timezone=str(occurred.tzinfo) if occurred and occurred.tzinfo else None,
        timezone_evidence="source_timestamp" if occurred and occurred.tzinfo else None,
        object_type=object_type, object_id=object_id, object_value=object_value,
        identifiers=identifiers, relationships=relationships,
        epistemic_hints={"event_type": "observed", "occurred_at": "declared"},
        parser_id=parser_id, parser_version="1.0.0", source_locator_id=locator_id,
    )


def map_connector_events(
    record: ConnectorRawRecord, context: Mapping[str, Any], *, artifact_id: UUID,
    snapshot_id: UUID, locator_id: UUID,
) -> tuple[ActivityEvent, ...]:
    if record.data_class == "browser.visit":
        try:
            document = json.loads(record.payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ()
        return (_event(
            record, context, artifact_id=artifact_id, snapshot_id=snapshot_id,
            locator_id=locator_id, event_type="BROWSER_VISIT", action=ActionClass.VISITED,
            data_domain="browsing", object_type="url", object_id=str(document.get("visit_id") or "") or None,
            object_value={"url": document.get("url"), "transition_type": document.get("transition_type")},
            identifiers={"visit_id": document.get("visit_id"), "browser_profile_connector_id": document.get("browser_profile_connector_id")},
            relationships={"referring_visit_id": document.get("referring_visit_id")},
            parser_id="task5.browser-visit",
        ),)
    if record.data_class == "ai.conversation_turn":
        try:
            document = json.loads(record.payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ()
        role = str(document.get("role") or "unknown")
        action = ActionClass.CREATED if role == "user" else ActionClass.OTHER
        return (_event(
            record, context, artifact_id=artifact_id, snapshot_id=snapshot_id,
            locator_id=locator_id, event_type="AI_CONVERSATION_TURN", action=action,
            data_domain="ai_conversation", object_type="conversation_turn",
            object_id=str(document.get("turn_id") or "") or None,
            object_value={
                "role": role, "text": document.get("text"), "model": document.get("model"),
                "title": document.get("title"), "service": document.get("service"),
            },
            identifiers={
                "conversation_id": document.get("conversation_id"),
                "turn_id": document.get("turn_id"),
            }, relationships={"source_pointer": document.get("source_pointer")},
            parser_id="task5.ai-conversation-turn",
        ),)
    if record.data_class in {"filesystem.file", "photo.media"}:
        change = str(record.source_metadata.get("change_kind") or "observed")
        photo = record.data_class == "photo.media"
        return (_event(
            record, context, artifact_id=artifact_id, snapshot_id=snapshot_id,
            locator_id=locator_id,
            event_type=("MEDIA_FILE_" if photo else "FILE_") + change.upper(),
            action=ActionClass.CREATED if change == "created" else ActionClass.EDITED,
            data_domain="media" if photo else "filesystem",
            object_type="media_file" if photo else "file",
            object_id=str(record.source_metadata.get("content_sha256") or "") or None,
            object_value={
                "path": record.source_metadata.get("path"),
                "content_sha256": record.source_metadata.get("content_sha256"),
                "change_kind": change,
                "physical_presence_supported": False if photo else None,
                "semantic_project_meaning_supported": False,
            },
            identifiers={"root_id": record.source_metadata.get("root_id")},
            relationships={}, parser_id="task5.folder-observation",
        ),)
    if record.data_class == "filesystem.observation":
        try:
            document = json.loads(record.payload)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ()
        return (_event(
            record, context, artifact_id=artifact_id, snapshot_id=snapshot_id,
            locator_id=locator_id, event_type="FILE_REMOVED_OBSERVATION",
            action=ActionClass.OTHER, data_domain="filesystem",
            object_type="file_observation", object_id=str(document.get("path_key") or "") or None,
            object_value={
                "change_kind": "removed", "previous": document.get("previous"),
                "historical_evidence_erased": False,
            }, identifiers={"root_id": record.source_metadata.get("root_id")},
            relationships={}, parser_id="task5.folder-removal",
        ),)
    if record.data_class != "email.message":
        return ()
    return _email_events(record, context, artifact_id, snapshot_id, locator_id)


def _email_events(record, context, artifact_id, snapshot_id, locator_id) -> tuple[ActivityEvent, ...]:
    metadata = record.source_metadata
    direction = str(metadata.get("direction") or "unknown")
    headers: dict[str, Any] = {}
    if record.media_type.casefold().startswith("message/rfc822"):
        message = BytesParser(policy=policy.default).parsebytes(record.payload)
        headers = {key.casefold(): str(value) for key, value in message.items()}
    else:
        try:
            document = json.loads(record.payload)
            headers = {str(key).casefold(): value for key, value in document.get("headers", {}).items()}
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            return ()
    reply = bool(headers.get("in-reply-to") or headers.get("references"))
    event_type = "EMAIL_REPLIED" if reply else "EMAIL_SENT" if direction == "outbound" else "EMAIL_RECEIVED"
    message_id = str(headers.get("message-id") or metadata.get("message_id") or record.source_record_id)
    base = _event(
        record, context, artifact_id=artifact_id, snapshot_id=snapshot_id,
        locator_id=locator_id, event_type=event_type, action=ActionClass.COMMUNICATED,
        data_domain="email", object_type="email_message", object_id=message_id,
        object_value={
            "direction": direction, "subject": headers.get("subject"),
            "from": headers.get("from"), "to": headers.get("to"),
        },
        identifiers={"message_id": message_id, "mailbox": metadata.get("mailbox"), "uid": metadata.get("uid")},
        relationships={"in_reply_to": headers.get("in-reply-to"), "references": headers.get("references")},
        parser_id="task5.email-message",
    )
    events = [base]
    flags = {str(value).casefold() for value in metadata.get("flags", ())}
    if "\\seen" in flags and direction != "outbound":
        events.append(_event(
            record, context, artifact_id=artifact_id, snapshot_id=snapshot_id,
            locator_id=locator_id, event_type="EMAIL_OPENED_CANDIDATE", action=ActionClass.CONSUMED,
            data_domain="email", object_type="email_message", object_id=message_id,
            object_value={"direction": direction, "basis": "imap_seen_flag"},
            identifiers={"message_id": message_id}, relationships={},
            parser_id="task5.email-seen-candidate",
        ))
    return tuple(events)
