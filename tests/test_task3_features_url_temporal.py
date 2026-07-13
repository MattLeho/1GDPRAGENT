from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import pytest

from features.inference_language import detect_inference_language
from features.temporal import normalise_temporal, temporal_feature_candidate
from features.url import decompose_url, url_feature_candidate
from ingestion.models import FeatureCandidateStatus, TemporalPrecision


def test_url_decomposition_is_local_structural_and_preserves_duplicate_query_values(monkeypatch):
    # If implementation ever grows a hidden network path this guard catches the
    # most common socket entry point; the module itself imports no HTTP client.
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: pytest.fail("network attempted"))
    result = decompose_url(
        "https://shop.account.example.co.uk:8443/orders/a%20b?user_id=42&tag=x&tag=y#receipt"
    )
    assert result.scheme == "https"
    assert result.hostname == "shop.account.example.co.uk"
    assert result.domain == "example.co.uk" and result.subdomain == "shop.account"
    assert result.port == 8443 and result.path == "/orders/a%20b" and result.decoded_path == "/orders/a b"
    assert result.query_keys == ("user_id", "tag")
    assert result.query_pairs == (("user_id", "42"), ("tag", "x"), ("tag", "y"))
    assert result.fragment == "receipt"
    assert result.query_identifier_candidates[0].candidate_types == ("identifier_key_hint",)


def test_url_query_values_are_only_candidates_and_feature_is_grounded():
    artifact_id = uuid4()
    result = decompose_url("https://example.test/?email=person%40example.test&x=550e8400-e29b-41d4-a716-446655440000")
    candidate_types = {kind for item in result.query_identifier_candidates for kind in item.candidate_types}
    assert {"email", "uuid"} <= candidate_types
    candidate = url_feature_candidate(result.original_value, source_artifact_ids=(artifact_id,))
    assert candidate.source_artifact_ids == (artifact_id,)
    assert candidate.candidate_status is FeatureCandidateStatus.DETERMINISTIC
    assert candidate.calculated_values["domain"] == "example.test"


def test_invalid_url_port_and_control_characters_are_rejected():
    with pytest.raises(ValueError, match="invalid URL"):
        decompose_url("https://example.test:99999/path")
    with pytest.raises(ValueError, match="control"):
        decompose_url("https://example.test/\nsecret")


def test_inference_language_hits_are_candidates_not_controller_assertions():
    event_id = uuid4()
    candidates = detect_inference_language(
        {"audience_segment": "Likely affinity: travel", "unrelated": "ordinary value"},
        source_event_ids=(event_id,),
        context_radius=12,
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.candidate_status is FeatureCandidateStatus.ADJUDICATION_REQUIRED
    assert candidate.calculated_values["semantic_claim"] is None
    assert {"audience", "segment", "likely", "affinity"} <= set(candidate.calculated_values["matched_terms"])
    assert candidate.source_event_ids == (event_id,)
    assert all(len(item["context"]) <= 32 for item in candidate.calculated_values["matches"])
    assert detect_inference_language("The weather is sunny", source_event_ids=(event_id,)) == ()

    bounded = detect_inference_language(
        "likely " * 20, source_event_ids=(event_id,), maximum_matches=3,
    )[0]
    assert len(bounded.calculated_values["matches"]) == 3
    assert bounded.calculated_values["match_count"] == 20
    assert bounded.calculated_values["omitted_match_count"] == 17


def test_inference_language_requires_grounding_through_frozen_contract():
    with pytest.raises(ValueError, match="source event or artefact"):
        detect_inference_language("predicted interest")


def test_date_only_never_becomes_midnight_utc():
    result = normalise_temporal("2025-03-04", parser_version="fixture-1")
    assert result.original_value == "2025-03-04"
    assert result.parsed_value == date(2025, 3, 4)
    assert not isinstance(result.parsed_value, datetime)
    assert result.temporal_precision is TemporalPrecision.DAY
    assert result.timezone is None and result.timezone_assumption is None
    assert result.timezone_evidence == "not_applicable_date_only"
    assert result.parser_version == "fixture-1"


def test_temporal_precision_timezone_evidence_and_assumption_are_explicit():
    aware = normalise_temporal("2025-03-04T12:34:56+01:00", parser_version="iso-1")
    assert aware.temporal_precision is TemporalPrecision.SECOND
    assert aware.timezone == "+01:00" and aware.timezone_evidence == "explicit_offset"
    assert aware.timezone_assumption is None

    floating = normalise_temporal(
        "2025-03-04T12:34", parser_version="iso-1", timezone_assumption="source locale unknown",
    )
    assert floating.temporal_precision is TemporalPrecision.MINUTE
    assert floating.parsed_value.tzinfo is None and floating.timezone is None
    assert floating.timezone_evidence == "absent"
    assert floating.timezone_assumption == "source locale unknown"

    named = normalise_temporal("2025-03-04T12:00 [Europe/London]", parser_version="iso-1")
    assert named.temporal_precision is TemporalPrecision.MINUTE
    assert named.timezone == "Europe/London" and named.timezone_evidence == "explicit_iana_zone"

    transition = normalise_temporal("2025-10-26T01:30 [Europe/London]", parser_version="iso-1")
    assert transition.parsed_value.tzinfo is None
    assert transition.timezone == "Europe/London"
    assert transition.timezone_evidence == "explicit_iana_zone_unresolved_transition"


def test_year_month_range_epoch_unknown_and_grounded_candidate():
    assert normalise_temporal("2025", parser_version="1").temporal_precision is TemporalPrecision.YEAR
    assert normalise_temporal("2025-03", parser_version="1").temporal_precision is TemporalPrecision.MONTH
    span = normalise_temporal({"start": "2025-03-01", "end": "2025-03-31"}, parser_version="1")
    assert span.temporal_precision is TemporalPrecision.RANGE
    assert span.parsed_value == {"start": date(2025, 3, 1), "end": date(2025, 3, 31)}
    epoch = normalise_temporal(1_741_088_096, parser_version="unix-1")
    assert epoch.timezone == "UTC" and epoch.timezone_evidence == "unix_epoch_semantics"
    unknown = normalise_temporal("next Tuesday", parser_version="1")
    assert unknown.temporal_precision is TemporalPrecision.UNKNOWN and unknown.parsed_value is None

    event_id = uuid4()
    candidate = temporal_feature_candidate("2025-03", parser_version="1", source_event_ids=(event_id,))
    assert candidate.candidate_status is FeatureCandidateStatus.DETERMINISTIC
    assert candidate.calculated_values["original_value"] == "2025-03"
    assert candidate.calculated_values["parser_version"] == "1"
