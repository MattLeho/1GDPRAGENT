from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from ingestion.models import FeatureCandidateStatus
from ingestion.models import ActionClass, ActivityEvent

from features.identifiers import (
    IdentifierObservation,
    IdentifierFeatureDetector,
    IdentifierType,
    aggregate_identifier_candidates,
    analyze_opaque_identifiers,
    detect_identifier,
)


def test_detects_strong_and_contextual_identifier_types() -> None:
    cases = (
        ("Person@Example.COM", None, IdentifierType.EMAIL, "person@example.com"),
        ("+44 (0)20 7946 0958", "phone_number", IdentifierType.PHONE, "+4402079460958"),
        ("JeanMarc", "username", IdentifierType.USERNAME, "JeanMarc"),
        ("acct-9281", "account_id", IdentifierType.ACCOUNT_ID, "acct-9281"),
        ("device-abc", "device_id", IdentifierType.DEVICE_ID, "device-abc"),
        ("ad-123", "advertising_id", IdentifierType.ADVERTISING_ID, "ad-123"),
        ("cookie-123", "cookie_id", IdentifierType.COOKIE_ID, "cookie-123"),
        ("profile-123", "profile_id", IdentifierType.PROFILE_ID, "profile-123"),
        ("customer-123", "customer_id", IdentifierType.PAYMENT_CUSTOMER_ID, "customer-123"),
        ("2001:db8::1", None, IdentifierType.IP, "2001:db8::1"),
        ("AA-BB-CC-DD-EE-FF", None, IdentifierType.MAC, "aa:bb:cc:dd:ee:ff"),
    )
    for value, key, expected_type, expected_value in cases:
        detected = detect_identifier(value, key=key)
        assert len(detected) == 1
        assert detected[0].identifier_type is expected_type
        assert detected[0].normalized_value == expected_value


def test_url_carried_identifiers_are_found_locally_without_fetching() -> None:
    query = detect_identifier("https://example.test/view?profile_id=p-123&lang=en")
    path = detect_identifier("https://example.test/users/user-456/history")
    assert [(item.identifier_type, item.normalized_value) for item in query] == [
        (IdentifierType.URL_CARRIED_IDENTIFIER, "p-123")
    ]
    assert [(item.identifier_type, item.normalized_value) for item in path] == [
        (IdentifierType.URL_CARRIED_IDENTIFIER, "user-456")
    ]


def test_ordinary_unknown_text_is_not_called_an_identifier() -> None:
    assert detect_identifier("a normal sentence with spaces") == ()
    assert detect_identifier("not_semantic") == ()


def test_all_identifier_aggregates_include_required_counts_and_stability() -> None:
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    observations = (
        IdentifierObservation("person@example.test", source_artifact_id=uuid4(), service="mail", domain="communication", schema_id="s1", seen_at=now),
        IdentifierObservation("PERSON@example.test", source_artifact_id=uuid4(), service="contacts", domain="contact", schema_id="s2", seen_at=now),
    )
    candidate = aggregate_identifier_candidates(observations)[0]
    values = candidate.calculated_values
    assert values["identifier_type"] == IdentifierType.EMAIL.value
    assert values["occurrence_count"] == 2
    assert values["source_count"] == 2
    assert values["service_count"] == 2
    assert values["domain_count"] == 2
    assert values["schema_count"] == 2
    assert values["first_seen"] == now.isoformat()
    assert values["last_seen"] == now.isoformat()
    assert values["stability"] == 0.5
    assert candidate.candidate_status is FeatureCandidateStatus.DETERMINISTIC


def test_opaque_recurring_token_remains_semantically_unknown() -> None:
    token = "a8f45c73d20e49b1b6ac1296"
    first_artifact, second_artifact = uuid4(), uuid4()
    observations = (
        IdentifierObservation(token, source_artifact_id=first_artifact, service="alpha", domain="search", schema_id="schema-a", seen_at=datetime(2024, 1, 1, tzinfo=timezone.utc)),
        IdentifierObservation(token, source_artifact_id=second_artifact, service="beta", domain="ads", schema_id="schema-b", seen_at=datetime(2025, 1, 1, tzinfo=timezone.utc)),
        IdentifierObservation(token, source_artifact_id=first_artifact, service="alpha", domain="search", schema_id="schema-a", seen_at=datetime(2026, 1, 1, tzinfo=timezone.utc)),
    )
    opaque = analyze_opaque_identifiers(observations)[0]
    assert opaque.occurrence_count == 3
    assert opaque.source_count == 2
    assert opaque.service_count == 2
    assert opaque.domain_count == 2
    assert opaque.cross_schema_count == 2
    assert opaque.cross_domain_count == 2
    assert opaque.recurrence_ratio == 2 / 3
    assert opaque.entropy_bits_per_character > 2.5
    assert opaque.assigned_meaning is None

    feature = aggregate_identifier_candidates(observations)[0]
    assert feature.candidate_status is FeatureCandidateStatus.UNKNOWN
    assert feature.calculated_values["identifier_type"] == IdentifierType.OPAQUE_RECURRING_TOKEN.value
    assert feature.calculated_values["normalized_value"] is None
    assert feature.calculated_values["assigned_meaning"] is None
    assert feature.calculated_values["semantic_adjudication_eligible"] is True
    assert token not in feature.model_dump_json()


def test_identifier_observation_requires_provenance_reference() -> None:
    try:
        IdentifierObservation("person@example.test")
    except ValueError as exc:
        assert "event or artefact" in str(exc)
    else:
        raise AssertionError("expected provenance-free observation to be rejected")


def test_identifier_detector_consumes_frozen_activity_event_contract() -> None:
    event_id, artifact_id = uuid4(), uuid4()
    event = ActivityEvent(
        event_id=event_id,
        record_signature="a" * 64,
        subject_id="subject",
        export_snapshot_id=uuid4(),
        artifact_id=artifact_id,
        service="mail",
        data_domain="communication",
        event_type="message",
        action_class=ActionClass.COMMUNICATED,
        identifiers={"email": "person@example.test"},
        parser_id="mail-parser",
        parser_version="1.0.0",
        source_locator_id=uuid4(),
    )
    candidates = IdentifierFeatureDetector().detect((event,))
    assert len(candidates) == 1
    assert candidates[0].detector_id == IdentifierFeatureDetector.detector_id
    assert candidates[0].source_event_ids == (event_id,)
    assert candidates[0].source_artifact_ids == (artifact_id,)
