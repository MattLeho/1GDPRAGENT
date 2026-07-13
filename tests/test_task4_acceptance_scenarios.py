"""Task 4 synthetic acceptance scenarios from Wave 6 of the plan.

These fixtures exercise the frozen Personal Insights contracts rather than
re-stating implementation details.  Scenario 18 delegates to the dedicated
database-backed evidence trace test so the acceptance gate proves mechanical
locator resolution all the way back to source bytes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from ingestion.models import ActionClass, ActivityEvent, TemporalPrecision
from insights.ai_conversations import analyse_ai_conversations
from insights.context import ExposureObservation, correlate_change
from insights.media import LocationObservation, MediaOriginResult, create_location_candidate
from insights.models import (
    ChangeInsight,
    CorrelationStatus,
    EvidenceKind,
    ExternalContextEvent,
    InsightEvidenceRef,
    LocationBasis,
    LocationEvidenceClass,
    MediaOrigin,
    SignalClass,
)
from insights.search import analyse_search_events
from insights.service import _interest_views
from insights.signals import classify_event, classify_events
from temporal.interest import aggregate_interest_states
from temporal.models import TopicAssignment
from test_task1_database_integration import migrated_database
from test_task4_evidence_trace import (
    test_every_insight_evidence_link_resolves_to_source as _assert_evidence_trace_resolves,
)


UTC = timezone.utc
START = datetime(2025, 1, 1, tzinfo=UTC)
SUBJECT = "task4-acceptance-subject"


def _event(
    kind: str,
    *,
    at: datetime = START,
    action: ActionClass = ActionClass.OTHER,
    domain: str = "fixture",
    service: str = "fixture",
    topic: str | None = None,
    text: str | None = None,
    role: str | None = None,
    session_id: str | None = None,
    relationships: dict | None = None,
) -> ActivityEvent:
    event_id = uuid4()
    links = dict(relationships or {})
    if topic:
        links["topic_labels"] = [topic]
    value = {"text": text or kind}
    if action is ActionClass.SEARCHED:
        value = {"query": text or kind}
    if role:
        value["role"] = role
    return ActivityEvent(
        event_id=event_id,
        record_signature=event_id.hex * 2,
        subject_id=SUBJECT,
        export_snapshot_id=uuid4(),
        artifact_id=uuid4(),
        service=service,
        data_domain=domain,
        event_type=kind,
        action_class=action,
        occurred_at=at,
        temporal_precision=TemporalPrecision.SECOND,
        object_value=value,
        relationships=links,
        identifiers={"session_id": session_id} if session_id else {},
        parser_id="task4-acceptance-fixture",
        parser_version="1",
        source_locator_id=uuid4(),
    )


def _assignments(events: tuple[ActivityEvent, ...], topic: str) -> tuple[TopicAssignment, ...]:
    return (
        TopicAssignment(
            topic_id=topic,
            topic_path=(topic,),
            source_event_ids=tuple(event.event_id for event in events),
            assignment_method="acceptance-fixture",
            assignment_version="1",
            confidence=1.0,
        ),
    )


def _interest_states(
    events: tuple[ActivityEvent, ...],
    topic: str,
    *,
    search_episode_ids: set[UUID] | None = None,
    prior_topic_ids: set[str] | None = None,
):
    return _interest_views(
        subject_id=SUBJECT,
        events=events,
        signals=classify_events(events),
        assignments=_assignments(events, topic),
        search_episode_ids=search_episode_ids or set(),
        start=min(event.occurred_at for event in events if event.occurred_at) - timedelta(seconds=1),
        end=max(event.occurred_at for event in events if event.occurred_at) + timedelta(days=1),
        baseline_events=(),
        prior_topic_ids=prior_topic_ids or set(),
        analysis_run_id=uuid4(),
    )


def _change(topic: str = "robotics") -> ChangeInsight:
    return ChangeInsight(
        insight_id=uuid4(),
        detector_id="acceptance.change",
        detector_version="1",
        change_type="REGIME_SHIFT",
        state_key=topic,
        detected_at=START,
        magnitude=0.75,
    )


def _external(topic: str = "robotics", *, title: str | None = None) -> ExternalContextEvent:
    return ExternalContextEvent(
        id=uuid4(),
        title=title or f"{topic} platform release",
        event_type="product_release",
        occurred_at=START - timedelta(days=2),
        topics=(topic,),
        ingested_at=START + timedelta(days=10),
    )


def _exposure(
    kind: str,
    *,
    topic: str = "robotics",
    direct_statement: bool = False,
    at: datetime | None = None,
) -> ExposureObservation:
    evidence_kind = EvidenceKind.ACTIVITY_EVENT
    return ExposureObservation(
        evidence=InsightEvidenceRef(
            kind=evidence_kind,
            ref_id=uuid4(),
            role="user_confirmation" if direct_statement else "supporting",
            occurred_at=at or START - timedelta(days=5),
            label=kind,
        ),
        occurred_at=at or START - timedelta(days=5),
        topics=(topic,),
        text=f"user {kind} {topic} platform release",
        direct_user_statement=direct_statement,
    )


def _origin(value: MediaOrigin) -> MediaOriginResult:
    return MediaOriginResult(value, 0.95, {
        "fixture": "task4-acceptance",
        "camera_origin_corroborated": value is MediaOrigin.CAMERA_ORIGIN,
    })


def _location(
    basis: LocationBasis,
    *,
    place: str,
    gps: bool,
    credible_time: bool,
) -> LocationObservation:
    return LocationObservation(
        basis=basis,
        evidence_locator_id=uuid4(),
        occurred_at=START,
        temporal_precision="SECOND",
        lat=51.5246 if gps else None,
        lon=-0.1340 if gps else None,
        place_label=place,
        confidence=0.9,
        credible_original_capture_time=credible_time,
    )


def test_scenario_01_weekly_newsletter_for_three_years_never_engaged_is_only_ambient_exposure():
    newsletters = tuple(
        _event("newsletter_received", at=START + timedelta(weeks=index), domain="email", topic="gardening")
        for index in range(157)
    )
    signals = classify_events(newsletters)
    assert {signal.signal_class for signal in signals} == {SignalClass.AMBIENT_EXPOSURE}
    assert all(not signal.interest_contributing and signal.weight == 0 for signal in signals)
    assert _interest_states(newsletters, "gardening") == ()


def test_scenario_02_newsletter_clicked_repeatedly_contributes_active_interest():
    clicks = tuple(
        _event("link_click", at=START + timedelta(weeks=index), domain="email", topic="gardening")
        for index in range(6)
    )
    signals = classify_events(clicks)
    states = _interest_states(clicks, "gardening")
    assert all(signal.signal_class is SignalClass.ACTIVE_INVESTIGATION for signal in signals)
    assert len(states) == 1 and states[0].topic_id == "gardening"
    assert states[0].calculated_features["signal_weight"] == pytest.approx(0.8)


def test_scenario_03_assistant_mentions_topic_without_user_follow_up_is_exposure_not_interest():
    assistant = _event(
        "assistant_generated",
        domain="ai_conversation",
        topic="robotics",
        role="assistant",
        text="Robotics may be relevant",
        session_id="s1",
    )
    analysis = analyse_ai_conversations((assistant,))
    signal = classify_event(assistant)
    assert signal.signal_class is SignalClass.AMBIENT_EXPOSURE
    assert signal.weight == 0 and not signal.interest_contributing
    assert analysis.user_originated_topics == () and analysis.recurrent_questions == ()
    assert analysis.evidence[0].role == "exposure"
    assert _interest_states((assistant,), "robotics") == ()


def test_scenario_04_user_authored_robotics_questions_across_six_sessions_are_recurrent():
    questions = tuple(
        _event(
            "user_authored",
            at=START + timedelta(weeks=index),
            domain="ai_conversation",
            topic="robotics",
            role="user",
            text=f"robotics architecture question {index}",
            session_id=f"session-{index}",
        )
        for index in range(6)
    )
    analysis = analyse_ai_conversations(questions)
    states = _interest_states(questions, "robotics")
    assert analysis.session_count == analysis.user_turn_count == 6
    assert analysis.assistant_turn_count == 0
    assert analysis.recurrent_questions == ({"topic_label": "robotics", "user_turn_count": 6, "session_count": 6},)
    assert all(ref.role == "supporting" for ref in analysis.evidence)
    assert len(states) == 1 and states[0].intensity > 0


def test_scenario_05_search_burst_followed_by_project_creation_links_transition():
    first = _event("query", action=ActionClass.SEARCHED, domain="search", service="browser", topic="robotics", text="build robot", relationships={"domain": "a.example"})
    second = _event("query", at=START + timedelta(minutes=10), action=ActionClass.SEARCHED, domain="search", service="search-engine", topic="robotics", text="build robot motor", relationships={"domain": "b.example", "refines_event_id": str(first.event_id)})
    third = _event("query", at=START + timedelta(minutes=20), action=ActionClass.SEARCHED, domain="search", service="docs", topic="robotics", text="build robot motor controller", relationships={"domain": "c.example", "refines_event_id": str(second.event_id)})
    project = _event("file_created", at=START + timedelta(days=1), action=ActionClass.CREATED, domain="projects", topic="robotics", relationships={"source_event_ids": [str(first.event_id)]})
    analysis = analyse_search_events((first, second, third, project))
    assert len(analysis.episodes) == 1
    assert analysis.episodes[0].query_count == 3
    assert analysis.episodes[0].cross_source_count == 3
    assert analysis.episodes[0].refinement_depth == 2
    assert analysis.episodes[0].project_transition is True


def test_scenario_06_one_curiosity_search_is_abandoned_and_not_enduring_interest():
    curiosity = _event("query", action=ActionClass.SEARCHED, domain="search", topic="volcanoes", text="why is lava red")
    analysis = analyse_search_events((curiosity,))
    assert analysis.abandoned_one_offs == 1 and analysis.episodes == ()
    assert _interest_states((curiosity,), "volcanoes", search_episode_ids=set()) == ()


def test_scenario_07_topic_return_after_nine_month_dormancy_is_marked_returning():
    returned = _event(
        "user_authored",
        at=START + timedelta(days=274),
        domain="ai_conversation",
        topic="robotics",
        role="user",
        session_id="return-session",
    )
    states = _interest_states((returned,), "robotics", prior_topic_ids={"robotics"})
    assert len(states) == 1 and states[0].change == "returning"
    assert states[0].first_observed_at == returned.occurred_at


def test_scenario_08_camera_photo_with_gps_and_capture_time_is_strong_location_observation():
    candidate = create_location_candidate(
        uuid4(),
        _origin(MediaOrigin.CAMERA_ORIGIN),
        _location(LocationBasis.EXIF_GPS, place="UCL", gps=True, credible_time=True),
    )
    assert candidate.evidence_class is LocationEvidenceClass.STRONG_OBSERVATION
    assert candidate.media_origin is MediaOrigin.CAMERA_ORIGIN
    assert candidate.lat is not None and candidate.occurred_at == START


def test_scenario_09_visual_ucl_landmark_without_gps_remains_unreviewed_candidate():
    candidate = create_location_candidate(
        uuid4(),
        _origin(MediaOrigin.CAMERA_ORIGIN),
        _location(LocationBasis.VISUAL_LANDMARK, place="UCL", gps=False, credible_time=False),
    )
    assert candidate.basis is LocationBasis.VISUAL_LANDMARK
    assert candidate.evidence_class is LocationEvidenceClass.CANDIDATE
    assert candidate.reviewed_by is None and candidate.lat is None


def test_scenario_10_screenshot_of_ucl_website_cannot_establish_physical_presence():
    candidate = create_location_candidate(
        uuid4(),
        _origin(MediaOrigin.SCREENSHOT),
        _location(LocationBasis.VISUAL_LANDMARK, place="UCL", gps=False, credible_time=False),
    )
    assert candidate.media_origin is MediaOrigin.SCREENSHOT
    assert candidate.evidence_class is LocationEvidenceClass.CANDIDATE
    assert candidate.calculated_features["credible_original_capture_time"] is False


def test_scenario_11_downloaded_paris_image_cannot_establish_physical_presence():
    candidate = create_location_candidate(
        uuid4(),
        _origin(MediaOrigin.DOWNLOADED_MEDIA),
        _location(LocationBasis.EXIF_GPS, place="Paris", gps=True, credible_time=True),
    )
    assert candidate.media_origin is MediaOrigin.DOWNLOADED_MEDIA
    assert candidate.evidence_class is LocationEvidenceClass.CANDIDATE


def test_scenario_12_usage_collapse_aligned_with_unrelated_event_is_only_coincidence():
    candidate = correlate_change(
        _change("usage collapse"),
        (_external("football", title="Football tournament begins"),),
    )[0]
    assert candidate.temporal_proximity > 0
    assert candidate.semantic_relevance == 0
    assert candidate.status is CorrelationStatus.COINCIDENCE_CANDIDATE


def test_scenario_13_relevant_event_near_change_without_exposure_evidence_is_only_coincidence():
    candidate = correlate_change(_change("robotics"), (_external("robotics"),))[0]
    assert candidate.semantic_relevance > 0 and candidate.temporal_proximity > 0
    assert candidate.user_exposure_evidence == ()
    assert candidate.preceding_related_activity is False
    assert candidate.status is CorrelationStatus.COINCIDENCE_CANDIDATE


def test_scenario_14_pre_change_search_and_user_ai_discussion_support_relation():
    observations = (
        _exposure("searched for", topic="robotics"),
        _exposure("authored AI discussion about", topic="robotics", at=START - timedelta(days=3)),
    )
    candidate = correlate_change(
        _change("robotics"),
        (_external("robotics"),),
        observations,
        behavioural_persistence=0.8,
    )[0]
    assert candidate.status is CorrelationStatus.EVIDENCE_SUPPORTED_RELATION
    assert len(candidate.user_exposure_evidence) == 2
    assert candidate.preceding_related_activity is True
    assert candidate.causal_claim is False


def test_scenario_15_contextual_candidates_never_become_causal_automatically():
    coincidence = correlate_change(_change("robotics"), (_external("robotics"),))[0]
    possible = correlate_change(
        _change("robotics"), (_external("robotics"),), (_exposure("searched for"),)
    )[0]
    supported = correlate_change(
        _change("robotics"),
        (_external("robotics"),),
        (_exposure("searched for"),),
        behavioural_persistence=1.0,
    )[0]
    assert [item.status for item in (coincidence, possible, supported)] == [
        CorrelationStatus.COINCIDENCE_CANDIDATE,
        CorrelationStatus.POSSIBLE_RELATION,
        CorrelationStatus.EVIDENCE_SUPPORTED_RELATION,
    ]
    assert all(item.causal_claim is False for item in (coincidence, possible, supported))
    assert all("caused_by" not in item.model_dump() for item in (coincidence, possible, supported))


def test_scenario_16_user_confirmed_relationship_is_distinct_and_still_not_machine_causation():
    candidate = correlate_change(
        _change("robotics"),
        (_external("robotics"),),
        (_exposure("confirmed relationship to", direct_statement=True),),
    )[0]
    assert candidate.status is CorrelationStatus.USER_CONFIRMED
    assert candidate.direct_user_statement is True
    assert candidate.user_exposure_evidence[0].role == "user_confirmation"
    assert candidate.causal_claim is False


def test_scenario_17_historical_activity_imported_in_2026_is_placed_by_occurrence_time():
    occurred_at = datetime(2018, 6, 12, 9, 30, tzinfo=UTC)
    imported_at = datetime(2026, 2, 1, tzinfo=UTC)
    historical = _event(
        "file_created",
        at=occurred_at,
        action=ActionClass.CREATED,
        domain="projects",
        topic="robotics",
        relationships={"imported_at": imported_at.isoformat()},
    )
    states = aggregate_interest_states(
        (historical,),
        _assignments((historical,), "robotics"),
        subject_id=SUBJECT,
        window_start=datetime(2018, 6, 1, tzinfo=UTC),
        window_end=datetime(2018, 7, 1, tzinfo=UTC),
    )
    assert len(states) == 1
    assert states[0].evidence_event_ids == (historical.event_id,)
    assert states[0].window_end < imported_at


@pytest.mark.asyncio
async def test_scenario_18_every_evidence_link_resolves_to_source(migrated_database, tmp_path):
    await _assert_evidence_trace_resolves(migrated_database, tmp_path)
