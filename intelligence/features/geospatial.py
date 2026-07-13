"""Deterministic geospatial precision and source-explicit interactions.

This module deliberately describes only what an ActivityEvent already says.  It
does not cluster coordinates, invent place roles, or translate interaction
actions into social relationship labels.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
import json
import math
import re
from typing import Any, Iterable, Mapping

from ingestion.models import (
    ActivityEvent,
    FeatureCandidate,
    FeatureCandidateStatus,
)


class GeospatialPrecision(str, Enum):
    EXACT_COORDINATE = "EXACT_COORDINATE"
    COARSE_COORDINATE = "COARSE_COORDINATE"
    ADDRESS = "ADDRESS"
    POSTCODE = "POSTCODE"
    PLACE = "PLACE"
    CITY = "CITY"
    REGION = "REGION"
    COUNTRY = "COUNTRY"


class InteractionAction(str, Enum):
    SENT_TO = "SENT_TO"
    RECEIVED_FROM = "RECEIVED_FROM"
    FOLLOWED = "FOLLOWED"
    SUBSCRIBED_TO = "SUBSCRIBED_TO"
    MEMBER_OF = "MEMBER_OF"
    APPEARS_IN_CONTACTS = "APPEARS_IN_CONTACTS"


_LATITUDE_KEYS = frozenset({"lat", "latitude"})
_LONGITUDE_KEYS = frozenset({"lon", "lng", "long", "longitude"})
_ACCURACY_KEYS = frozenset({
    "accuracy", "accuracy_m", "accuracy_meter", "accuracy_meters",
    "accuracy_metre", "accuracy_metres", "horizontal_accuracy",
    "horizontal_accuracy_m", "reported_accuracy", "accuracy_km", "accuracy_ft",
})
_ADDRESS_KEYS = frozenset({"address", "street_address", "formatted_address"})
_POSTCODE_KEYS = frozenset({"postcode", "postal_code", "zip", "zip_code"})
_PLACE_KEYS = frozenset({"place", "place_name", "location_name", "venue"})
_CITY_KEYS = frozenset({"city", "locality", "town"})
_REGION_KEYS = frozenset({"region", "state", "province", "county"})
_COUNTRY_KEYS = frozenset({"country", "country_name", "country_code"})
_EXPLICIT_PRECISION = {item.value: item for item in GeospatialPrecision}
_EXACT_ACCURACY_METRES = 100.0


def _normalise_key(value: Any) -> str:
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", str(value).strip())
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _first(mapping: Mapping[str, Any], names: frozenset[str]) -> tuple[str, Any] | None:
    for key, value in mapping.items():
        if _normalise_key(key) in names and value not in (None, ""):
            return str(key), value
    return None


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _coordinate_decimals(value: Any) -> int:
    try:
        exponent = Decimal(str(value)).as_tuple().exponent
    except (InvalidOperation, ValueError):
        return 0
    return max(0, -exponent)


def _reported_accuracy(mapping: Mapping[str, Any]) -> tuple[Any | None, float | None]:
    found = _first(mapping, _ACCURACY_KEYS)
    if found is None:
        return None, None
    key, raw = found
    if isinstance(raw, bool):
        return raw, None
    factor = 1.0
    numeric: float | None = None
    if isinstance(raw, (int, float, Decimal)):
        numeric = _number(raw)
    elif isinstance(raw, str):
        match = re.fullmatch(
            r"\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(m|metres?|meters?|km|kilometres?|kilometers?|ft|feet)?\s*",
            raw,
            flags=re.IGNORECASE,
        )
        if match:
            numeric = _number(match.group(1))
            unit = (match.group(2) or "m").lower()
            factor = 1000.0 if unit.startswith("k") else (0.3048 if unit in {"ft", "feet"} else 1.0)
    if numeric is not None:
        normalised_key = _normalise_key(key)
        factor = 1000.0 if normalised_key.endswith("km") else (0.3048 if normalised_key.endswith("ft") else factor)
    metres = None if numeric is None or numeric < 0 else numeric * factor
    return raw, metres


def _coordinate_candidate(location_key: str, mapping: Mapping[str, Any]) -> dict[str, Any] | None:
    lat_item = _first(mapping, _LATITUDE_KEYS)
    lon_item = _first(mapping, _LONGITUDE_KEYS)
    if lat_item is None or lon_item is None:
        return None
    latitude, longitude = _number(lat_item[1]), _number(lon_item[1])
    if latitude is None or longitude is None or not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        return None
    raw_accuracy, accuracy_metres = _reported_accuracy(mapping)
    explicit = _first(mapping, frozenset({"precision", "geospatial_precision"}))
    explicit_precision = None
    if explicit is not None:
        explicit_precision = _EXPLICIT_PRECISION.get(str(explicit[1]).strip().upper())
    if explicit_precision in {GeospatialPrecision.EXACT_COORDINATE, GeospatialPrecision.COARSE_COORDINATE}:
        precision = explicit_precision
    elif accuracy_metres is not None:
        precision = (
            GeospatialPrecision.EXACT_COORDINATE
            if accuracy_metres <= _EXACT_ACCURACY_METRES
            else GeospatialPrecision.COARSE_COORDINATE
        )
    else:
        decimal_places = min(_coordinate_decimals(lat_item[1]), _coordinate_decimals(lon_item[1]))
        precision = GeospatialPrecision.EXACT_COORDINATE if decimal_places >= 4 else GeospatialPrecision.COARSE_COORDINATE
    values: dict[str, Any] = {
        "location_key": location_key,
        "precision": precision.value,
        "latitude": latitude,
        "longitude": longitude,
    }
    if raw_accuracy is not None:
        # Keep the exact source-reported representation as well as a useful
        # normalised value.  A failed normalisation never erases source data.
        values["reported_accuracy"] = raw_accuracy
        values["reported_accuracy_metres"] = accuracy_metres
    return values


def _named_candidate(location_key: str, mapping: Mapping[str, Any]) -> dict[str, Any] | None:
    declared = _first(mapping, frozenset({"precision", "geospatial_precision"}))
    if declared is not None:
        precision = _EXPLICIT_PRECISION.get(str(declared[1]).strip().upper())
        if precision not in {None, GeospatialPrecision.EXACT_COORDINATE, GeospatialPrecision.COARSE_COORDINATE}:
            reported = _first(mapping, frozenset({"value", "name", "label"}))
            if reported is not None:
                return {
                    "location_key": location_key,
                    "precision": precision.value,
                    "reported_value": reported[1],
                    "source_reported": True,
                }
    for precision, names in (
        (GeospatialPrecision.ADDRESS, _ADDRESS_KEYS),
        (GeospatialPrecision.POSTCODE, _POSTCODE_KEYS),
        (GeospatialPrecision.PLACE, _PLACE_KEYS),
        (GeospatialPrecision.CITY, _CITY_KEYS),
        (GeospatialPrecision.REGION, _REGION_KEYS),
        (GeospatialPrecision.COUNTRY, _COUNTRY_KEYS),
    ):
        found = _first(mapping, names)
        if found is not None:
            return {
                "location_key": location_key,
                "precision": precision.value,
                "reported_value": found[1],
                "source_reported": True,
            }
    return None


def _location_payloads(locations: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    candidates: list[dict[str, Any]] = []
    # Parsers may emit either one location object or named location selector
    # outputs.  Treat the former as one unit to keep latitude/longitude paired.
    if _first(locations, _LATITUDE_KEYS) and _first(locations, _LONGITUDE_KEYS):
        coordinate = _coordinate_candidate("location", locations)
        if coordinate:
            candidates.append(coordinate)
    else:
        for key, value in locations.items():
            normalised_key = _normalise_key(key)
            if isinstance(value, Mapping):
                candidate = _coordinate_candidate(str(key), value) or _named_candidate(str(key), value)
            else:
                candidate = _named_candidate(str(key), {normalised_key: value})
            if candidate:
                candidates.append(candidate)
    return tuple(sorted(candidates, key=lambda item: json.dumps(item, sort_keys=True, default=str)))


@dataclass(frozen=True, slots=True)
class GeospatialFeatureDetector:
    detector_id: str = "task3.geospatial_precision"
    detector_version: str = "1.0.0"

    def detect(self, events: tuple[ActivityEvent, ...]) -> Iterable[FeatureCandidate]:
        for event in events:
            for values in _location_payloads(event.locations):
                yield FeatureCandidate(
                    feature_type="geospatial.precision",
                    detector_id=self.detector_id,
                    detector_version=self.detector_version,
                    source_event_ids=(event.event_id,),
                    calculated_values=values,
                    confidence=1.0,
                    rule_result=True,
                    candidate_status=FeatureCandidateStatus.DETERMINISTIC,
                )


def _action(value: Any) -> InteractionAction | None:
    key = _normalise_key(value).upper()
    try:
        return InteractionAction(key)
    except ValueError:
        return None


def _interaction_payloads(relationships: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    found: list[dict[str, Any]] = []
    for key, value in relationships.items():
        direct = _action(key)
        if direct is not None and value not in (None, "", [], {}):
            found.append({"action": direct.value, "target": value, "source_field": str(key)})
        if isinstance(value, Mapping):
            declared_action = value.get("action", value.get("relationship_action"))
            explicit = _action(declared_action) if declared_action is not None else None
            if explicit is None:
                continue
            target = next(
                (value[name] for name in ("target", "party", "object", "identifier", "value") if name in value),
                None,
            )
            if target not in (None, "", [], {}):
                found.append({"action": explicit.value, "target": target, "source_field": str(key)})
    unique = {
        json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str): item
        for item in found
    }
    return tuple(unique[key] for key in sorted(unique))


@dataclass(frozen=True, slots=True)
class ExplicitInteractionFeatureDetector:
    detector_id: str = "task3.explicit_interaction"
    detector_version: str = "1.0.0"

    def detect(self, events: tuple[ActivityEvent, ...]) -> Iterable[FeatureCandidate]:
        for event in events:
            for values in _interaction_payloads(event.relationships):
                yield FeatureCandidate(
                    feature_type="interaction.explicit_action",
                    detector_id=self.detector_id,
                    detector_version=self.detector_version,
                    source_event_ids=(event.event_id,),
                    calculated_values=values,
                    confidence=1.0,
                    rule_result=True,
                    candidate_status=FeatureCandidateStatus.DETERMINISTIC,
                )


def extract_geospatial_features(events: Iterable[ActivityEvent]) -> tuple[FeatureCandidate, ...]:
    return tuple(GeospatialFeatureDetector().detect(tuple(events)))


def extract_explicit_interactions(events: Iterable[ActivityEvent]) -> tuple[FeatureCandidate, ...]:
    return tuple(ExplicitInteractionFeatureDetector().detect(tuple(events)))
