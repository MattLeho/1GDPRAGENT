from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import UUID, uuid5

import pytest
from pydantic import ValidationError

from ingestion.models import ActionClass, ActivityEvent
from temporal.engagement import ACTION_DIMENSION, build_engagement_profile, build_engagement_profiles
from temporal.interactions import build_interaction_states, counterpart_hash
from temporal.models import InteractionState, TopicAssignment
from temporal.routines import build_routine_distributions, build_routine_drift


_NAMESPACE = UUID("ccf6cf50-a302-4db8-ac66-ad94239cfb33")


def _id(name: str) -> UUID:
    return uuid5(_NAMESPACE, name)


def _event(
    name: str,
    *,
    when: datetime | None,
    action: ActionClass = ActionClass.OTHER,
    subject: str = "person-1",
    service: str | None = "Fixture",
    event_type: str = "fixture.event",
    relationships: dict | None = None,
) -> ActivityEvent:
    event_id = _id(name)
    return ActivityEvent(
        event_id=event_id,
        record_signature=hashlib.sha256(name.encode()).hexdigest(),
        subject_id=subject,
        export_snapshot_id=_id(f"snapshot:{name}"),
        artifact_id=_id(f"artifact:{name}"),
        service=service,
        data_domain="synthetic_history",
        event_type=event_type,
        action_class=action,
        occurred_at=when,
        relationships=relationships or {},
        parser_id="synthetic.history",
        parser_version="1",
        source_locator_id=_id(f"locator:{name}"),
    )


def test_engagement_profile_counts_only_transparent_canonical_action_mappings():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    actions = (
        ActionClass.CONSUMED, ActionClass.VISITED, ActionClass.PURCHASED,
        ActionClass.SEARCHED, ActionClass.CREATED, ActionClass.PUBLISHED,
        ActionClass.EDITED, ActionClass.CODED, ActionClass.COMMUNICATED,
        ActionClass.AUTHENTICATED, ActionClass.OTHER,
    )
    events = tuple(
        _event(f"engagement-{index}", when=start + timedelta(hours=index), action=action)
        for index, action in enumerate(actions)
    )

    profile = build_engagement_profile(
        (*events, events[0]), subject_id="person-1",
        window_start=start, window_end=start + timedelta(days=1),
    )
    assert profile is not None
    assert profile.model_dump(exclude={"evidence_event_ids", "subject_id", "window_start", "window_end"}) == {
        "consumption": 3.0,
        "investigation": 1.0,
        "creation": 2.0,
        "implementation": 2.0,
        "communication": 1.0,
    }
    assert len(profile.evidence_event_ids) == 9
    assert ActionClass.AUTHENTICATED not in ACTION_DIMENSION
    assert ActionClass.OTHER not in ACTION_DIMENSION
    assert profile == build_engagement_profile(
        reversed(events), subject_id="person-1",
        window_start=start, window_end=start + timedelta(days=1),
    )


def test_engagement_preserves_unknown_and_empty_windows_without_fabricated_evidence():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    unknown_time = _event("unknown-time", when=None, action=ActionClass.COMMUNICATED)
    outside = _event("outside", when=start + timedelta(days=2), action=ActionClass.CREATED)
    assert build_engagement_profile(
        (unknown_time, outside), subject_id="person-1",
        window_start=start, window_end=start + timedelta(days=1),
    ) is None
    assert build_engagement_profiles(
        (unknown_time, outside), window_start=start, window_end=start + timedelta(days=1),
    ) == ()
    with pytest.raises(ValueError, match="window_end"):
        build_engagement_profile((), subject_id="person-1", window_start=start, window_end=start)


def test_routines_cover_hour_day_service_event_and_evidence_linked_topic():
    start = datetime(2024, 1, 1, tzinfo=timezone.utc)  # Monday
    first = _event(
        "routine-first", when=start + timedelta(hours=9), service="Search",
        event_type="query.performed", action=ActionClass.SEARCHED,
    )
    second = _event(
        "routine-second", when=start + timedelta(days=1, hours=21), service=None,
        event_type="video.viewed", action=ActionClass.CONSUMED,
    )
    assignment = TopicAssignment(
        topic_id="privacy", topic_path=("technology", "privacy"),
        source_event_ids=(first.event_id,), assignment_method="synthetic_fixture",
        assignment_version="1", confidence=1.0,
    )
    distributions = build_routine_distributions(
        (second, first, first), window_start=start, window_end=start + timedelta(days=7),
        topic_assignments=(assignment,),
    )

    assert {item.dimension for item in distributions} == {"hour", "day", "service", "event", "topic"}
    by_key = {(item.dimension, item.bucket): item for item in distributions}
    assert by_key[("hour", "09")].event_count == 1
    assert by_key[("hour", "09")].proportion == 0.5
    assert by_key[("day", "Monday")].evidence_event_ids == (first.event_id,)
    assert by_key[("service", "UNKNOWN")].evidence_event_ids == (second.event_id,)
    assert by_key[("event", "query.performed")].proportion == 0.5
    assert by_key[("topic", "privacy")].evidence_event_ids == (first.event_id,)
    assert by_key[("topic", "UNKNOWN")].evidence_event_ids == (second.event_id,)
    assert distributions == build_routine_distributions(
        reversed((first, second)), window_start=start, window_end=start + timedelta(days=7),
        topic_assignments=(assignment,),
    )


def test_routine_drift_uses_total_variation_without_semantic_labels():
    baseline_start = datetime(2024, 1, 1, tzinfo=timezone.utc)
    current_start = datetime(2024, 2, 1, tzinfo=timezone.utc)
    baseline_event = _event(
        "baseline", when=baseline_start + timedelta(hours=8), service="Search",
        event_type="query", action=ActionClass.SEARCHED,
    )
    current_event = _event(
        "current", when=current_start + timedelta(hours=20), service="Editor",
        event_type="edit", action=ActionClass.EDITED,
    )
    baseline = build_routine_distributions(
        (baseline_event,), window_start=baseline_start, window_end=baseline_start + timedelta(days=7),
    )
    current = build_routine_distributions(
        (current_event,), window_start=current_start, window_end=current_start + timedelta(days=7),
    )
    drift = build_routine_drift(baseline, current)
    assert {item.dimension for item in drift} == {"hour", "day", "service", "event", "topic"}
    assert next(item for item in drift if item.dimension == "hour").total_variation_distance == 1.0
    assert next(item for item in drift if item.dimension == "service").current_distribution == {"Editor": 1.0}
    # Both histories lack an assigned topic, so their explicit UNKNOWN distribution did not drift.
    assert next(item for item in drift if item.dimension == "topic").total_variation_distance == 0.0
    payload = json.dumps([item.model_dump(mode="json") for item in drift], sort_keys=True)
    assert all(label not in payload.lower() for label in ("personality", "friend", "partner", "colleague"))


def test_interaction_state_is_grounded_in_explicit_direction_and_observed_timing():
    start = datetime(2024, 1, 1, 9, tzinfo=timezone.utc)
    target = "Alice@Example.Test"
    events = (
        _event("in-1", when=start, service="Mail", relationships={"received_from": target}),
        _event("out-1", when=start + timedelta(minutes=5), service="Mail", relationships={"sent_to": target.lower()}),
        _event(
            "in-2", when=start + timedelta(days=1), service="Chat",
            relationships={"party": {"action": "RECEIVED_FROM", "target": f" {target} "}},
        ),
        _event(
            "out-2", when=start + timedelta(days=1, minutes=15), service="Chat",
            relationships={"party": {"relationship_action": "SENT_TO", "identifier": target}},
        ),
        _event("unsupported-role", when=start, relationships={"friend": target, "partner": target}),
    )
    states = build_interaction_states((*reversed(events), events[0]))
    assert len(states) == 1
    state = states[0]
    assert state.counterpart_hash == counterpart_hash(target.lower())
    assert state.inbound == 2 and state.outbound == 2
    assert state.reciprocity_ratio == 1.0
    assert state.response_interval_seconds == 600.0
    assert state.active_days == 2 and state.service_count == 2
    assert state.burstiness is not None and -1 <= state.burstiness <= 1
    assert len(state.evidence_event_ids) == 4
    assert state.relationship_label is None and state.personality_label is None
    assert states == build_interaction_states(events)


def test_interaction_unknown_timing_stays_unknown_and_labels_are_mechanically_forbidden():
    event = _event("untimed", when=None, relationships={"sent_to": "counterpart"})
    state = build_interaction_states((event,))[0]
    assert state.outbound == 1 and state.inbound == 0
    assert state.reciprocity_ratio == 0.0
    assert state.response_interval_seconds is None
    assert state.active_days == 0 and state.burstiness is None
    with pytest.raises(ValidationError):
        InteractionState(**{**state.model_dump(), "relationship_label": "FRIEND"})

