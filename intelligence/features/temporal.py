"""Deterministic temporal normalisation with explicit precision and timezone evidence."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field

from ingestion.models import (
    FeatureCandidate,
    FeatureCandidateStatus,
    FrozenModel,
    TemporalPrecision,
)


DETECTOR_ID = "task3.temporal.normalisation"
DETECTOR_VERSION = "1.0.0"

_YEAR = re.compile(r"^(\d{4})$")
_MONTH = re.compile(r"^(\d{4})-(\d{2})$")
_DAY = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")
_HOUR = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}(?:Z|[+-]\d{2}:?\d{2})?$")
_MINUTE = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}(?:Z|[+-]\d{2}:?\d{2})?$")
_SECOND = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?$")
_ZONE_SUFFIX = re.compile(r"^(.*?)(?:\s*)\[([^\]]+)\]$")


class TemporalNormalisation(FrozenModel):
    original_value: Any
    parsed_value: Any | None = None
    timezone: str | None = None
    timezone_evidence: str | None = None
    timezone_assumption: str | None = None
    temporal_precision: TemporalPrecision
    parser_version: str = Field(min_length=1)
    parse_error: str | None = None


def _offset_name(value: datetime) -> str | None:
    offset = value.utcoffset()
    if offset is None:
        return None
    seconds = int(offset.total_seconds())
    if seconds == 0:
        return "UTC"
    sign = "+" if seconds >= 0 else "-"
    seconds = abs(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    return f"{sign}{hours:02d}:{minutes:02d}"


def _datetime_result(
    original: Any,
    parsed: datetime,
    precision: TemporalPrecision,
    parser_version: str,
    *,
    zone_name: str | None = None,
    zone_evidence: str | None = None,
    timezone_assumption: str | None = None,
) -> TemporalNormalisation:
    timezone_name = zone_name or _offset_name(parsed)
    evidence = zone_evidence or ("explicit_offset" if parsed.utcoffset() is not None else "absent")
    return TemporalNormalisation(
        original_value=original,
        parsed_value=parsed,
        timezone=timezone_name,
        timezone_evidence=evidence,
        timezone_assumption=timezone_assumption if parsed.utcoffset() is None else None,
        temporal_precision=precision,
        parser_version=parser_version,
    )


def _normalise_string(
    original: str,
    parser_version: str,
    timezone_assumption: str | None,
) -> TemporalNormalisation:
    value = original.strip()
    if match := _YEAR.fullmatch(value):
        return TemporalNormalisation(
            original_value=original, parsed_value=match.group(1), timezone_evidence="not_applicable",
            temporal_precision=TemporalPrecision.YEAR, parser_version=parser_version,
        )
    if match := _MONTH.fullmatch(value):
        try:
            date(int(match.group(1)), int(match.group(2)), 1)
        except ValueError as error:
            return _unknown(original, parser_version, str(error))
        return TemporalNormalisation(
            original_value=original, parsed_value=value, timezone_evidence="not_applicable",
            temporal_precision=TemporalPrecision.MONTH, parser_version=parser_version,
        )
    if _DAY.fullmatch(value):
        try:
            parsed_date = date.fromisoformat(value)
        except ValueError as error:
            return _unknown(original, parser_version, str(error))
        # A date remains a date. It is never fabricated as midnight UTC.
        return TemporalNormalisation(
            original_value=original, parsed_value=parsed_date, timezone_evidence="not_applicable_date_only",
            temporal_precision=TemporalPrecision.DAY, parser_version=parser_version,
        )

    zone_name: str | None = None
    zone_evidence: str | None = None
    datetime_text = value
    if zone_match := _ZONE_SUFFIX.fullmatch(value):
        datetime_text, zone_name = zone_match.groups()
        try:
            zone = ZoneInfo(zone_name)
        except ZoneInfoNotFoundError as error:
            return _unknown(original, parser_version, f"unknown timezone: {zone_name}")
        zone_evidence = "explicit_iana_zone"
    else:
        zone = None

    if _HOUR.fullmatch(datetime_text):
        precision = TemporalPrecision.HOUR
        datetime_text = re.sub(r"([T ]\d{2})(Z|[+-]\d{2}:?\d{2})?$", r"\1:00\2", datetime_text)
    elif _MINUTE.fullmatch(datetime_text):
        precision = TemporalPrecision.MINUTE
    elif _SECOND.fullmatch(datetime_text):
        precision = TemporalPrecision.SECOND
    else:
        return _unknown(original, parser_version, "unsupported or ambiguous temporal representation")
    try:
        parsed = datetime.fromisoformat(datetime_text.replace("Z", "+00:00").replace(",", "."))
        if zone is not None:
            if parsed.tzinfo is not None:
                return _unknown(original, parser_version, "both offset and named timezone were supplied")
            first = parsed.replace(tzinfo=zone, fold=0)
            second = parsed.replace(tzinfo=zone, fold=1)
            if first.utcoffset() != second.utcoffset():
                # A wall time in a DST transition is ambiguous or nonexistent.
                # Preserve the wall time and named-zone evidence, but do not
                # fabricate one of the possible instants.
                return TemporalNormalisation(
                    original_value=original,
                    parsed_value=parsed,
                    timezone=zone_name,
                    timezone_evidence="explicit_iana_zone_unresolved_transition",
                    temporal_precision=precision,
                    parser_version=parser_version,
                )
            parsed = first
    except ValueError as error:
        return _unknown(original, parser_version, str(error))
    return _datetime_result(
        original, parsed, precision, parser_version, zone_name=zone_name,
        zone_evidence=zone_evidence, timezone_assumption=timezone_assumption,
    )


def _unknown(original: Any, parser_version: str, error: str) -> TemporalNormalisation:
    return TemporalNormalisation(
        original_value=original,
        temporal_precision=TemporalPrecision.UNKNOWN,
        parser_version=parser_version,
        parse_error=error,
    )


def normalise_temporal(
    value: Any,
    *,
    parser_version: str,
    timezone_assumption: str | None = None,
) -> TemporalNormalisation:
    """Normalise supported temporal values without inventing precision or timezone."""
    if not parser_version or not parser_version.strip():
        raise ValueError("parser_version is required")
    if isinstance(value, datetime):
        return _datetime_result(
            value, value, TemporalPrecision.SECOND, parser_version,
            timezone_assumption=timezone_assumption,
        )
    if isinstance(value, date):
        return TemporalNormalisation(
            original_value=value, parsed_value=value, timezone_evidence="not_applicable_date_only",
            temporal_precision=TemporalPrecision.DAY, parser_version=parser_version,
        )
    if isinstance(value, bool):
        return _unknown(value, parser_version, "boolean is not a temporal value")
    if isinstance(value, (int, float)):
        try:
            seconds = float(value) / 1000 if abs(float(value)) >= 100_000_000_000 else float(value)
            parsed = datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as error:
            return _unknown(value, parser_version, str(error))
        return TemporalNormalisation(
            original_value=value, parsed_value=parsed, timezone="UTC",
            timezone_evidence="unix_epoch_semantics", temporal_precision=TemporalPrecision.SECOND,
            parser_version=parser_version,
        )
    if isinstance(value, str):
        return _normalise_string(value, parser_version, timezone_assumption)
    if isinstance(value, Mapping) and set(value) == {"start", "end"}:
        start = normalise_temporal(value["start"], parser_version=parser_version, timezone_assumption=timezone_assumption)
        end = normalise_temporal(value["end"], parser_version=parser_version, timezone_assumption=timezone_assumption)
        if TemporalPrecision.UNKNOWN in {start.temporal_precision, end.temporal_precision}:
            return _unknown(value, parser_version, "range boundary could not be normalised")
        timezone_name = start.timezone if start.timezone == end.timezone else None
        assumption = start.timezone_assumption if start.timezone_assumption == end.timezone_assumption else None
        return TemporalNormalisation(
            original_value=value,
            parsed_value={"start": start.parsed_value, "end": end.parsed_value},
            timezone=timezone_name,
            timezone_evidence="range_boundaries",
            timezone_assumption=assumption,
            temporal_precision=TemporalPrecision.RANGE,
            parser_version=parser_version,
        )
    return _unknown(value, parser_version, "unsupported temporal value type")


# American spelling for callers that already use "normalization".
normalize_temporal = normalise_temporal


def temporal_feature_candidate(
    value: Any,
    *,
    parser_version: str,
    source_event_ids: Iterable[UUID] = (),
    source_artifact_ids: Iterable[UUID] = (),
    timezone_assumption: str | None = None,
) -> FeatureCandidate:
    normalisation = normalise_temporal(
        value, parser_version=parser_version, timezone_assumption=timezone_assumption,
    )
    successful = normalisation.temporal_precision is not TemporalPrecision.UNKNOWN
    return FeatureCandidate(
        feature_type="temporal_normalisation",
        detector_id=DETECTOR_ID,
        detector_version=DETECTOR_VERSION,
        source_event_ids=tuple(source_event_ids),
        source_artifact_ids=tuple(source_artifact_ids),
        calculated_values=normalisation.model_dump(mode="json"),
        rule_result=successful,
        candidate_status=(
            FeatureCandidateStatus.DETERMINISTIC if successful else FeatureCandidateStatus.UNKNOWN
        ),
    )
