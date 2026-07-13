from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from insights.context import ExposureObservation, correlate_change
from insights.media import (
    LocationObservation,
    MediaOriginResult,
    aggregate_places,
    build_place_insight,
    create_media_content_candidate,
    create_location_candidate,
    visual_task_requests,
)
from insights.models import (
    ChangeInsight,
    CorrelationStatus,
    EvidenceKind,
    ExternalContextEvent,
    InsightEvidenceRef,
    LocationBasis,
    LocationEvidenceClass,
    MediaAnalysisMode,
    MediaOrigin,
    ProjectEpisodeView,
)


NOW = datetime(2025, 5, 20, tzinfo=timezone.utc)


def change(state_key: str = "robotics research") -> ChangeInsight:
    return ChangeInsight(
        insight_id=uuid4(), detector_id="fixture", detector_version="1",
        change_type="REGIME_SHIFT", state_key=state_key, detected_at=NOW,
        magnitude=2.0,
    )


def event(title: str, *, days_before: int = 2, topics: tuple[str, ...] = ()) -> ExternalContextEvent:
    return ExternalContextEvent(
        id=uuid4(), title=title, event_type="product_release",
        occurred_at=NOW - timedelta(days=days_before), topics=topics, ingested_at=NOW,
    )


def exposure(*, days_before: int = 5, statement: bool = False) -> ExposureObservation:
    at = NOW - timedelta(days=days_before)
    return ExposureObservation(
        evidence=InsightEvidenceRef(
            kind=EvidenceKind.ACTIVITY_EVENT, ref_id=uuid4(), role="exposure", occurred_at=at,
        ),
        occurred_at=at, topics=("robotics",), text="user searched robotics release",
        direct_user_statement=statement,
    )


def test_context_search_starts_from_change_and_proximity_alone_is_coincidence():
    result = correlate_change(change(), (event("Robotics product release", topics=("robotics",)),))
    assert len(result) == 1
    assert result[0].status is CorrelationStatus.COINCIDENCE_CANDIDATE
    assert result[0].causal_claim is False
    assert "caused_by" not in result[0].model_dump()
    assert result[0].local_change["state_key"] == "robotics research"
    assert result[0].external_event["title"] == "Robotics product release"
    assert any(ref.kind is EvidenceKind.EXTERNAL_CONTEXT_EVENT for ref in result[0].evidence)


def test_relevant_pre_change_exposure_can_strengthen_relation_but_never_cause():
    possible = correlate_change(
        change(), (event("Robotics product release", topics=("robotics",)),), (exposure(),),
    )[0]
    supported = correlate_change(
        change(), (event("Robotics product release", topics=("robotics",)),), (exposure(),),
        behavioural_persistence=0.8,
    )[0]
    assert possible.status is CorrelationStatus.POSSIBLE_RELATION
    assert supported.status is CorrelationStatus.EVIDENCE_SUPPORTED_RELATION
    assert supported.user_exposure_evidence and supported.preceding_related_activity
    assert possible.causal_claim is supported.causal_claim is False


def test_unrelated_or_post_change_exposure_does_not_strengthen_and_confirmation_is_separate():
    external = event("Robotics product release", topics=("robotics",))
    unrelated = ExposureObservation(
        evidence=InsightEvidenceRef(kind=EvidenceKind.ACTIVITY_EVENT, ref_id=uuid4(), role="exposure"),
        occurred_at=NOW - timedelta(days=1), topics=("gardening",), text="garden article",
    )
    post_change = exposure(days_before=-1)
    assert correlate_change(change(), (external,), (unrelated, post_change))[0].status is CorrelationStatus.COINCIDENCE_CANDIDATE
    confirmed = correlate_change(change(), (external,), (exposure(statement=True),))[0]
    assert confirmed.status is CorrelationStatus.USER_CONFIRMED
    assert confirmed.direct_user_statement and confirmed.causal_claim is False


def test_accepted_assertion_confirmation_is_separate_from_prechange_exposure():
    confirmation=InsightEvidenceRef(
        kind=EvidenceKind.ASSERTION,ref_id=uuid4(),role="user_confirmation",occurred_at=NOW+timedelta(days=1),
    )
    result=correlate_change(
        change(),(event("Robotics product release",topics=("robotics",)),),
        confirmation_evidence=(confirmation,),
    )[0]
    assert result.status is CorrelationStatus.USER_CONFIRMED
    assert result.direct_user_statement is True
    assert result.preceding_related_activity is False
    assert confirmation in result.user_exposure_evidence


def origin(value: MediaOrigin) -> MediaOriginResult:
    return MediaOriginResult(value, 0.9, {
        "source": "deterministic_metadata",
        "camera_origin_corroborated": value is MediaOrigin.CAMERA_ORIGIN,
    })


def location(basis: LocationBasis, **values) -> LocationObservation:
    defaults = dict(
        basis=basis, evidence_locator_id=uuid4(), occurred_at=NOW,
        temporal_precision="SECOND", lat=51.5246, lon=-0.1340,
        place_label="UCL", confidence=0.85, credible_original_capture_time=True,
    )
    defaults.update(values)
    return LocationObservation(**defaults)


def test_camera_gps_with_credible_capture_time_is_strong_observation():
    candidate = create_location_candidate(uuid4(), origin(MediaOrigin.CAMERA_ORIGIN), location(LocationBasis.EXIF_GPS))
    assert candidate.evidence_class is LocationEvidenceClass.STRONG_OBSERVATION
    assert {ref.kind for ref in candidate.evidence} == {EvidenceKind.SOURCE_ARTIFACT, EvidenceKind.EVIDENCE_LOCATOR}


def test_screenshot_download_and_generated_media_never_establish_presence():
    for media_origin in (MediaOrigin.SCREENSHOT, MediaOrigin.DOWNLOADED_MEDIA, MediaOrigin.GENERATED_MEDIA):
        candidate = create_location_candidate(uuid4(), origin(media_origin), location(LocationBasis.EXIF_GPS))
        assert candidate.evidence_class is LocationEvidenceClass.CANDIDATE


def test_visual_landmark_stays_candidate_and_user_confirmation_is_distinct():
    landmark = create_location_candidate(
        uuid4(), origin(MediaOrigin.CAMERA_ORIGIN),
        location(LocationBasis.VISUAL_LANDMARK, lat=None, lon=None, credible_original_capture_time=False),
    )
    confirmed = create_location_candidate(
        uuid4(), origin(MediaOrigin.UNKNOWN),
        location(LocationBasis.USER_CONFIRMED, reviewed_by="user", credible_original_capture_time=False),
    )
    assert landmark.evidence_class is LocationEvidenceClass.CANDIDATE
    assert confirmed.evidence_class is LocationEvidenceClass.USER_CONFIRMED


def test_metadata_only_is_default_and_visual_work_is_only_described():
    artifact_id, locator_id = uuid4(), uuid4()
    assert visual_task_requests(artifact_id, locator_id) == ()
    requests = visual_task_requests(artifact_id, locator_id, MediaAnalysisMode.SELECTIVE_VISUAL)
    assert {request.task_key for request in requests} == {"image.origin_classification"}
    assert all(request.artifact_id == artifact_id for request in requests)
    screenshot_requests=visual_task_requests(
        artifact_id,locator_id,MediaAnalysisMode.SELECTIVE_VISUAL,origin(MediaOrigin.SCREENSHOT),
    )
    assert {request.task_key for request in screenshot_requests}=={"image.ocr","image.caption"}
    camera_requests=visual_task_requests(
        artifact_id,locator_id,MediaAnalysisMode.SELECTIVE_VISUAL,origin(MediaOrigin.CAMERA_ORIGIN),
    )
    assert camera_requests==()


def test_origin_classifier_uses_geometry_and_download_provenance_conservatively():
    from insights.media import classify_media_origin
    screenshot=classify_media_origin({"dimensions":{"width":1920,"height":1080}},original_path="capture.png")
    downloaded=classify_media_origin({"downloaded_from":"https://example.invalid/photo"},original_path="photo.jpg")
    assert screenshot.origin is MediaOrigin.SCREENSHOT
    assert screenshot.calculated_features["common_screen_geometry"] is True
    assert downloaded.origin is MediaOrigin.DOWNLOADED_MEDIA
    assert downloaded.calculated_features["download_source_hint_present"] is True


def test_routed_camera_origin_cannot_override_screenshot_or_download_provenance():
    from insights.media import classify_media_origin
    routed_camera={"origin":"camera_origin","confidence":0.99}
    screenshot=classify_media_origin(
        {"device":{"make":"Fixture"},"capture_timestamp":"2025:01:01 12:00:00"},
        original_path="Screenshot 2025.png",routed_result=routed_camera,
    )
    downloaded=classify_media_origin(
        {"downloaded_from":"https://example.invalid/photo"},
        original_path="Downloads/photo.jpg",routed_result=routed_camera,
    )
    assert screenshot.origin is MediaOrigin.SCREENSHOT
    assert downloaded.origin is MediaOrigin.DOWNLOADED_MEDIA
    assert screenshot.calculated_features["origin_conflict"] is True
    assert downloaded.calculated_features["origin_conflict"] is True
    assert screenshot.calculated_features["camera_origin_corroborated"] is False
    assert downloaded.calculated_features["camera_origin_corroborated"] is False


def test_routed_screenshot_or_download_conflict_keeps_metadata_gps_as_candidate():
    from insights.media import classify_media_origin
    metadata={"device":{"make":"Fixture"},"capture_timestamp":"2025:01:01 12:00:00"}
    for routed_origin in ("screenshot","downloaded_media"):
        classified=classify_media_origin(
            metadata,original_path="camera.jpg",
            routed_result={"origin":routed_origin,"confidence":0.99},
        )
        candidate=create_location_candidate(uuid4(),classified,location(LocationBasis.EXIF_GPS))
        assert classified.calculated_features["origin_conflict"] is True
        assert candidate.evidence_class is LocationEvidenceClass.CANDIDATE


def test_routed_screenshot_outputs_create_evidence_linked_content_candidates_without_raw_text():
    artifact_id,locator_id=uuid4(),uuid4()
    candidate=create_media_content_candidate(
        artifact_id=artifact_id,evidence_locator_id=locator_id,
        origin=origin(MediaOrigin.SCREENSHOT),task_outputs={
            "image.ocr":{"text":"GitHub browser dashboard example.com","words":[{"text":"GitHub"}]},
            "image.caption":{"text":"A browser interface","topics":["software"],"entities":["GitHub"]},
        },
    )
    assert candidate.application_candidates == ("github",)
    assert candidate.interface_candidates == ("browser", "dashboard")
    assert candidate.webpage_candidates == ("example.com",)
    assert candidate.visible_topic_candidates == ("software",)
    assert candidate.visible_entity_candidates == ("GitHub",)
    assert "GitHub browser dashboard" not in candidate.model_dump_json()
    assert {ref.kind for ref in candidate.evidence} == {EvidenceKind.SOURCE_ARTIFACT,EvidenceKind.EVIDENCE_LOCATOR}


def test_place_aggregates_preserve_evidence_class_and_confidence():
    artifact = uuid4()
    camera = create_location_candidate(artifact, origin(MediaOrigin.CAMERA_ORIGIN), location(LocationBasis.EXIF_GPS))
    screenshot = create_location_candidate(uuid4(), origin(MediaOrigin.SCREENSHOT), location(LocationBasis.EXIF_GPS))
    aggregates = aggregate_places((camera, screenshot))
    assert len(aggregates) == 1
    aggregate = aggregates[0]
    assert aggregate["evidence_class_counts"] == {"candidate": 1, "strong_observation": 1}
    assert aggregate["confidence_values"] == (0.85, 0.85)
    assert aggregate["presence_supported_count"] == 1


def test_movement_and_project_links_use_presence_evidence_only():
    def camera(place: str, at: datetime):
        return create_location_candidate(
            uuid4(), origin(MediaOrigin.CAMERA_ORIGIN),
            location(
                LocationBasis.EXIF_GPS, place_label=place, occurred_at=at,
                lat=51.5 if place == "London" else 48.85,
                lon=-0.1 if place == "London" else 2.35,
            ),
        )

    observations = (
        camera("London", datetime(2025, 1, 4, tzinfo=timezone.utc)),
        camera("London", datetime(2025, 1, 18, tzinfo=timezone.utc)),
        camera("Paris", datetime(2025, 2, 5, tzinfo=timezone.utc)),
        camera("Paris", datetime(2025, 2, 6, tzinfo=timezone.utc)),
        create_location_candidate(
            uuid4(), origin(MediaOrigin.SCREENSHOT),
            location(
                LocationBasis.EXIF_GPS, place_label="Tokyo",
                occurred_at=datetime(2025, 2, 6, tzinfo=timezone.utc),
                lat=35.68, lon=139.76,
            ),
        ),
    )
    project = ProjectEpisodeView(
        insight_id=uuid4(), detector_id="fixture", detector_version="1",
        start_at=datetime(2025, 2, 1, tzinfo=timezone.utc),
        end_at=datetime(2025, 2, 10, tzinfo=timezone.utc),
    )
    insight = build_place_insight(
        observations, insight_id=uuid4(), project_episodes=(project,),
    )
    assert len(insight.activity_centre_changes) == 1
    assert insight.activity_centre_changes[0]["home_inference"] is False
    assert len(insight.travel_periods) == 1
    assert insight.travel_periods[0]["place_keys"] == ("label:paris",)
    assert len(insight.place_linked_project_episodes) == 1
    assert insight.place_linked_project_episodes[0]["place_keys"] == ("label:paris",)
    assert all("tokyo" not in str(item).casefold() for item in (
        *insight.activity_centre_changes,
        *insight.travel_periods,
        *insight.place_linked_project_episodes,
    ))
