"""Context-aware identifier detection and aggregate opaque-token analysis."""

from __future__ import annotations

import hashlib
import ipaddress
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable
from urllib.parse import parse_qsl, unquote, urlsplit
from uuid import UUID

from ingestion.models import ActivityEvent, FeatureCandidate, FeatureCandidateStatus, OpaqueIdentifierCandidate

from .dictionaries import normalize_schema_key


DETECTOR_VERSION = "1.0.0"


class IdentifierType(str, Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    USERNAME = "USERNAME"
    ACCOUNT_ID = "ACCOUNT_ID"
    DEVICE_ID = "DEVICE_ID"
    ADVERTISING_ID = "ADVERTISING_ID"
    COOKIE_ID = "COOKIE_ID"
    PROFILE_ID = "PROFILE_ID"
    PAYMENT_CUSTOMER_ID = "PAYMENT_CUSTOMER_ID"
    IP = "IP"
    MAC = "MAC"
    URL_CARRIED_IDENTIFIER = "URL_CARRIED_IDENTIFIER"
    OPAQUE_RECURRING_TOKEN = "OPAQUE_RECURRING_TOKEN"


@dataclass(frozen=True, slots=True)
class IdentifierObservation:
    value: str
    key: str | None = None
    source_event_id: UUID | None = None
    source_artifact_id: UUID | None = None
    service: str | None = None
    domain: str | None = None
    schema_id: str | None = None
    seen_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.source_event_id is None and self.source_artifact_id is None:
            raise ValueError("identifier observations require an event or artefact reference")


@dataclass(frozen=True, slots=True)
class DetectedIdentifier:
    identifier_type: IdentifierType
    normalized_value: str | None
    token_hash: str
    matched_rule: str
    assigned_meaning: None = None


_EMAIL = re.compile(r"[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?(?:\.[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?)+", re.IGNORECASE)
_MAC = re.compile(r"(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}")
_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}")
_OPAQUE = re.compile(r"[A-Za-z0-9_-]{12,128}")

_CONTEXT_TYPES: dict[IdentifierType, frozenset[str]] = {
    IdentifierType.USERNAME: frozenset({"username", "user_name", "handle", "screen_name"}),
    IdentifierType.ACCOUNT_ID: frozenset({"account_id", "accountid", "user_id", "userid", "member_id"}),
    IdentifierType.DEVICE_ID: frozenset({"device_id", "deviceid", "imei", "serial_number", "hardware_id"}),
    IdentifierType.ADVERTISING_ID: frozenset({"advertising_id", "advertiser_id", "ad_id", "gaid", "idfa"}),
    IdentifierType.COOKIE_ID: frozenset({"cookie_id", "cookieid", "visitor_id", "browser_id"}),
    IdentifierType.PROFILE_ID: frozenset({"profile_id", "profileid"}),
    IdentifierType.PAYMENT_CUSTOMER_ID: frozenset({"payment_id", "customer_id", "customerid", "billing_id", "transaction_id"}),
}
_URL_ID_KEYS = frozenset(key for keys in _CONTEXT_TYPES.values() for key in keys) | frozenset({"id", "identifier", "uid", "sid", "cid", "token"})
_PATH_ID_PARENTS = frozenset({"user", "users", "account", "accounts", "profile", "profiles", "device", "devices", "customer", "customers"})


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def shannon_entropy(value: str) -> float:
    """Shannon entropy in bits per character."""

    if not value:
        return 0.0
    counts = Counter(value)
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _context_type(key: str | None) -> IdentifierType | None:
    if not key:
        return None
    normalized = normalize_schema_key(key)
    for identifier_type, keys in _CONTEXT_TYPES.items():
        if normalized in keys:
            return identifier_type
    return None


def _normalize_phone(value: str) -> str | None:
    digits = re.sub(r"\D", "", value)
    if not 7 <= len(digits) <= 15:
        return None
    return ("+" if value.strip().startswith("+") else "") + digits


def _url_identifiers(value: str) -> tuple[str, ...]:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ()
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ()
    found: list[str] = []
    query_parts = list(parse_qsl(parsed.query, keep_blank_values=False))
    if "=" in parsed.fragment:
        query_parts.extend(parse_qsl(parsed.fragment, keep_blank_values=False))
    for key, candidate in query_parts:
        if normalize_schema_key(key) in _URL_ID_KEYS and candidate:
            found.append(unquote(candidate))
    segments = [unquote(part) for part in parsed.path.split("/") if part]
    for parent, candidate in zip(segments, segments[1:]):
        if normalize_schema_key(parent) in _PATH_ID_PARENTS and candidate:
            found.append(candidate)
    return tuple(dict.fromkeys(found))


def detect_identifier(value: str, *, key: str | None = None) -> tuple[DetectedIdentifier, ...]:
    """Detect strong formats first, then context-labelled and opaque values."""

    raw = str(value).strip()
    if not raw:
        return ()
    found: list[DetectedIdentifier] = []
    url_values = _url_identifiers(raw)
    for carried in url_values:
        found.append(DetectedIdentifier(IdentifierType.URL_CARRIED_IDENTIFIER, carried, _sha256(carried), "url-carried-identifier"))
    if found:
        return tuple(found)
    if _EMAIL.fullmatch(raw):
        normalized = raw.casefold()
        return (DetectedIdentifier(IdentifierType.EMAIL, normalized, _sha256(normalized), "email-format"),)
    if _MAC.fullmatch(raw):
        normalized = raw.replace("-", ":").casefold()
        return (DetectedIdentifier(IdentifierType.MAC, normalized, _sha256(normalized), "mac-format"),)
    try:
        normalized_ip = ipaddress.ip_address(raw).compressed
    except ValueError:
        normalized_ip = None
    if normalized_ip:
        return (DetectedIdentifier(IdentifierType.IP, normalized_ip, _sha256(normalized_ip), "ip-format"),)
    context_type = _context_type(key)
    if normalize_schema_key(key or "") in {"phone", "phone_number", "mobile", "telephone"} or raw.startswith("+"):
        phone = _normalize_phone(raw)
        if phone:
            return (DetectedIdentifier(IdentifierType.PHONE, phone, _sha256(phone), "phone-format-and-context"),)
    if context_type is not None:
        return (DetectedIdentifier(context_type, raw, _sha256(raw), "schema-key-context"),)
    # UUIDs and high-entropy machine-shaped strings remain explicitly meaningless.
    mixed_machine_shape = any(char.isalpha() for char in raw) and any(char.isdigit() for char in raw)
    if _UUID.fullmatch(raw) or (_OPAQUE.fullmatch(raw) and mixed_machine_shape and shannon_entropy(raw) >= 2.5):
        return (DetectedIdentifier(IdentifierType.OPAQUE_RECURRING_TOKEN, None, _sha256(raw), "opaque-shape"),)
    return ()


def _source_key(observation: IdentifierObservation) -> str:
    return str(observation.source_event_id or observation.source_artifact_id)


def aggregate_identifier_candidates(observations: Iterable[IdentifierObservation]) -> tuple[FeatureCandidate, ...]:
    """Aggregate identifier candidates without inventing opaque-token semantics."""

    grouped: dict[tuple[IdentifierType, str], list[tuple[IdentifierObservation, DetectedIdentifier]]] = defaultdict(list)
    for observation in observations:
        for detected in detect_identifier(observation.value, key=observation.key):
            grouped[(detected.identifier_type, detected.token_hash)].append((observation, detected))

    candidates: list[FeatureCandidate] = []
    for (identifier_type, token_hash), entries in sorted(grouped.items(), key=lambda item: (item[0][0].value, item[0][1])):
        source_events = tuple(dict.fromkeys(item.source_event_id for item, _ in entries if item.source_event_id))
        source_artifacts = tuple(dict.fromkeys(item.source_artifact_id for item, _ in entries if item.source_artifact_id))
        services = {item.service for item, _ in entries if item.service}
        domains = {item.domain for item, _ in entries if item.domain}
        schemas = {item.schema_id for item, _ in entries if item.schema_id}
        sources = {_source_key(item) for item, _ in entries}
        times = sorted(item.seen_at for item, _ in entries if item.seen_at)
        occurrence_count = len(entries)
        recurrence_ratio = (occurrence_count - 1) / occurrence_count
        cross_source_factor = min(1.0, len(sources) / 2)
        stability = recurrence_ratio * cross_source_factor
        detected = entries[0][1]
        opaque = identifier_type is IdentifierType.OPAQUE_RECURRING_TOKEN
        candidates.append(FeatureCandidate(
            feature_type="identifier_candidate",
            detector_id="privacy.identifier",
            detector_version=DETECTOR_VERSION,
            source_event_ids=source_events,
            source_artifact_ids=source_artifacts,
            calculated_values={
                "identifier_type": identifier_type.value,
                "identifier_hash": token_hash,
                "normalized_value": None if opaque else detected.normalized_value,
                "assigned_meaning": None,
                "occurrence_count": occurrence_count,
                "source_count": len(sources),
                "service_count": len(services),
                "domain_count": len(domains),
                "schema_count": len(schemas),
                "first_seen": times[0].isoformat() if times else None,
                "last_seen": times[-1].isoformat() if times else None,
                "recurrence_ratio": recurrence_ratio,
                "stability": stability,
                "matched_rule": detected.matched_rule,
                "semantic_adjudication_eligible": opaque,
            },
            confidence=0.0 if opaque else 1.0,
            rule_result=not opaque,
            candidate_status=FeatureCandidateStatus.UNKNOWN if opaque else FeatureCandidateStatus.DETERMINISTIC,
        ))
    return tuple(candidates)


def analyze_opaque_identifiers(observations: Iterable[IdentifierObservation]) -> tuple[OpaqueIdentifierCandidate, ...]:
    """Return aggregate shape/recurrence features for opaque values only."""

    grouped: dict[str, list[tuple[IdentifierObservation, str]]] = defaultdict(list)
    for observation in observations:
        for detected in detect_identifier(observation.value, key=observation.key):
            if detected.identifier_type is IdentifierType.OPAQUE_RECURRING_TOKEN:
                grouped[detected.token_hash].append((observation, observation.value.strip()))
    result: list[OpaqueIdentifierCandidate] = []
    for token_hash, entries in sorted(grouped.items()):
        observations_only = [item for item, _ in entries]
        values = [value for _, value in entries]
        sources = {_source_key(item) for item in observations_only}
        services = {item.service for item in observations_only if item.service}
        domains = {item.domain for item in observations_only if item.domain}
        schemas = {item.schema_id for item in observations_only if item.schema_id}
        times = sorted(item.seen_at for item in observations_only if item.seen_at)
        result.append(OpaqueIdentifierCandidate(
            token_hash=token_hash,
            occurrence_count=len(entries),
            source_count=len(sources),
            service_count=len(services),
            domain_count=len(domains),
            first_seen=times[0] if times else None,
            last_seen=times[-1] if times else None,
            entropy_bits_per_character=sum(shannon_entropy(value) for value in values) / len(values),
            recurrence_ratio=(len(entries) - 1) / len(entries),
            cross_schema_count=len(schemas),
            cross_domain_count=len(domains),
            assigned_meaning=None,
        ))
    return tuple(result)


class IdentifierFeatureDetector:
    """Pipeline adapter that aggregates identifier fields across ActivityEvents."""

    detector_id = "privacy.identifier"
    detector_version = DETECTOR_VERSION

    def detect(self, events: tuple[ActivityEvent, ...]) -> tuple[FeatureCandidate, ...]:
        observations: list[IdentifierObservation] = []
        for event in events:
            for key, value in event.identifiers.items():
                values = value if isinstance(value, (list, tuple, set)) else (value,)
                observations.extend(
                    IdentifierObservation(
                        value=str(item),
                        key=key,
                        source_event_id=event.event_id,
                        source_artifact_id=event.artifact_id,
                        service=event.service,
                        domain=event.data_domain,
                        schema_id=f"{event.parser_id}:{event.parser_version}",
                        seen_at=event.occurred_at,
                    )
                    for item in values
                    if item not in (None, "")
                )
            if isinstance(event.object_value, str) and event.object_value.startswith(("http://", "https://")):
                observations.append(IdentifierObservation(
                    value=event.object_value,
                    key="url",
                    source_event_id=event.event_id,
                    source_artifact_id=event.artifact_id,
                    service=event.service,
                    domain=event.data_domain,
                    schema_id=f"{event.parser_id}:{event.parser_version}",
                    seen_at=event.occurred_at,
                ))
        return aggregate_identifier_candidates(observations)
