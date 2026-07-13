"""Constrained, deterministic execution of reviewed declarative parser specs.

Selectors are data only.  The runtime deliberately supports JSON Pointer and a
small JSON-path-like subset; it never evaluates expressions or generated code.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import re
from typing import Any, Iterable, Mapping
from uuid import UUID, uuid5

from .models import ActivityEvent, DeclarativeParserSpec, ParserExecutionResult


EVENT_NAMESPACE = UUID("2f56a5d8-51d4-4bd6-a765-41378c61aa39")
_JSON_PATH = re.compile(r"^\$(?:(?:\.[A-Za-z_][A-Za-z0-9_-]*)|(?:\[(?:0|[1-9][0-9]*)\]))*$")
_FORBIDDEN = ("*", "..", "?(", "[?", "@", "(`", "__")


class ParserSpecError(ValueError):
    """Raised when a parser spec contains an unsafe or unsupported selector."""


class RecordRejected(ValueError):
    """Raised when one record cannot preserve required provenance."""


@dataclass(frozen=True, slots=True)
class LocatedRecord:
    value: Mapping[str, Any]
    source_locator_id: UUID
    field_locator_ids: Mapping[str, UUID]


def validate_selector(selector: str, *, family: str) -> str:
    if not selector or len(selector.encode("utf-8")) > 512:
        raise ParserSpecError("selector must be non-empty and at most 512 bytes")
    if any(token in selector for token in _FORBIDDEN):
        raise ParserSpecError("wildcards, recursion, filters, scripts and magic names are forbidden")
    normalised_family = family.lower()
    if normalised_family in {"json", "structured", "structured_text", "tabular"}:
        if selector.startswith("/") or selector == "":
            _decode_pointer(selector)
            return selector
        if _JSON_PATH.fullmatch(selector):
            return selector
        raise ParserSpecError("selector is not JSON Pointer or restricted JSON path")
    raise ParserSpecError(f"declarative selectors are not supported for family {family!r}")


def validate_parser_spec(spec: DeclarativeParserSpec) -> DeclarativeParserSpec:
    selectors = _selectors(spec)
    if not spec.parser_id.strip() or not spec.parser_version.strip():
        raise ParserSpecError("parser_id and parser_version are required")
    if not spec.event_type.strip() or not spec.data_domain.strip():
        raise ParserSpecError("event_type and data_domain are required")
    for name, selector in selectors.items():
        try:
            validate_selector(selector, family=spec.file_family)
        except ParserSpecError as exc:
            raise ParserSpecError(f"invalid {name}: {exc}") from exc
    return spec


def _decode_pointer(pointer: str) -> tuple[str, ...]:
    if pointer == "":
        return ()
    if not pointer.startswith("/"):
        raise ParserSpecError("JSON Pointer must start with /")
    result: list[str] = []
    for raw in pointer[1:].split("/"):
        index = 0
        while index < len(raw):
            if raw[index] == "~" and (index + 1 == len(raw) or raw[index + 1] not in "01"):
                raise ParserSpecError("invalid JSON Pointer escape")
            index += 2 if raw[index] == "~" else 1
        result.append(raw.replace("~1", "/").replace("~0", "~"))
    return tuple(result)


def _path_tokens(selector: str) -> tuple[str | int, ...]:
    if selector.startswith("/") or selector == "":
        return tuple(int(part) if part.isdigit() else part for part in _decode_pointer(selector))
    tokens: list[str | int] = []
    for name, index in re.findall(r"\.([A-Za-z_][A-Za-z0-9_-]*)|\[([0-9]+)\]", selector[1:]):
        tokens.append(name if name else int(index))
    return tuple(tokens)


def selector_to_json_pointer(selector: str, *, family: str = "json") -> str:
    """Return the canonical JSON Pointer for a safe supported selector."""
    validate_selector(selector, family=family)
    if selector.startswith("/") or selector == "":
        return selector
    return "".join(
        "/" + str(token).replace("~", "~0").replace("/", "~1")
        for token in _path_tokens(selector)
    )


def select(value: Any, selector: str, *, family: str = "json") -> Any:
    validate_selector(selector, family=family)
    current = value
    for token in _path_tokens(selector):
        if isinstance(token, int):
            if not isinstance(current, list) or token >= len(current):
                raise KeyError(selector)
            current = current[token]
        else:
            if not isinstance(current, Mapping) or token not in current:
                raise KeyError(selector)
            current = current[token]
    return current


def _selectors(spec: DeclarativeParserSpec) -> dict[str, str]:
    values: dict[str, str] = {}
    if spec.timestamp_selector:
        values["occurred_at"] = spec.timestamp_selector
    if spec.subject_selector:
        values["subject_id"] = spec.subject_selector
    values.update({f"object.{key}": value for key, value in spec.object_selectors.items()})
    values.update({f"identifier.{key}": value for key, value in spec.identifier_selectors.items()})
    values.update({f"location.{key}": value for key, value in spec.location_selectors.items()})
    values.update({f"relationship.{key}": value for key, value in spec.relationship_fields.items()})
    return values


def parser_selectors(spec: DeclarativeParserSpec) -> dict[str, str]:
    validate_parser_spec(spec)
    return _selectors(spec)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str, allow_nan=False)


def execute_parser(
    spec: DeclarativeParserSpec,
    records: Iterable[LocatedRecord],
    *,
    artifact_id: UUID,
    export_snapshot_id: UUID,
) -> ParserExecutionResult:
    validate_parser_spec(spec)
    emitted: list[ActivityEvent] = []
    rejected = 0
    seen = 0
    warnings: list[str] = []
    selectors = _selectors(spec)
    for index, record in enumerate(records):
        seen += 1
        try:
            selected = {name: select(record.value, selector, family=spec.file_family) for name, selector in selectors.items()}
            missing = [name for name, selector in selectors.items() if selector not in record.field_locator_ids]
            if missing:
                raise RecordRejected("exact field locator missing for " + ", ".join(sorted(missing)))
            subject = selected.get("subject_id")
            if subject in (None, ""):
                raise RecordRejected("subject selector did not produce a value")
            identifiers = {key.removeprefix("identifier."): value for key, value in selected.items() if key.startswith("identifier.")}
            objects = {key.removeprefix("object."): value for key, value in selected.items() if key.startswith("object.")}
            locations = {key.removeprefix("location."): value for key, value in selected.items() if key.startswith("location.")}
            relationships = {key.removeprefix("relationship."): value for key, value in selected.items() if key.startswith("relationship.")}
            canonical_fields = {
                "subject_id": str(subject), "service": spec.service, "product": spec.product,
                "data_domain": spec.data_domain, "event_type": spec.event_type,
                "occurred_at": selected.get("occurred_at"), "identifiers": identifiers,
                "objects": objects, "locations": locations, "relationships": relationships,
            }
            signature = hashlib.sha256(_canonical(canonical_fields).encode()).hexdigest()
            object_id = identifiers.get("object_id") or identifiers.get("id")
            object_value = objects.get("value") if "value" in objects else (objects or None)
            original_time = selected.get("occurred_at")
            normalised_time = None
            occurred_at = None
            if spec.timestamp_selector:
                from features.temporal import normalise_temporal
                normalised_time = normalise_temporal(original_time, parser_version=spec.parser_version)
                if spec.temporal_precision.value != "UNKNOWN" and normalised_time.temporal_precision != spec.temporal_precision:
                    raise RecordRejected(
                        f"timestamp precision {normalised_time.temporal_precision.value} does not match declared {spec.temporal_precision.value}"
                    )
                parsed_time = normalised_time.parsed_value
                # Floating wall times and date-only values are preserved but do
                # not become fabricated UTC instants.
                if isinstance(parsed_time, datetime) and parsed_time.tzinfo is not None:
                    occurred_at = parsed_time
            emitted.append(ActivityEvent(
                event_id=uuid5(EVENT_NAMESPACE, signature), record_signature=signature,
                subject_id=str(subject), export_snapshot_id=export_snapshot_id,
                artifact_id=artifact_id, service=spec.service, product=spec.product,
                data_domain=spec.data_domain, event_type=spec.event_type,
                action_class=spec.action_class, occurred_at=occurred_at,
                occurred_at_original=original_time,
                temporal_precision=(normalised_time.temporal_precision if normalised_time else spec.temporal_precision),
                timezone=(normalised_time.timezone if normalised_time else None),
                timezone_evidence=(normalised_time.timezone_evidence if normalised_time else None),
                timezone_assumption=(normalised_time.timezone_assumption if normalised_time else None),
                object_type=spec.object_type, object_id=None if object_id is None else str(object_id),
                object_value=object_value, identifiers=identifiers, locations=locations,
                relationships=relationships, epistemic_hints=spec.epistemic_hints,
                parser_id=spec.parser_id,
                parser_version=spec.parser_version, source_locator_id=record.source_locator_id,
                field_locator_ids={name: record.field_locator_ids[selector] for name, selector in selectors.items()},
            ))
        except (KeyError, TypeError, ValueError) as exc:
            rejected += 1
            warnings.append(f"record {index}: {exc}")
    return ParserExecutionResult(
        parser_id=spec.parser_id, parser_version=spec.parser_version,
        artifact_id=artifact_id, records_seen=seen, events_emitted=len(emitted),
        rejected_records=rejected, events=tuple(emitted), warnings=tuple(warnings),
    )
