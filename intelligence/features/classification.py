"""Deterministic service/path and privacy data-class candidate detectors."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable
from uuid import UUID

from ingestion.models import (
    ActivityEvent,
    FeatureCandidate,
    FeatureCandidateStatus,
    PrivacyDataClass,
)

from .dictionaries import KeyCategory, match_schema_keys, normalize_schema_key


DETECTOR_VERSION = "1.0.0"


def _tokens(value: str | None) -> frozenset[str]:
    if not value:
        return frozenset()
    normalized = normalize_schema_key(value)
    return frozenset(part for part in normalized.split("_") if part)


@dataclass(frozen=True, slots=True)
class ServicePathRule:
    rule_id: str
    service: str
    required_tokens: frozenset[str]
    data_domain: str | None = None
    data_classes: tuple[PrivacyDataClass, ...] = ()

    def matches(self, path_tokens: frozenset[str]) -> bool:
        return self.required_tokens <= path_tokens


SERVICE_PATH_RULES: tuple[ServicePathRule, ...] = (
    ServicePathRule("google-takeout", "google", frozenset({"takeout"})),
    ServicePathRule("youtube", "youtube", frozenset({"youtube"}), "media", (PrivacyDataClass.CONTENT_CONSUMPTION, PrivacyDataClass.MEDIA)),
    ServicePathRule("google-search", "google_search", frozenset({"my", "activity", "search"}), "search_history", (PrivacyDataClass.SEARCH_HISTORY, PrivacyDataClass.BEHAVIOURAL_EVENT)),
    ServicePathRule("google-search-service", "google_search", frozenset({"google", "search"}), "search_history", (PrivacyDataClass.SEARCH_HISTORY, PrivacyDataClass.BEHAVIOURAL_EVENT)),
    ServicePathRule("gmail", "gmail", frozenset({"gmail"}), "communication", (PrivacyDataClass.COMMUNICATION,)),
    ServicePathRule("google-maps", "google_maps", frozenset({"maps"}), "location", (PrivacyDataClass.LOCATION,)),
    ServicePathRule("chrome", "chrome", frozenset({"chrome"}), "browser_history", (PrivacyDataClass.BEHAVIOURAL_EVENT,)),
    ServicePathRule("facebook", "facebook", frozenset({"facebook"}), "social", (PrivacyDataClass.SOCIAL_INTERACTION,)),
    ServicePathRule("instagram", "instagram", frozenset({"instagram"}), "social", (PrivacyDataClass.SOCIAL_INTERACTION, PrivacyDataClass.MEDIA)),
    ServicePathRule("linkedin", "linkedin", frozenset({"linkedin"}), "social", (PrivacyDataClass.SOCIAL_INTERACTION,)),
    ServicePathRule("spotify", "spotify", frozenset({"spotify"}), "media", (PrivacyDataClass.CONTENT_CONSUMPTION, PrivacyDataClass.MEDIA)),
    ServicePathRule("netflix", "netflix", frozenset({"netflix"}), "media", (PrivacyDataClass.CONTENT_CONSUMPTION, PrivacyDataClass.MEDIA)),
    ServicePathRule("amazon-orders", "amazon", frozenset({"amazon", "orders"}), "commerce", (PrivacyDataClass.PURCHASE,)),
    ServicePathRule("microsoft", "microsoft", frozenset({"microsoft"})),
    ServicePathRule("apple", "apple", frozenset({"apple"})),
)


def _source_refs(
    source_event_ids: Iterable[UUID], source_artifact_ids: Iterable[UUID]
) -> tuple[tuple[UUID, ...], tuple[UUID, ...]]:
    events = tuple(dict.fromkeys(source_event_ids))
    artifacts = tuple(dict.fromkeys(source_artifact_ids))
    if not events and not artifacts:
        raise ValueError("classification requires a source event or artefact reference")
    return events, artifacts


def classify_service_path(
    path: str,
    *,
    source_event_ids: Iterable[UUID] = (),
    source_artifact_ids: Iterable[UUID] = (),
    rules: tuple[ServicePathRule, ...] = SERVICE_PATH_RULES,
) -> FeatureCandidate:
    """Classify distinctive path tokens, preserving conflicts and unknown paths."""

    events, artifacts = _source_refs(source_event_ids, source_artifact_ids)
    clean_path = PurePosixPath(path.replace("\\", "/")).as_posix()
    path_tokens = _tokens(clean_path)
    matches = tuple(rule for rule in rules if rule.matches(path_tokens))
    services = sorted({rule.service for rule in matches})
    # A parent Google Takeout token is compatible with a specific Google product.
    material_services = [service for service in services if service != "google"] or services
    if not matches:
        status = FeatureCandidateStatus.UNKNOWN
        confidence = 0.0
    elif len(material_services) > 1:
        status = FeatureCandidateStatus.AMBIGUOUS
        confidence = 0.5
    else:
        status = FeatureCandidateStatus.DETERMINISTIC
        confidence = 1.0
    classes = sorted({item.value for rule in matches for item in rule.data_classes})
    return FeatureCandidate(
        feature_type="service_path_classification",
        detector_id="privacy.service-path",
        detector_version=DETECTOR_VERSION,
        source_event_ids=events,
        source_artifact_ids=artifacts,
        calculated_values={
            "path": clean_path,
            "service_candidates": material_services,
            "data_domain_candidates": sorted({rule.data_domain for rule in matches if rule.data_domain}),
            "data_class_candidates": classes,
            "matched_rule_ids": [rule.rule_id for rule in matches],
            "semantic_adjudication_eligible": status in {FeatureCandidateStatus.UNKNOWN, FeatureCandidateStatus.AMBIGUOUS},
        },
        confidence=confidence,
        rule_result=bool(matches),
        candidate_status=status,
    )


_SIGNALS: dict[PrivacyDataClass, frozenset[str]] = {
    PrivacyDataClass.DIRECT_IDENTIFIER: frozenset({"email", "email_address", "phone", "phone_number", "full_name", "account_id", "profile_id"}),
    PrivacyDataClass.QUASI_IDENTIFIER: frozenset({"birth_date", "date_of_birth", "postcode", "postal_code", "ip_address", "age"}),
    PrivacyDataClass.CONTACT: frozenset({"contact", "contacts", "address_book"}),
    PrivacyDataClass.LOCATION: frozenset({"location", "latitude", "longitude", "coordinates", "address", "postcode", "city", "country", "place"}),
    PrivacyDataClass.COMMUNICATION: frozenset({"message", "messages", "email", "mail", "chat", "conversation", "call"}),
    PrivacyDataClass.SOCIAL_INTERACTION: frozenset({"follower", "following", "friend", "member", "participant", "shared_with"}),
    PrivacyDataClass.BEHAVIOURAL_EVENT: frozenset({"activity", "event", "history", "interaction", "action"}),
    PrivacyDataClass.SEARCH_HISTORY: frozenset({"search", "query", "searched"}),
    PrivacyDataClass.CONTENT_CONSUMPTION: frozenset({"watch", "watched", "listen", "listened", "viewed", "played", "consumed"}),
    PrivacyDataClass.PURCHASE: frozenset({"purchase", "order", "orders", "checkout"}),
    PrivacyDataClass.PAYMENT: frozenset({"payment", "card", "billing", "transaction"}),
    PrivacyDataClass.DEVICE: frozenset({"device", "device_id", "hardware", "imei", "serial_number"}),
    PrivacyDataClass.AUTHENTICATION: frozenset({"login", "logout", "authentication", "session", "credential"}),
    PrivacyDataClass.SECURITY_EVENT: frozenset({"security", "breach", "failed_login", "alert", "mfa", "two_factor"}),
    PrivacyDataClass.ADVERTISEMENT: frozenset({"advertising", "advertisement", "ad_id", "campaign", "audience"}),
    PrivacyDataClass.INFERRED_ATTRIBUTE: frozenset({"inferred", "prediction", "propensity", "affinity", "segment", "interest", "model_output"}),
    PrivacyDataClass.DECLARED_ATTRIBUTE: frozenset({"declared", "self_reported", "profile_answer", "preference"}),
    PrivacyDataClass.BIOMETRIC_CANDIDATE: frozenset({"biometric", "faceprint", "fingerprint", "voiceprint", "face_embedding"}),
    PrivacyDataClass.MEDIA: frozenset({"image", "photo", "video", "audio", "media"}),
    PrivacyDataClass.DOCUMENT: frozenset({"document", "pdf", "spreadsheet", "presentation", "file"}),
}


def classify_data_classes(
    *,
    schema_keys: Iterable[str] = (),
    path: str | None = None,
    service: str | None = None,
    data_domain: str | None = None,
    event_type: str | None = None,
    object_type: str | None = None,
    epistemic_hints: Iterable[str] = (),
    source_event_ids: Iterable[UUID] = (),
    source_artifact_ids: Iterable[UUID] = (),
) -> FeatureCandidate:
    """Emit one grounded, multi-label data-class candidate."""

    events, artifacts = _source_refs(source_event_ids, source_artifact_ids)
    keys = tuple(str(key) for key in schema_keys)
    dictionary_matches = match_schema_keys(keys)
    normalized_signals = {normalize_schema_key(key) for key in keys}
    for value in (path, service, data_domain, event_type, object_type):
        if value:
            normalized_signals.add(normalize_schema_key(value))
            normalized_signals.update(_tokens(value))
    normalized_signals.update(normalize_schema_key(hint) for hint in epistemic_hints)

    matched: dict[PrivacyDataClass, set[str]] = {}
    for data_class, signals in _SIGNALS.items():
        evidence = signals & normalized_signals
        if evidence:
            matched[data_class] = set(evidence)

    categories = {match.category for match in dictionary_matches}
    if KeyCategory.LOCATION in categories:
        matched.setdefault(PrivacyDataClass.LOCATION, set()).add("schema-key-dictionary")
    if KeyCategory.RELATIONSHIP in categories:
        matched.setdefault(PrivacyDataClass.SOCIAL_INTERACTION, set()).add("schema-key-dictionary")
    if KeyCategory.INFERENCE_LANGUAGE in categories:
        matched.setdefault(PrivacyDataClass.INFERRED_ATTRIBUTE, set()).add("schema-key-dictionary")

    if matched:
        classes = sorted(data_class.value for data_class in matched)
        status = FeatureCandidateStatus.DETERMINISTIC
        confidence = 1.0
    else:
        classes = [PrivacyDataClass.UNKNOWN.value]
        status = FeatureCandidateStatus.UNKNOWN
        confidence = 0.0

    return FeatureCandidate(
        feature_type="privacy_data_class_candidate",
        detector_id="privacy.data-class",
        detector_version=DETECTOR_VERSION,
        source_event_ids=events,
        source_artifact_ids=artifacts,
        calculated_values={
            "data_classes": classes,
            "matched_signals": {
                data_class.value: sorted(signals) for data_class, signals in sorted(matched.items(), key=lambda item: item[0].value)
            },
            "key_dictionary_matches": [
                {
                    "key": match.original_key,
                    "category": match.category.value,
                    "dictionary_id": match.dictionary_id,
                    "dictionary_version": match.dictionary_version,
                }
                for match in dictionary_matches
            ],
            "semantic_adjudication_eligible": status is FeatureCandidateStatus.UNKNOWN,
        },
        confidence=confidence,
        rule_result=bool(matched),
        candidate_status=status,
    )


class ServicePathDataClassDetector:
    """Pipeline adapter that derives service/path and data-class candidates."""

    detector_id = "privacy.service-path-data-class"
    detector_version = DETECTOR_VERSION

    def __init__(self, artifact_paths: dict[UUID, str] | None = None) -> None:
        self._artifact_paths = dict(artifact_paths or {})

    def detect(self, events: tuple[ActivityEvent, ...]) -> tuple[FeatureCandidate, ...]:
        candidates: list[FeatureCandidate] = []
        for event in events:
            path = self._artifact_paths.get(event.artifact_id)
            if path or event.service or event.product:
                service_candidate = classify_service_path(
                    " / ".join(value for value in (path, event.service, event.product) if value),
                    source_event_ids=(event.event_id,),
                )
                candidates.append(service_candidate.model_copy(update={
                    "detector_id": self.detector_id,
                    "detector_version": self.detector_version,
                }))
            schema_keys = tuple(event.identifiers) + tuple(event.locations) + tuple(event.relationships)
            data_class_candidate = classify_data_classes(
                schema_keys=schema_keys,
                path=path,
                service=event.service,
                data_domain=event.data_domain,
                event_type=event.event_type,
                object_type=event.object_type,
                epistemic_hints=event.epistemic_hints.values(),
                source_event_ids=(event.event_id,),
            )
            candidates.append(data_class_candidate.model_copy(update={
                "detector_id": self.detector_id,
                "detector_version": self.detector_version,
            }))
        return tuple(candidates)
