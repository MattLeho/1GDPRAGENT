"""Versioned, deterministic schema-key dictionaries.

These dictionaries provide structural hints only.  A key match is never promoted to
an assertion about a person or a controller's processing without corroborating
evidence and the normal review/provenance path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


DICTIONARY_VERSION = "1.0.0"


class KeyCategory(str, Enum):
    TIMESTAMP = "timestamp"
    IDENTIFIER = "identifier"
    LOCATION = "location"
    RELATIONSHIP = "relationship"
    INFERENCE_LANGUAGE = "inference_language"


_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")
_SEPARATORS = re.compile(r"[^a-z0-9]+")


def normalize_schema_key(key: str) -> str:
    """Return a stable representation for exact dictionary matching."""

    split = _CAMEL_BOUNDARY.sub("_", str(key).strip())
    return _SEPARATORS.sub("_", split.casefold()).strip("_")


@dataclass(frozen=True, slots=True)
class VersionedKeyDictionary:
    dictionary_id: str
    version: str
    category: KeyCategory
    keys: tuple[str, ...]

    def __post_init__(self) -> None:
        normalized = tuple(sorted({normalize_schema_key(key) for key in self.keys}))
        if not self.dictionary_id or not self.version or not normalized:
            raise ValueError("a key dictionary requires an id, version, and keys")
        object.__setattr__(self, "keys", normalized)

    def matches(self, key: str) -> bool:
        return normalize_schema_key(key) in self.keys


@dataclass(frozen=True, slots=True)
class KeyDictionaryMatch:
    original_key: str
    normalized_key: str
    category: KeyCategory
    dictionary_id: str
    dictionary_version: str


DEFAULT_KEY_DICTIONARIES: tuple[VersionedKeyDictionary, ...] = (
    VersionedKeyDictionary(
        "privacy.schema.timestamp-keys",
        DICTIONARY_VERSION,
        KeyCategory.TIMESTAMP,
        (
            "timestamp", "time", "date", "datetime", "created_at", "updated_at",
            "occurred_at", "event_time", "event_timestamp", "start_time", "end_time",
            "last_seen", "first_seen", "published_at", "captured_at", "logged_at",
        ),
    ),
    VersionedKeyDictionary(
        "privacy.schema.identifier-keys",
        DICTIONARY_VERSION,
        KeyCategory.IDENTIFIER,
        (
            "id", "identifier", "user_id", "account_id", "profile_id", "device_id",
            "advertising_id", "ad_id", "cookie_id", "customer_id", "payment_id",
            "transaction_id", "message_id", "session_id", "username", "email",
            "email_address", "phone", "phone_number", "ip_address", "mac_address",
        ),
    ),
    VersionedKeyDictionary(
        "privacy.schema.location-keys",
        DICTIONARY_VERSION,
        KeyCategory.LOCATION,
        (
            "location", "latitude", "longitude", "lat", "lon", "lng", "coordinates",
            "address", "postcode", "postal_code", "city", "region", "country", "place_id",
            "geo", "geolocation", "accuracy", "altitude",
        ),
    ),
    VersionedKeyDictionary(
        "privacy.schema.relationship-keys",
        DICTIONARY_VERSION,
        KeyCategory.RELATIONSHIP,
        (
            "sender", "recipient", "recipients", "from", "to", "cc", "bcc", "contact",
            "contacts", "follower", "following", "member", "members", "attendee",
            "attendees", "organizer", "participant", "participants", "shared_with",
        ),
    ),
    VersionedKeyDictionary(
        "privacy.schema.inference-language-keys",
        DICTIONARY_VERSION,
        KeyCategory.INFERENCE_LANGUAGE,
        (
            "inferred", "inference", "prediction", "predicted", "propensity", "affinity",
            "segment", "audience_segment", "interest", "interests", "estimated",
            "likelihood", "probability", "score", "model_output", "recommendation_reason",
        ),
    ),
)


def match_schema_key(
    key: str,
    dictionaries: tuple[VersionedKeyDictionary, ...] = DEFAULT_KEY_DICTIONARIES,
) -> tuple[KeyDictionaryMatch, ...]:
    """Return all exact category matches for a key (multi-label by design)."""

    normalized = normalize_schema_key(key)
    return tuple(
        KeyDictionaryMatch(
            original_key=key,
            normalized_key=normalized,
            category=dictionary.category,
            dictionary_id=dictionary.dictionary_id,
            dictionary_version=dictionary.version,
        )
        for dictionary in dictionaries
        if dictionary.matches(normalized)
    )


def match_schema_keys(keys: list[str] | tuple[str, ...] | set[str]) -> tuple[KeyDictionaryMatch, ...]:
    return tuple(match for key in sorted(keys) for match in match_schema_key(key))
