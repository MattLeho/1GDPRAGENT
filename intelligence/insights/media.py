"""Deterministic media-location interpretation with physical-presence guards."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping
from uuid import UUID, uuid5
import hashlib
import re

from .models import (
    EvidenceKind,
    InsightEvidenceRef,
    LocationBasis,
    LocationEvidenceClass,
    MediaAnalysisMode,
    MediaLocationCandidate,
    MediaContentCandidate,
    MediaOrigin,
    PlaceInsight,
    ProjectEpisodeView,
)


DETECTOR_ID = "task4.media_location"
DETECTOR_VERSION = "1.0.0"
_NAMESPACE = UUID("20a66934-96c0-41e5-94fd-5a1457e0d9fb")
_DOMAIN = re.compile(r"\b(?:https?://)?(?:www\.)?([a-z0-9-]+(?:\.[a-z0-9-]+)+)\b",re.I)
_KNOWN_SERVICES = ("chatgpt","github","google","gmail","youtube","slack","teams","notion","figma","reddit","linkedin","facebook","instagram","x.com")
_INTERFACE_WORDS = ("browser","dashboard","settings","search","inbox","editor","terminal","menu","dialog","toolbar")


@dataclass(frozen=True, slots=True)
class MediaOriginResult:
    origin: MediaOrigin
    confidence: float
    calculated_features: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("origin confidence must be between zero and one")


@dataclass(frozen=True, slots=True)
class LocationObservation:
    basis: LocationBasis
    evidence_locator_id: UUID
    evidence_artifact_id: UUID | None = None
    occurred_at: datetime | None = None
    temporal_precision: str = "UNKNOWN"
    location_type: str | None = None
    lat: float | None = None
    lon: float | None = None
    place_label: str | None = None
    confidence: float = 0.0
    credible_original_capture_time: bool = False
    reviewed_by: str | None = None
    rejected: bool = False


@dataclass(frozen=True, slots=True)
class VisualTaskRequest:
    """Description for later Task Router submission; this module never calls a provider."""

    task_key: str
    artifact_id: UUID
    evidence_locator_id: UUID
    purpose: str


def classify_media_origin(
    metadata: Mapping[str, Any], *, original_path: str = "",
    routed_result: Mapping[str, Any] | None = None,
) -> MediaOriginResult:
    """Consume a routed result or apply the same conservative metadata rules.

    A routed classifier result remains a candidate. Metadata fallback is local
    and deterministic; unknown is preserved rather than guessed.
    """
    software = str(metadata.get("software") or "").casefold()
    device = metadata.get("device") if isinstance(metadata.get("device"), Mapping) else {}
    path = original_path.casefold().replace("\\", "/")
    dimensions = metadata.get("dimensions") if isinstance(metadata.get("dimensions"),Mapping) else {}
    width=int(dimensions.get("width") or metadata.get("width") or 0)
    height=int(dimensions.get("height") or metadata.get("height") or 0)
    common_screen_geometry=(width,height) in {
        (1280,720),(1366,768),(1440,900),(1536,864),(1920,1080),(2560,1440),(3840,2160),
    }
    source_hint=str(metadata.get("source_uri") or metadata.get("downloaded_from") or "").casefold()
    generated = ("stable diffusion","midjourney","dall-e","comfyui","automatic1111","firefly")
    if any(marker in software for marker in generated):
        origin, confidence = MediaOrigin.GENERATED_MEDIA, 0.95
    elif "screenshot" in path or "screen shot" in path or "snipping tool" in software or (
        common_screen_geometry and not device and not metadata.get("capture_timestamp")
    ):
        origin, confidence = MediaOrigin.SCREENSHOT, 0.92
    elif device and metadata.get("capture_timestamp"):
        origin, confidence = MediaOrigin.CAMERA_ORIGIN, 0.94
    elif software:
        origin, confidence = MediaOrigin.EDITED_MEDIA, 0.72
    elif "/download" in path or path.startswith("downloads/") or bool(source_hint):
        origin, confidence = MediaOrigin.DOWNLOADED_MEDIA, 0.65
    else:
        origin, confidence = MediaOrigin.UNKNOWN, 0.25
    features = {
        "device_metadata_present":bool(device), "capture_time_present":bool(metadata.get("capture_timestamp")),
        "software":metadata.get("software"), "original_path_hint":original_path,
        "width":width or None,"height":height or None,"common_screen_geometry":common_screen_geometry,
        "download_source_hint_present":bool(source_hint),
        "deterministic_origin":origin.value,
        "camera_origin_corroborated":origin is MediaOrigin.CAMERA_ORIGIN,
        "routed_origin":None,
        "origin_conflict":False,
    }
    if not routed_result or not routed_result.get("origin"):
        return MediaOriginResult(origin=origin, confidence=confidence, calculated_features=features)

    try:
        routed_origin = MediaOrigin(str(routed_result["origin"]))
    except ValueError:
        routed_origin = MediaOrigin.UNKNOWN
    routed_confidence = max(0.0,min(1.0,float(routed_result.get("confidence",0.0))))
    conflict = routed_origin is not MediaOrigin.UNKNOWN and routed_origin is not origin
    features.update({
        "routed_origin":routed_origin.value,
        "routed_origin_confidence":routed_confidence,
        "routed_features":dict(routed_result.get("features") or {}),
        "origin_conflict":conflict,
    })
    if routed_origin is MediaOrigin.CAMERA_ORIGIN:
        # A model label cannot create camera provenance; deterministic capture
        # metadata must independently agree.
        resolved = origin if origin is MediaOrigin.CAMERA_ORIGIN else origin
    elif origin is MediaOrigin.CAMERA_ORIGIN and routed_origin is not MediaOrigin.CAMERA_ORIGIN:
        # Conflicting screenshot/download classifications are kept conservative.
        resolved = routed_origin if routed_origin is not MediaOrigin.UNKNOWN else MediaOrigin.UNKNOWN
    elif origin is MediaOrigin.UNKNOWN:
        resolved = routed_origin
    elif routed_origin in {MediaOrigin.SCREENSHOT,MediaOrigin.DOWNLOADED_MEDIA,MediaOrigin.GENERATED_MEDIA}:
        resolved = routed_origin
    elif conflict:
        resolved = MediaOrigin.UNKNOWN
    else:
        resolved = origin
    features["camera_origin_corroborated"] = (
        resolved is MediaOrigin.CAMERA_ORIGIN and origin is MediaOrigin.CAMERA_ORIGIN
    )
    resolved_confidence = confidence if resolved is origin else routed_confidence
    return MediaOriginResult(origin=resolved, confidence=resolved_confidence, calculated_features=features)


def visual_task_requests(
    artifact_id: UUID,
    evidence_locator_id: UUID,
    mode: MediaAnalysisMode = MediaAnalysisMode.METADATA_ONLY,
    origin: MediaOriginResult | None = None,
) -> tuple[VisualTaskRequest, ...]:
    if mode is MediaAnalysisMode.METADATA_ONLY:
        return ()
    if mode is MediaAnalysisMode.FULL_VISUAL:
        keys = ("image.origin_classification", "image.ocr", "image.caption", "image.landmark_candidate")
    elif origin is None:
        keys = ("image.origin_classification",)
    elif origin.origin is MediaOrigin.SCREENSHOT:
        keys = ("image.ocr","image.caption")
    elif origin.origin is MediaOrigin.UNKNOWN or origin.confidence < 0.7:
        keys = ("image.landmark_candidate",)
    else:
        keys = ()
    return tuple(VisualTaskRequest(
        task_key=key,
        artifact_id=artifact_id,
        evidence_locator_id=evidence_locator_id,
        purpose="Return a reviewable media candidate; do not assert physical presence.",
    ) for key in keys)


def create_media_content_candidate(
    *, artifact_id: UUID, evidence_locator_id: UUID,
    origin: MediaOriginResult, task_outputs: Mapping[str, Mapping[str, Any]],
    analysis_run_id: UUID | None = None,
) -> MediaContentCandidate:
    """Summarise routed screenshot outputs without exposing raw OCR in overview APIs."""
    ocr = task_outputs.get("image.ocr", {})
    caption = task_outputs.get("image.caption", {})
    text = str(ocr.get("text") or "")
    lowered = text.casefold()
    words = ocr.get("words") if isinstance(ocr.get("words"),list) else []
    applications = tuple(sorted({name for name in _KNOWN_SERVICES if name in lowered}))
    interfaces = tuple(sorted({name for name in _INTERFACE_WORDS if name in lowered}))
    webpages = tuple(sorted({match.group(1).casefold() for match in _DOMAIN.finditer(text)}))
    services = tuple(sorted(set(applications) | {domain.split(".")[0] for domain in webpages}))
    topics = tuple(sorted({str(value) for output in task_outputs.values() for value in (output.get("topics") or ()) if str(value).strip()}))
    entities = tuple(sorted({str(value) for output in task_outputs.values() for value in (output.get("entities") or ()) if str(value).strip()}))
    identity = uuid5(_NAMESPACE,f"content:{artifact_id}:{evidence_locator_id}:{DETECTOR_VERSION}")
    evidence = (
        InsightEvidenceRef(kind=EvidenceKind.SOURCE_ARTIFACT,ref_id=artifact_id,artifact_id=artifact_id),
        InsightEvidenceRef(kind=EvidenceKind.EVIDENCE_LOCATOR,ref_id=evidence_locator_id,
                           artifact_id=artifact_id,locator_id=evidence_locator_id),
    )
    return MediaContentCandidate(
        insight_id=identity,detector_id="task4.media_content",detector_version=DETECTOR_VERSION,
        analysis_run_id=analysis_run_id,calculated_features={
            "task_keys":tuple(sorted(task_outputs)),"raw_ocr_hidden":True,
            "physical_presence_supported":False,
        },evidence=evidence,artifact_id=artifact_id,evidence_locator_id=evidence_locator_id,
        media_origin=origin.origin,ocr_word_count=len(words) if words else len(text.split()),
        ocr_text_fingerprint=(hashlib.sha256(" ".join(lowered.split()).encode()).hexdigest()[:16] if text else None),
        application_candidates=applications,interface_candidates=interfaces,
        webpage_candidates=webpages,service_candidates=services,
        visible_topic_candidates=topics,visible_entity_candidates=entities,
        caption_available=bool(caption.get("text")),
    )


def create_location_candidate(
    artifact_id: UUID,
    origin: MediaOriginResult,
    observation: LocationObservation,
    *,
    analysis_run_id: UUID | None = None,
) -> MediaLocationCandidate:
    if (observation.lat is None) != (observation.lon is None):
        raise ValueError("latitude and longitude must be supplied together")
    if observation.basis in {LocationBasis.EXIF_GPS, LocationBasis.TAKEOUT_SIDECAR} and observation.lat is None:
        raise ValueError("GPS and sidecar location observations require coordinates")
    if observation.basis is LocationBasis.VISUAL_LANDMARK and not observation.place_label:
        raise ValueError("visual landmark observations require a place label")
    if observation.basis is LocationBasis.USER_CONFIRMED and not observation.reviewed_by:
        raise ValueError("user-confirmed locations require reviewed_by")

    if observation.rejected:
        evidence_class = LocationEvidenceClass.REJECTED
    elif observation.basis is LocationBasis.USER_CONFIRMED:
        evidence_class = LocationEvidenceClass.USER_CONFIRMED
    elif (
        observation.basis in {LocationBasis.EXIF_GPS, LocationBasis.TAKEOUT_SIDECAR}
        and observation.credible_original_capture_time
        and origin.origin is MediaOrigin.CAMERA_ORIGIN
        and origin.calculated_features.get("camera_origin_corroborated") is True
    ):
        evidence_class = LocationEvidenceClass.STRONG_OBSERVATION
    else:
        evidence_class = LocationEvidenceClass.CANDIDATE

    candidate_id = uuid5(
        _NAMESPACE,
        f"{artifact_id}:{observation.evidence_locator_id}:{observation.basis.value}:"
        f"{observation.occurred_at}:{observation.lat}:{observation.lon}:{observation.place_label}:"
        f"{observation.reviewed_by}:{observation.rejected}:{DETECTOR_VERSION}",
    )
    locator_ref = InsightEvidenceRef(
        kind=EvidenceKind.EVIDENCE_LOCATOR,
        ref_id=observation.evidence_locator_id,
        artifact_id=observation.evidence_artifact_id or artifact_id,
        role="user_confirmation" if evidence_class is LocationEvidenceClass.USER_CONFIRMED else "supporting",
        occurred_at=observation.occurred_at,
        weight=observation.confidence,
    )
    artifact_ref = InsightEvidenceRef(
        kind=EvidenceKind.SOURCE_ARTIFACT,
        ref_id=artifact_id,
        artifact_id=artifact_id,
        occurred_at=observation.occurred_at,
        weight=origin.confidence,
    )
    return MediaLocationCandidate(
        insight_id=candidate_id,
        detector_id=DETECTOR_ID,
        detector_version=DETECTOR_VERSION,
        analysis_run_id=analysis_run_id,
        calculated_features={
            "origin_confidence": origin.confidence,
            "origin_features": dict(origin.calculated_features),
            "evidence_locator_id": str(observation.evidence_locator_id),
            "credible_original_capture_time": observation.credible_original_capture_time,
        },
        evidence=(artifact_ref, locator_ref),
        artifact_id=artifact_id,
        occurred_at=observation.occurred_at,
        temporal_precision=observation.temporal_precision,
        location_type=observation.location_type,
        lat=observation.lat,
        lon=observation.lon,
        place_label=observation.place_label,
        basis=observation.basis,
        confidence=observation.confidence,
        evidence_class=evidence_class,
        media_origin=origin.origin,
        reviewed_by=observation.reviewed_by,
    )


def create_location_candidates(
    artifact_id: UUID,
    origin: MediaOriginResult,
    observations: Iterable[LocationObservation],
    *,
    analysis_run_id: UUID | None = None,
) -> tuple[MediaLocationCandidate, ...]:
    return tuple(create_location_candidate(
        artifact_id, origin, observation, analysis_run_id=analysis_run_id
    ) for observation in observations)


def aggregate_places(candidates: Iterable[MediaLocationCandidate]) -> tuple[dict[str, Any], ...]:
    """Group candidates without collapsing their evidence classes or confidence."""

    groups: dict[str, list[MediaLocationCandidate]] = defaultdict(list)
    for candidate in candidates:
        if candidate.place_label:
            key = f"label:{candidate.place_label.casefold().strip()}"
        elif candidate.lat is not None and candidate.lon is not None:
            key = f"coordinates:{candidate.lat:.3f},{candidate.lon:.3f}"
        else:
            key = f"candidate:{candidate.insight_id}"
        groups[key].append(candidate)

    aggregates: list[dict[str, Any]] = []
    for key, items in sorted(groups.items()):
        classes = Counter(item.evidence_class.value for item in items)
        aggregates.append({
            "place_key": key,
            "place_label": next((item.place_label for item in items if item.place_label), None),
            "observation_count": len(items),
            "evidence_class_counts": dict(sorted(classes.items())),
            "confidence_values": tuple(item.confidence for item in items),
            "candidate_ids": tuple(str(item.insight_id) for item in items),
            "presence_supported_count": sum(
                item.evidence_class in {LocationEvidenceClass.STRONG_OBSERVATION, LocationEvidenceClass.USER_CONFIRMED}
                for item in items
            ),
        })
    return tuple(aggregates)


def _place_key(candidate: MediaLocationCandidate) -> str:
    if candidate.place_label:
        return f"label:{candidate.place_label.casefold().strip()}"
    if candidate.lat is not None and candidate.lon is not None:
        return f"coordinates:{candidate.lat:.3f},{candidate.lon:.3f}"
    return f"candidate:{candidate.insight_id}"


def _presence_observations(
    candidates: Iterable[MediaLocationCandidate],
) -> tuple[MediaLocationCandidate, ...]:
    return tuple(sorted(
        (
            candidate for candidate in candidates
            if candidate.occurred_at is not None
            and candidate.evidence_class in {
                LocationEvidenceClass.STRONG_OBSERVATION,
                LocationEvidenceClass.USER_CONFIRMED,
            }
        ),
        key=lambda candidate: (candidate.occurred_at, str(candidate.insight_id)),
    ))


def _activity_centre_changes(
    observations: tuple[MediaLocationCandidate, ...],
) -> tuple[dict[str, Any], ...]:
    """Detect only changes in the dominant observed place per UTC month.

    This is an observed activity-centre shift, never a HOME inference.
    Candidate-only media is excluded before this function is called.
    """
    by_month: dict[str, list[MediaLocationCandidate]] = defaultdict(list)
    for observation in observations:
        by_month[observation.occurred_at.strftime("%Y-%m")].append(observation)
    dominant: list[tuple[str, str, int]] = []
    for month, items in sorted(by_month.items()):
        counts = Counter(_place_key(item) for item in items)
        place_key, count = sorted(counts.items(), key=lambda value: (-value[1], value[0]))[0]
        dominant.append((month, place_key, count))
    return tuple(
        {
            "from_period": previous[0],
            "to_period": current[0],
            "from_place_key": previous[1],
            "to_place_key": current[1],
            "from_observation_count": previous[2],
            "to_observation_count": current[2],
            "classification": "observed_activity_centre_shift",
            "home_inference": False,
        }
        for previous, current in zip(dominant, dominant[1:])
        if previous[1] != current[1]
    )


def _travel_periods(
    observations: tuple[MediaLocationCandidate, ...],
) -> tuple[dict[str, Any], ...]:
    """Return reviewable non-primary-place runs backed by at least two observations."""
    counts = Counter(_place_key(item) for item in observations)
    if len(counts) < 2:
        return ()
    primary = sorted(counts.items(), key=lambda value: (-value[1], value[0]))[0][0]
    away = [item for item in observations if _place_key(item) != primary]
    runs: list[list[MediaLocationCandidate]] = []
    for item in away:
        if not runs or item.occurred_at - runs[-1][-1].occurred_at > timedelta(days=3):
            runs.append([item])
        else:
            runs[-1].append(item)
    return tuple(
        {
            "start_at": run[0].occurred_at,
            "end_at": run[-1].occurred_at,
            "place_keys": tuple(sorted({_place_key(item) for item in run})),
            "evidence_count": len(run),
            "classification": "travel_period_candidate",
            "primary_activity_centre_key": primary,
            "home_inference": False,
        }
        for run in runs if len(run) >= 2
    )


def _place_linked_projects(
    observations: tuple[MediaLocationCandidate, ...],
    project_episodes: Iterable[ProjectEpisodeView],
) -> tuple[dict[str, Any], ...]:
    links = []
    for episode in project_episodes:
        matching = tuple(
            item for item in observations
            if episode.start_at <= item.occurred_at <= episode.end_at
        )
        if not matching:
            continue
        links.append({
            "project_insight_id": str(episode.insight_id),
            "start_at": episode.start_at,
            "end_at": episode.end_at,
            "place_keys": tuple(sorted({_place_key(item) for item in matching})),
            "location_evidence_count": len(matching),
            "classification": "temporal_place_project_link",
            "causal_claim": False,
        })
    return tuple(links)


def build_place_insight(
    candidates: Iterable[MediaLocationCandidate],
    *,
    insight_id: UUID,
    analysis_run_id: UUID | None = None,
    project_episodes: Iterable[ProjectEpisodeView] = (),
    media_content_candidates: Iterable[MediaContentCandidate] = (),
) -> PlaceInsight:
    candidate_tuple = tuple(candidates)
    content_tuple = tuple(media_content_candidates)
    aggregates = aggregate_places(candidate_tuple)
    presence = _presence_observations(candidate_tuple)
    recurrent = tuple(item for item in aggregates if item["presence_supported_count"] > 1)
    new = tuple(item for item in aggregates if item["presence_supported_count"] == 1)
    return PlaceInsight(
        insight_id=insight_id,
        detector_id="task4.place_aggregate",
        detector_version=DETECTOR_VERSION,
        analysis_run_id=analysis_run_id,
        calculated_features={"candidate_count": len(candidate_tuple)},
        evidence=tuple(ref for candidate in candidate_tuple for ref in candidate.evidence)
                 + tuple(ref for candidate in content_tuple for ref in candidate.evidence),
        recurrent_places=recurrent,
        new_places=new,
        activity_centre_changes=_activity_centre_changes(presence),
        travel_periods=_travel_periods(presence),
        place_linked_project_episodes=_place_linked_projects(presence, project_episodes),
        media_content_candidates=content_tuple,
        candidates=candidate_tuple,
    )
