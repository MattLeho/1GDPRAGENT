from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from uuid import uuid4

import pytest

from features.density import DensityCooccurrenceDetector, aggregate_density_features
from features.geospatial import (
    ExplicitInteractionFeatureDetector,
    GeospatialFeatureDetector,
    extract_explicit_interactions,
    extract_geospatial_features,
)
from features.pipeline import extract_features
from ingestion.models import ActivityEvent, FeatureCandidateStatus


def _event(*, when=None, event_type="fixture.event", domain="activity", locations=None,
           relationships=None, identifiers=None, object_id=None):
    event_id = uuid4()
    return ActivityEvent(
        event_id=event_id,
        record_signature=hashlib.sha256(str(event_id).encode()).hexdigest(),
        subject_id="person-1", export_snapshot_id=uuid4(), artifact_id=uuid4(),
        service="Fixture", data_domain=domain, event_type=event_type,
        occurred_at=when, object_id=object_id, identifiers=identifiers or {},
        locations=locations or {}, relationships=relationships or {},
        parser_id="fixture", parser_version="1", source_locator_id=uuid4(),
    )


def test_geospatial_precision_preserves_reported_accuracy_without_place_role_inference():
    exact = _event(locations={
        "capture": {"latitude": "51.50070", "longitude": "-0.12460", "accuracy": "50 ft"},
    })
    coarse = _event(locations={
        "point": {"lat": 51.5, "lng": -0.1, "horizontal_accuracy": 250},
    })
    named = _event(locations={"locality": "London"})
    candidates = extract_geospatial_features((exact, coarse, named))

    assert [item.calculated_values["precision"] for item in candidates] == [
        "EXACT_COORDINATE", "COARSE_COORDINATE", "CITY",
    ]
    assert candidates[0].calculated_values["reported_accuracy"] == "50 ft"
    assert candidates[0].calculated_values["reported_accuracy_metres"] == pytest.approx(15.24)
    assert candidates[1].calculated_values["reported_accuracy"] == 250
    assert candidates[1].calculated_values["reported_accuracy_metres"] == 250
    assert all(item.source_event_ids and item.candidate_status is FeatureCandidateStatus.DETERMINISTIC for item in candidates)
    serialised = json.dumps([item.model_dump(mode="json") for item in candidates], sort_keys=True)
    assert "HOME" not in serialised and "dominant" not in serialised


def test_geospatial_detector_rejects_invalid_coordinates_and_does_not_cluster_events():
    events = tuple(
        _event(
            when=datetime(2024, 1, day, 2, tzinfo=timezone.utc),
            locations={"lat": 95, "longitude": -0.1, "accuracy": 5},
        )
        for day in range(1, 5)
    )
    assert tuple(GeospatialFeatureDetector().detect(events)) == ()


def test_interactions_require_six_source_explicit_actions_and_never_infer_social_roles():
    explicit = _event(relationships={
        "sent_to": "alice@example.test",
        "membership": {"action": "MEMBER_OF", "target": "privacy-club"},
        "friend": "bob@example.test",
        "partner": "charlie@example.test",
    })
    communication_only = _event(event_type="message.received", relationships={"person": "dana"})
    candidates = extract_explicit_interactions((explicit, communication_only))
    assert {item.calculated_values["action"] for item in candidates} == {"SENT_TO", "MEMBER_OF"}
    payload = json.dumps([item.calculated_values for item in candidates], sort_keys=True)
    assert "FRIEND" not in payload and "PARTNER" not in payload and "COLLEAGUE" not in payload
    assert {item.source_event_ids for item in candidates} == {(explicit.event_id,)}
    assert tuple(ExplicitInteractionFeatureDetector().detect((communication_only,))) == ()


def test_density_aggregate_has_daily_hourly_object_burst_and_periodicity_metrics():
    start = datetime(2024, 1, 1, 10, tzinfo=timezone.utc)
    events = tuple(
        _event(when=start + timedelta(days=index), event_type="search.performed", object_id=f"query-{index % 2}")
        for index in range(3)
    )
    candidates = aggregate_density_features(events)
    assert len(candidates) == 1
    values = candidates[0].calculated_values
    assert values["event_type"] == "search.performed"
    assert values["event_count"] == 3 and values["unique_object_count"] == 2
    assert values["events_by_day"] == {"2024-01-01": 1, "2024-01-02": 1, "2024-01-03": 1}
    assert values["hour_of_day_distribution"] == {"10": 3}
    assert values["burstiness"] == -1.0
    assert values["dominant_interval_seconds"] == 86400
    assert values["periodicity_score"] == 1.0
    assert values["first_seen"] == "2024-01-01T10:00:00+00:00"
    assert values["last_seen"] == "2024-01-03T10:00:00+00:00"
    assert candidates[0].source_event_ids == tuple(sorted((event.event_id for event in events), key=str))
    assert candidates == aggregate_density_features(reversed(events))
    assert aggregate_density_features((*events, events[0])) == candidates


def test_identifier_and_explicit_data_class_cross_domain_cooccurrence_are_aggregate_only():
    token = "person@example.test"
    first = _event(domain="search_history", identifiers={"email": token})
    second = _event(domain="communication", identifiers={"email": token})
    third = _event(domain="communication", identifiers={"email": "other@example.test"})
    classes = {
        first.event_id: ("DIRECT_IDENTIFIER",),
        second.event_id: ("DIRECT_IDENTIFIER",),
    }
    candidates = aggregate_density_features((first, second, third), data_classes_by_event=classes)
    identifier = next(item for item in candidates if item.feature_type == "identifier.cross_domain_cooccurrence")
    data_class = next(item for item in candidates if item.feature_type == "data_class.cross_domain_cooccurrence")
    assert identifier.calculated_values == {
        "identifier_type": "email",
        "token_hash": hashlib.sha256(json.dumps(token).encode()).hexdigest(),
        "domains": ["communication", "search_history"],
        "domain_count": 2,
        "event_count": 2,
    }
    assert token not in json.dumps(identifier.calculated_values)
    assert data_class.calculated_values["data_class"] == "DIRECT_IDENTIFIER"
    assert data_class.calculated_values["domains"] == ["communication", "search_history"]
    # The third event's domain never causes a data class to be invented.
    assert third.event_id not in data_class.source_event_ids


def test_partition_rows_accept_parquet_json_shapes_and_require_explicit_classes():
    shared = "opaque-fixture-token"
    first_id, second_id = uuid4(), uuid4()
    rows = [
        {
            "event_id": str(first_id), "artifact_id": str(uuid4()), "subject_id": "p",
            "event_type": "fixture", "data_domain": "domain-a",
            "occurred_at": "2024-01-01T00:00:00Z",
            "identifiers": json.dumps({"opaque": shared}),
            "data_classes": json.dumps(["QUASI_IDENTIFIER"]),
        },
        {
            "event_id": str(second_id), "artifact_id": str(uuid4()), "subject_id": "p",
            "event_type": "fixture", "data_domain": "domain-b",
            "occurred_at": "2024-01-01T01:00:00+00:00",
            "identifiers": json.dumps({"opaque": shared}),
            "data_classes": ["QUASI_IDENTIFIER"],
        },
    ]
    candidates = aggregate_density_features(rows)
    assert {item.feature_type for item in candidates} == {
        "activity.density", "identifier.cross_domain_cooccurrence",
        "data_class.cross_domain_cooccurrence",
    }
    assert tuple(DensityCooccurrenceDetector().detect(())) == ()
    with pytest.raises(ValueError, match="unsupported explicit data class"):
        aggregate_density_features([{**rows[0], "data_classes": ["FRIEND"]}])
    with pytest.raises(ValueError, match="grounding"):
        aggregate_density_features([{"event_type": "fixture"}])


def test_geo_interaction_and_density_detectors_use_feature_pipeline_without_model_residue():
    event = _event(
        when=datetime(2024, 1, 1, tzinfo=timezone.utc),
        locations={"city": "London"}, relationships={"followed": "source-account"},
    )
    result = extract_features(
        (event,),
        (GeospatialFeatureDetector(), ExplicitInteractionFeatureDetector(), DensityCooccurrenceDetector()),
        analysis_run_id=uuid4(),
    )
    assert result.event_count == 1 and result.model_invocation_count == 0
    assert {item.feature_type for item in result.candidates} == {
        "geospatial.precision", "interaction.explicit_action", "activity.density",
    }
