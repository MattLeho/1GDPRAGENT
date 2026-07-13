from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from insights.models import (
    CorrelationStatus, EvidenceKind, InsightEvidenceRef, InsightPeriod,
    LocationBasis, LocationEvidenceClass, MediaLocationCandidate, MediaOrigin,
    PeriodGranularity, TemporalCorrelationCandidate, TemporalMode,
)


NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def test_period_modes_have_one_unambiguous_shape():
    period = InsightPeriod(mode=TemporalMode.PERIOD, granularity=PeriodGranularity.MONTH, from_at=NOW, to_at=NOW + timedelta(days=31))
    point = InsightPeriod(mode=TemporalMode.POINT_IN_TIME, granularity=PeriodGranularity.DAY, point_at=NOW)
    assert period.from_at == NOW and point.point_at == NOW
    with pytest.raises(ValidationError):
        InsightPeriod(mode=TemporalMode.PERIOD, granularity=PeriodGranularity.MONTH, point_at=NOW)
    with pytest.raises(ValidationError):
        InsightPeriod(mode=TemporalMode.POINT_IN_TIME, granularity=PeriodGranularity.DAY, point_at=NOW, from_at=NOW)


def _media(origin: MediaOrigin, basis: LocationBasis, evidence_class: LocationEvidenceClass):
    return MediaLocationCandidate(
        insight_id=uuid4(), detector_id="fixture", detector_version="1",
        artifact_id=uuid4(), temporal_precision="SECOND", lat=51.5, lon=-0.1,
        basis=basis, confidence=0.8, evidence_class=evidence_class, media_origin=origin,
    )


def test_media_contract_prevents_content_from_becoming_presence():
    for origin in (MediaOrigin.SCREENSHOT, MediaOrigin.DOWNLOADED_MEDIA, MediaOrigin.GENERATED_MEDIA):
        with pytest.raises(ValidationError):
            _media(origin, LocationBasis.EXIF_GPS, LocationEvidenceClass.STRONG_OBSERVATION)
    with pytest.raises(ValidationError):
        _media(MediaOrigin.CAMERA_ORIGIN, LocationBasis.VISUAL_LANDMARK, LocationEvidenceClass.STRONG_OBSERVATION)
    assert _media(MediaOrigin.CAMERA_ORIGIN, LocationBasis.EXIF_GPS, LocationEvidenceClass.STRONG_OBSERVATION).evidence_class is LocationEvidenceClass.STRONG_OBSERVATION


def _correlation(status: CorrelationStatus, *, exposure=False, statement=False):
    evidence = (InsightEvidenceRef(kind=EvidenceKind.ACTIVITY_EVENT, ref_id=uuid4(), role="exposure"),) if exposure else ()
    return TemporalCorrelationCandidate(
        insight_id=uuid4(), detector_id="fixture", detector_version="1",
        local_change_id=uuid4(), external_event_id=uuid4(), temporal_proximity=1.0,
        semantic_relevance=0.9, user_exposure_evidence=evidence,
        direct_user_statement=statement, preceding_related_activity=exposure,
        behavioural_persistence=1.0, competing_explanations_count=0,
        status=status, causal_claim=False,
    )


def test_correlation_contract_never_promotes_timing_to_evidence_or_cause():
    coincidence = _correlation(CorrelationStatus.COINCIDENCE_CANDIDATE)
    assert coincidence.causal_claim is False
    with pytest.raises(ValidationError):
        _correlation(CorrelationStatus.EVIDENCE_SUPPORTED_RELATION)
    assert _correlation(CorrelationStatus.EVIDENCE_SUPPORTED_RELATION, exposure=True).causal_claim is False
    with pytest.raises(ValidationError):
        _correlation(CorrelationStatus.USER_CONFIRMED, exposure=True)
    assert _correlation(CorrelationStatus.USER_CONFIRMED, exposure=True, statement=True).status is CorrelationStatus.USER_CONFIRMED
