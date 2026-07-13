from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from ingestion.models import ActionClass, ActivityEvent, TemporalPrecision
from insights.ai_conversations import analyse_ai_conversations
from insights.search import analyse_search_events
from insights.signals import classify_event, conversation_turn_role
from insights.models import ConversationTurnRole, SignalClass


BASE = datetime(2025, 1, 1, tzinfo=timezone.utc)


def event(kind: str, *, at=BASE, action=ActionClass.OTHER, domain="email", service="fixture", value=None, relationships=None, identifiers=None):
    return ActivityEvent(event_id=uuid4(), record_signature="a" * 64, subject_id="subject", export_snapshot_id=uuid4(), artifact_id=uuid4(), service=service, data_domain=domain, event_type=kind, action_class=action, occurred_at=at, temporal_precision=TemporalPrecision.SECOND, object_value=value, relationships=relationships or {}, identifiers=identifiers or {}, parser_id="fixture", parser_version="1", source_locator_id=uuid4())


def test_newsletter_signal_hierarchy_is_deterministic():
    cases = [("newsletter_received", SignalClass.AMBIENT_EXPOSURE, False), ("newsletter_open", SignalClass.AMBIENT_EXPOSURE, False), ("link_click", SignalClass.ACTIVE_INVESTIGATION, True), ("replied", SignalClass.AMBIENT_EXPOSURE, False), ("unsubscribe", SignalClass.DISENGAGEMENT, False)]
    for kind, expected, contributes in cases:
        result = classify_event(event(kind))
        assert result.signal_class is expected and result.interest_contributing is contributes
    opened_received = classify_event(event("newsletter_open", relationships={"direction": "received"}))
    assert opened_received.signal_class is SignalClass.AMBIENT_EXPOSURE
    reliable_open = classify_event(event("newsletter_open", relationships={"open_evidence_reliable": True}))
    assert reliable_open.signal_class is SignalClass.PASSIVE_CONSUMPTION
    assert reliable_open.interest_contributing and reliable_open.weight == 0.25
    unreliable_open=classify_event(event("newsletter_open",relationships={"open_evidence_reliable":False}))
    assert unreliable_open.signal_class is SignalClass.AMBIENT_EXPOSURE
    assert unreliable_open.source_reliability < reliable_open.source_reliability


def test_reply_requires_outbound_or_user_authored_evidence():
    inbound = classify_event(event("replied", relationships={"direction": "inbound"}))
    outbound = classify_event(event("replied", relationships={"direction": "outbound"}))
    sent = classify_event(event("sent_reply"))
    authored = classify_event(event("replied", value={"role": "user"}))
    assert inbound.signal_class is SignalClass.AMBIENT_EXPOSURE and not inbound.interest_contributing
    assert all(result.signal_class is SignalClass.COMMUNICATION and result.interest_contributing for result in (outbound, sent, authored))


def test_creation_and_implementation_remain_distinct():
    assert classify_event(event("file_created", action=ActionClass.CREATED)).signal_class is SignalClass.CREATION
    assert classify_event(event("file_edited", action=ActionClass.EDITED)).signal_class is SignalClass.IMPLEMENTATION


def test_assistant_text_is_exposure_but_user_turn_is_behavioural():
    assistant = classify_event(event("assistant_generated", domain="ai_conversation", value={"role": "assistant", "text": "robotics"}))
    user = classify_event(event("user_authored", domain="ai_conversation", value={"role": "user", "text": "robotics"}))
    assert assistant.signal_class is SignalClass.AMBIENT_EXPOSURE and not assistant.interest_contributing
    assert user.signal_class is SignalClass.ACTIVE_INVESTIGATION and user.interest_contributing


def test_explicit_canonical_ai_role_is_authoritative_for_every_role():
    cases = {
        "user": ConversationTurnRole.USER_AUTHORED_TURN,
        "assistant": ConversationTurnRole.ASSISTANT_GENERATED_TURN,
        "system": ConversationTurnRole.SYSTEM_TURN,
        "tool": ConversationTurnRole.TOOL_TURN,
        "unknown": ConversationTurnRole.UNKNOWN,
    }
    for role, expected in cases.items():
        conflicting = event(
            "assistant_generated",
            domain="ai_conversation",
            value={"role": role},
            relationships={"message_type": "assistant", "author": "assistant"},
            identifiers={"source_role": "assistant"},
        )
        assert conversation_turn_role(conflicting) is expected

    explicit_user = classify_event(event(
        "assistant_generated",
        domain="ai_conversation",
        value={"role": "user"},
        relationships={"message_type": "assistant"},
    ))
    assert explicit_user.signal_class is SignalClass.ACTIVE_INVESTIGATION
    assert explicit_user.interest_contributing


def test_ai_role_heuristics_are_only_a_fallback_when_role_is_absent():
    heuristic = event("user_authored", domain="ai_conversation", value={"text": "question"})
    explicit_unknown = event("user_authored", domain="ai_conversation", value={"role": "unknown"})
    assert conversation_turn_role(heuristic) is ConversationTurnRole.USER_AUTHORED_TURN
    assert conversation_turn_role(explicit_unknown) is ConversationTurnRole.UNKNOWN


def test_single_search_remains_abandoned_one_off_and_raw_query_is_not_summarised():
    query = "private medical question unique phrase"
    insight = analyse_search_events([event("query", action=ActionClass.SEARCHED, domain="search", value={"query": query})])
    assert insight.abandoned_one_offs == 1 and not insight.episodes and not insight.recurring_queries
    assert query not in insight.model_dump_json()


def test_cross_source_refinement_episode_and_search_to_project_transition():
    first = event("query", action=ActionClass.SEARCHED, domain="search", service="browser", value={"query": "build robot"}, relationships={"topic_labels": ["robotics"], "domain": "a.example"})
    second = event("query", at=BASE + timedelta(minutes=10), action=ActionClass.SEARCHED, domain="search", service="search-engine", value={"query": "build robot motor control"}, relationships={"topic_labels": ["robotics"], "domain": "b.example", "refines_event_id": str(first.event_id)})
    project = event("file_created", at=BASE + timedelta(days=1), action=ActionClass.CREATED, domain="documents", relationships={"topic_labels": ["robotics"], "source_event_ids": [str(first.event_id)]})
    insight = analyse_search_events([first, second, project])
    assert len(insight.episodes) == 1
    episode = insight.episodes[0]
    assert episode.cross_source_count == 2 and episode.refinement_depth == 1 and episode.project_transition
    assert insight.refinement_chains[0]["depth"] == 1


def test_temporal_proximity_across_sources_does_not_join_unrelated_searches():
    first = event("query", action=ActionClass.SEARCHED, domain="search", service="browser", value={"query": "garden roses"})
    second = event("query", at=BASE + timedelta(minutes=5), action=ActionClass.SEARCHED, domain="search", service="search-engine", value={"query": "python database"})
    insight = analyse_search_events([first, second])
    assert not insight.episodes and insight.abandoned_one_offs == 2


def test_search_revisitation_is_separate_from_same_session_repetition():
    rows=[
        event("query",action=ActionClass.SEARCHED,domain="search",value={"query":"robot motor"}),
        event("query",at=BASE+timedelta(hours=1),action=ActionClass.SEARCHED,domain="search",value={"query":"robot motor"}),
        event("query",at=BASE+timedelta(days=3),action=ActionClass.SEARCHED,domain="search",value={"query":"robot motor"}),
    ]
    recurring=analyse_search_events(rows).recurring_queries[0]
    assert recurring["count"]==3
    assert recurring["revisit_count"]==1


def test_ai_roles_sessions_follow_up_recurrence_and_project_linkage():
    events = [
        event("user_authored", domain="ai_conversation", value={"role": "user", "text": "secret one"}, identifiers={"session_id": "s1"}, relationships={"topic_labels": ["robotics"]}),
        event("assistant_generated", at=BASE + timedelta(minutes=1), domain="ai_conversation", value={"role": "assistant", "text": "secret response"}, identifiers={"session_id": "s1"}, relationships={"topic_labels": ["unfollowed-assistant-topic"]}),
        event("user_authored", at=BASE + timedelta(minutes=2), domain="ai_conversation", value={"role": "user", "text": "secret refinement"}, identifiers={"session_id": "s1"}, relationships={"topic_labels": ["robotics"], "project_id": "p1"}),
        event("user_authored", at=BASE + timedelta(days=8), domain="ai_conversation", value={"role": "user", "text": "secret return"}, identifiers={"session_id": "s2"}, relationships={"topic_labels": ["robotics"]}),
    ]
    insight = analyse_ai_conversations(events)
    assert insight.session_count == 2 and insight.user_turn_count == 3 and insight.assistant_turn_count == 1
    assert insight.maximum_follow_up_depth == 1 and insight.project_linked_session_ids == ("s1",)
    assert insight.calculated_features["session_durations_seconds"]["s1"] == 120.0
    assert insight.recurrent_questions[0]["topic_label"] == "robotics"
    assert insight.refinement_chains[0]["stage_sequence"] == ("initial_question", "related_project_activity")
    assert all(item["topic_label"] != "unfollowed-assistant-topic" for item in insight.user_originated_topics)
    assert "secret" not in insight.model_dump_json()


def test_ai_refinement_chain_preserves_question_architecture_implementation_order():
    rows=[
        event("user_authored",domain="ai_conversation",value={"role":"user","text":"What is a robot?"},identifiers={"session_id":"chain"}),
        event("user_authored",at=BASE+timedelta(minutes=1),domain="ai_conversation",value={"role":"user","text":"How does the motor work technically?"},identifiers={"session_id":"chain"}),
        event("user_authored",at=BASE+timedelta(minutes=2),domain="ai_conversation",value={"role":"user","text":"Design the system architecture and component interface"},identifiers={"session_id":"chain"}),
        event("user_authored",at=BASE+timedelta(minutes=3),domain="ai_conversation",value={"role":"user","text":"Implement and debug the code"},identifiers={"session_id":"chain"}),
        event("user_authored",at=BASE+timedelta(minutes=4),domain="ai_conversation",value={"role":"user","text":"Link this to my project"},identifiers={"session_id":"chain"},relationships={"project_id":"p1"}),
    ]
    chain=analyse_ai_conversations(rows).refinement_chains[0]
    assert chain["stage_sequence"] == (
        "initial_question","technical_follow_up","architecture_follow_up",
        "implementation_follow_up","related_project_activity",
    )
