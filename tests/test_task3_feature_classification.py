from __future__ import annotations

from uuid import uuid4

from ingestion.models import ActionClass, ActivityEvent, FeatureCandidateStatus, PrivacyDataClass

from features.classification import ServicePathDataClassDetector, classify_data_classes, classify_service_path
from features.dictionaries import (
    DEFAULT_KEY_DICTIONARIES,
    DICTIONARY_VERSION,
    KeyCategory,
    match_schema_key,
    normalize_schema_key,
)


def test_versioned_key_dictionaries_normalize_without_substring_matching() -> None:
    assert normalize_schema_key("eventTimestamp") == "event_timestamp"
    matches = match_schema_key("eventTimestamp")
    assert [(match.category, match.dictionary_version) for match in matches] == [
        (KeyCategory.TIMESTAMP, DICTIONARY_VERSION)
    ]
    assert match_schema_key("not_really_an_event_timestamp_suffix") == ()
    assert {dictionary.category for dictionary in DEFAULT_KEY_DICTIONARIES} == set(KeyCategory)


def test_service_path_classifier_preserves_specific_service_and_path_evidence() -> None:
    candidate = classify_service_path(
        "Takeout/My Activity/Search/MyActivity.json",
        source_artifact_ids=(uuid4(),),
    )
    assert candidate.candidate_status is FeatureCandidateStatus.DETERMINISTIC
    assert candidate.calculated_values["service_candidates"] == ["google_search"]
    assert candidate.calculated_values["data_class_candidates"] == [
        PrivacyDataClass.BEHAVIOURAL_EVENT.value,
        PrivacyDataClass.SEARCH_HISTORY.value,
    ]
    assert candidate.rule_result is True


def test_service_path_classifier_unknown_remains_adjudication_eligible() -> None:
    candidate = classify_service_path(
        "Export/Unrecognised/records.bin",
        source_artifact_ids=(uuid4(),),
    )
    assert candidate.candidate_status is FeatureCandidateStatus.UNKNOWN
    assert candidate.calculated_values["service_candidates"] == []
    assert candidate.calculated_values["semantic_adjudication_eligible"] is True
    assert candidate.confidence == 0.0


def test_data_class_detector_emits_multi_label_candidate_with_dictionary_versions() -> None:
    candidate = classify_data_classes(
        schema_keys=("emailAddress", "latitude", "audienceSegment", "message"),
        data_domain="communication",
        source_event_ids=(uuid4(),),
    )
    classes = set(candidate.calculated_values["data_classes"])
    assert {
        PrivacyDataClass.DIRECT_IDENTIFIER.value,
        PrivacyDataClass.LOCATION.value,
        PrivacyDataClass.COMMUNICATION.value,
        PrivacyDataClass.INFERRED_ATTRIBUTE.value,
    } <= classes
    dictionary_versions = {
        match["dictionary_version"]
        for match in candidate.calculated_values["key_dictionary_matches"]
    }
    assert dictionary_versions == {DICTIONARY_VERSION}
    assert candidate.candidate_status is FeatureCandidateStatus.DETERMINISTIC


def test_data_class_detector_does_not_promote_unknown_keys() -> None:
    candidate = classify_data_classes(
        schema_keys=("flibble", "misc_value"),
        source_artifact_ids=(uuid4(),),
    )
    assert candidate.calculated_values["data_classes"] == [PrivacyDataClass.UNKNOWN.value]
    assert candidate.calculated_values["semantic_adjudication_eligible"] is True
    assert candidate.candidate_status is FeatureCandidateStatus.UNKNOWN


def test_data_class_candidate_requires_grounded_source_reference() -> None:
    try:
        classify_data_classes(schema_keys=("email",))
    except ValueError as exc:
        assert "source event or artefact" in str(exc)
    else:
        raise AssertionError("expected ungrounded candidate to be rejected")


def test_service_data_class_detector_consumes_activity_event_contract() -> None:
    event = ActivityEvent(
        event_id=uuid4(),
        record_signature="b" * 64,
        subject_id="subject",
        export_snapshot_id=uuid4(),
        artifact_id=uuid4(),
        service="google_search",
        data_domain="search_history",
        event_type="searched",
        action_class=ActionClass.SEARCHED,
        identifiers={"account_id": "acct-1"},
        parser_id="search-parser",
        parser_version="1.0.0",
        source_locator_id=uuid4(),
    )
    candidates = ServicePathDataClassDetector().detect((event,))
    assert len(candidates) == 2
    assert {candidate.detector_id for candidate in candidates} == {
        ServicePathDataClassDetector.detector_id
    }
    assert PrivacyDataClass.SEARCH_HISTORY.value in candidates[1].calculated_values["data_classes"]
