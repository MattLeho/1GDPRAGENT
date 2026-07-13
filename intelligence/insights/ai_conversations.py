"""Deterministic AI-conversation semantics derived from authored turn evidence."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import re
from uuid import NAMESPACE_URL, UUID, uuid5

from ingestion.models import ActivityEvent

from .models import AIConversationInsight, ConversationTurnRole, EvidenceKind, InsightEvidenceRef
from .signals import conversation_turn_role


DETECTOR_ID = "task4.ai_conversations.deterministic"
DETECTOR_VERSION = "1"


def analyse_ai_conversations(events: list[ActivityEvent] | tuple[ActivityEvent, ...], *, analysis_run_id: UUID | None = None) -> AIConversationInsight:
    turns = sorted((event for event in events if _is_ai_turn(event) and event.occurred_at), key=lambda event: event.occurred_at)  # type: ignore[arg-type]
    sessions: dict[str, list[ActivityEvent]] = defaultdict(list)
    for event in turns:
        sessions[_session_id(event)].append(event)
    user_turns = [event for event in turns if conversation_turn_role(event) is ConversationTurnRole.USER_AUTHORED_TURN]
    assistant_turns = [event for event in turns if conversation_turn_role(event) is ConversationTurnRole.ASSISTANT_GENERATED_TURN]
    topic_sessions: dict[str, set[str]] = defaultdict(set)
    topic_events: dict[str, set[UUID]] = defaultdict(set)
    for event in user_turns:
        for topic in _topics(event):
            topic_sessions[topic].add(_session_id(event)); topic_events[topic].add(event.event_id)
    originated = tuple({"topic_label": topic, "user_turn_count": len(topic_events[topic]), "session_count": len(session_ids)} for topic, session_ids in sorted(topic_sessions.items()))
    sustained = tuple(item for item in originated if int(item["user_turn_count"]) >= 2)
    recurrent = tuple(item for item in originated if int(item["session_count"]) >= 2)
    linked = tuple(sorted(session_id for session_id, group in sessions.items() if any(_project_linked(event) for event in group)))
    refinement_chains = tuple(
        chain for session_id, group in sorted(sessions.items())
        if (chain := _refinement_chain(session_id, group))["user_turn_count"] > 0
    )
    evidence = tuple(_evidence(event, conversation_turn_role(event)) for event in turns)
    services = tuple(sorted({str(event.service or event.product) for event in turns if event.service or event.product}))
    max_depth = max((_follow_up_depth(group) for group in sessions.values()), default=0)
    durations = {
        session_id: max(0.0, (group[-1].occurred_at - group[0].occurred_at).total_seconds())
        for session_id, group in sessions.items() if group[0].occurred_at and group[-1].occurred_at
    }
    identity = ",".join(str(event.event_id) for event in turns)
    return AIConversationInsight(
        insight_id=uuid5(NAMESPACE_URL, f"{DETECTOR_ID}:{identity}"), detector_id=DETECTOR_ID,
        detector_version=DETECTOR_VERSION, analysis_run_id=analysis_run_id,
        user_originated_topics=originated, sustained_clusters=sustained, recurrent_questions=recurrent,
        refinement_chains=refinement_chains,
        services=services, session_count=len(sessions), user_turn_count=len(user_turns),
        assistant_turn_count=len(assistant_turns), maximum_follow_up_depth=max_depth,
        project_linked_session_ids=linked, evidence=evidence,
        calculated_features={
            "unknown_role_turn_count": sum(conversation_turn_role(event) is ConversationTurnRole.UNKNOWN for event in turns),
            "session_durations_seconds": durations,
            "question_refinement_count":sum(max(0, int(item["user_turn_count"])-1) for item in refinement_chains),
        },
    )


def _is_ai_turn(event: ActivityEvent) -> bool:
    domain = event.data_domain.casefold()
    return domain in {"ai", "ai_conversation", "conversation"} or conversation_turn_role(event) is not ConversationTurnRole.UNKNOWN


def _session_id(event: ActivityEvent) -> str:
    value = event.identifiers.get("session_id") or event.relationships.get("session_id")
    if isinstance(event.object_value, dict):
        value = value or event.object_value.get("session_id")
    return str(value or f"event:{event.event_id}")


def _topics(event: ActivityEvent) -> tuple[str, ...]:
    value = event.relationships.get("topic_labels") or event.relationships.get("topics") or []
    if isinstance(value, str): value = [value]
    return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))


def _project_linked(event: ActivityEvent) -> bool:
    return bool(event.relationships.get("project_id") or event.relationships.get("project_event_ids"))


def _follow_up_depth(events: list[ActivityEvent]) -> int:
    user_positions = [index for index, event in enumerate(events) if conversation_turn_role(event) is ConversationTurnRole.USER_AUTHORED_TURN]
    return max(0, len(user_positions) - 1)


def _turn_text(event: ActivityEvent) -> str:
    if isinstance(event.object_value, str):
        return event.object_value
    if isinstance(event.object_value, dict):
        return str(event.object_value.get("text") or event.object_value.get("content") or "")
    return ""


def _refinement_stage(event: ActivityEvent, position: int) -> str:
    explicit = str(event.relationships.get("refinement_stage") or "").casefold()
    if explicit in {"initial_question","technical_follow_up","architecture_follow_up","implementation_follow_up","related_project_activity"}:
        return explicit
    if _project_linked(event):
        return "related_project_activity"
    text = _turn_text(event).casefold()
    tokens = set(re.findall(r"[a-z0-9]+", text))
    if event.action_class.value in {"EDITED","CODED","CREATED","PUBLISHED"} or tokens & {"implement","implementation","code","build","debug","deploy"}:
        return "implementation_follow_up"
    if tokens & {"architecture","architect","design","component","interface","pipeline","schema"}:
        return "architecture_follow_up"
    if position > 0 or tokens & {"how","why","error","configure","technical","detail"}:
        return "technical_follow_up"
    return "initial_question"


def _refinement_chain(session_id: str, events: list[ActivityEvent]) -> dict[str, object]:
    user_events = [event for event in events if conversation_turn_role(event) is ConversationTurnRole.USER_AUTHORED_TURN]
    stages = []
    for index, event in enumerate(user_events):
        stage = _refinement_stage(event, index)
        if not stages or stages[-1] != stage:
            stages.append(stage)
    return {
        "session_id":session_id,
        "user_turn_count":len(user_events),
        "stage_sequence":tuple(stages),
        "reached_project_activity":"related_project_activity" in stages,
        "event_ids":tuple(str(event.event_id) for event in user_events),
    }


def _evidence(event: ActivityEvent, role: ConversationTurnRole) -> InsightEvidenceRef:
    evidence_role = "exposure" if role is ConversationTurnRole.ASSISTANT_GENERATED_TURN else "supporting"
    return InsightEvidenceRef(kind=EvidenceKind.ACTIVITY_EVENT, ref_id=event.event_id, role=evidence_role, occurred_at=event.occurred_at, artifact_id=event.artifact_id, locator_id=event.source_locator_id, label=role.value)


def privacy_safe_text_fingerprint(text: str) -> str:
    """Public helper for drill-down references; it never returns source text."""
    return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()[:16]


# American-spelling aliases for API/service callers.
analyze_ai_conversations = analyse_ai_conversations
