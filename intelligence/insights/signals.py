"""Deterministic exposure and engagement classification for ActivityEvents."""
from __future__ import annotations

from dataclasses import dataclass

from ingestion.models import ActionClass, ActivityEvent

from .models import ConversationTurnRole, SignalClass


@dataclass(frozen=True)
class ClassifiedSignal:
    event: ActivityEvent
    signal_class: SignalClass
    interest_contributing: bool
    weight: float
    reason: str
    source_reliability: float = 1.0
    source_rule: str = "deterministic-default"


def conversation_turn_role(event: ActivityEvent) -> ConversationTurnRole:
    canonical_role = _canonical_conversation_role(event)
    if canonical_role is not None:
        return canonical_role

    values = _semantic_values(event)
    if _contains(values, "assistant", "assistant_generated", "model_response"):
        return ConversationTurnRole.ASSISTANT_GENERATED_TURN
    if _contains(values, "user", "user_authored", "human_prompt"):
        return ConversationTurnRole.USER_AUTHORED_TURN
    if _contains(values, "system", "system_prompt"):
        return ConversationTurnRole.SYSTEM_TURN
    if _contains(values, "tool", "function_call", "tool_result"):
        return ConversationTurnRole.TOOL_TURN
    return ConversationTurnRole.UNKNOWN


def classify_event(event: ActivityEvent) -> ClassifiedSignal:
    values = _semantic_values(event)
    role = conversation_turn_role(event)

    if _contains(values, "unsubscribe", "unsubscribed", "opt_out"):
        return ClassifiedSignal(event, SignalClass.DISENGAGEMENT, False, 0.0, "explicit disengagement action",0.95,"explicit-user-action")
    if _contains(values, "reply", "replied", "sent_reply", "reply_sent"):
        direction_values = _direction_values(event)
        if _contains(direction_values, "inbound", "incoming", "received"):
            return ClassifiedSignal(event, SignalClass.AMBIENT_EXPOSURE, False, 0.0, "inbound reply is received exposure",0.9,"received-message")
        authored = role is ConversationTurnRole.USER_AUTHORED_TURN or _contains(
            direction_values,
            "outbound",
            "outgoing",
            "sent",
            "sent_reply",
            "reply_sent",
            "outbound_reply",
            "user_authored",
            "user_authored_reply",
        )
        if authored:
            return ClassifiedSignal(event, SignalClass.COMMUNICATION, True, 1.0, "outbound or user-authored reply",0.95,"authored-message")
        return ClassifiedSignal(event, SignalClass.AMBIENT_EXPOSURE, False, 0.0, "reply without authorship evidence remains exposure",0.5,"unqualified-reply")
    if role is ConversationTurnRole.ASSISTANT_GENERATED_TURN:
        return ClassifiedSignal(event, SignalClass.AMBIENT_EXPOSURE, False, 0.0, "assistant-generated text is exposure",1.0,"conversation-role")
    if role is ConversationTurnRole.USER_AUTHORED_TURN:
        return ClassifiedSignal(event, SignalClass.ACTIVE_INVESTIGATION, True, 1.0, "user-authored AI turn",1.0,"conversation-role")
    if _contains(values, "click", "clicked", "link_click"):
        return ClassifiedSignal(event, SignalClass.ACTIVE_INVESTIGATION, True, 0.8, "click is active engagement",0.9,"explicit-click")
    if _contains(values, "open", "opened", "email_open", "newsletter_open"):
        reliable = event.relationships.get("open_evidence_reliable") is True
        if reliable:
            return ClassifiedSignal(event, SignalClass.PASSIVE_CONSUMPTION, True, 0.25, "reliable open is weak passive consumption",0.7,"source-open-signal")
        return ClassifiedSignal(event, SignalClass.AMBIENT_EXPOSURE, False, 0.0, "unreliable open signal remains exposure",0.25,"unreliable-open-signal")
    if _contains(values, "received", "delivered", "newsletter_received", "email_received"):
        return ClassifiedSignal(event, SignalClass.AMBIENT_EXPOSURE, False, 0.0, "delivery is ambient exposure",0.9,"delivery-record")
    if event.action_class is ActionClass.SEARCHED:
        return ClassifiedSignal(event, SignalClass.ACTIVE_INVESTIGATION, True, 0.5, "search is active but may be one-off",0.9,"authored-search")
    if event.action_class in {ActionClass.CREATED, ActionClass.PUBLISHED}:
        return ClassifiedSignal(event, SignalClass.CREATION, True, 1.0, "authored or created output")
    if event.action_class in {ActionClass.EDITED, ActionClass.CODED} or _contains(values, "implemented", "deployed"):
        return ClassifiedSignal(event, SignalClass.IMPLEMENTATION, True, 1.0, "implementation activity")
    if event.action_class is ActionClass.COMMUNICATED:
        return ClassifiedSignal(event, SignalClass.COMMUNICATION, True, 1.0, "communication activity")
    if event.action_class in {ActionClass.CONSUMED, ActionClass.VISITED}:
        return ClassifiedSignal(event, SignalClass.PASSIVE_CONSUMPTION, True, 0.25, "consumption activity")
    return ClassifiedSignal(event, SignalClass.UNKNOWN, False, 0.0, "no deterministic signal rule matched")


def classify_events(events: list[ActivityEvent] | tuple[ActivityEvent, ...]) -> tuple[ClassifiedSignal, ...]:
    return tuple(classify_event(event) for event in events)


def _semantic_values(event: ActivityEvent) -> tuple[str, ...]:
    values: list[object] = [event.event_type, event.data_domain, event.object_type]
    for mapping in (event.identifiers, event.relationships):
        values.extend(mapping.values())
    if isinstance(event.object_value, dict):
        for key in ("role", "direction", "action", "event_type", "message_type"):
            values.append(event.object_value.get(key))
    return tuple(str(value).strip().casefold().replace("-", "_").replace(" ", "_") for value in values if value is not None)


def _canonical_conversation_role(event: ActivityEvent) -> ConversationTurnRole | None:
    """Resolve the canonical turn role without allowing metadata to overrule it.

    ``object_value.role`` is the normalised canonical field.  When the field is
    present, even an explicit ``unknown`` (or an unsupported value) is
    authoritative.  Event-type and metadata heuristics are only used when the
    canonical field is absent.
    """
    if not isinstance(event.object_value, dict) or "role" not in event.object_value:
        return None
    value = str(event.object_value.get("role") or "unknown").strip().casefold().replace("-", "_").replace(" ", "_")
    return {
        "user": ConversationTurnRole.USER_AUTHORED_TURN,
        "assistant": ConversationTurnRole.ASSISTANT_GENERATED_TURN,
        "system": ConversationTurnRole.SYSTEM_TURN,
        "tool": ConversationTurnRole.TOOL_TURN,
        "unknown": ConversationTurnRole.UNKNOWN,
    }.get(value, ConversationTurnRole.UNKNOWN)


def _direction_values(event: ActivityEvent) -> tuple[str, ...]:
    values: list[object] = [event.event_type]
    for mapping in (event.relationships, event.object_value if isinstance(event.object_value, dict) else {}):
        for key in ("direction", "action", "message_type"):
            if key in mapping:
                values.append(mapping[key])
    return tuple(str(value).strip().casefold().replace("-", "_").replace(" ", "_") for value in values if value is not None)


def _contains(values: tuple[str, ...], *needles: str) -> bool:
    return any(value == needle or value.endswith(f"_{needle}") for value in values for needle in needles)
