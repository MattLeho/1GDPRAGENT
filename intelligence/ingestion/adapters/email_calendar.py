from __future__ import annotations

import mailbox
import re
from collections import defaultdict
from datetime import datetime
from email import policy
from email.headerregistry import AddressHeader
from email.message import EmailMessage, Message
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..models import (
    EmbeddedMember,
    EvidenceLocatorValue,
    ExtractionContext,
    ExtractionResult,
    ExtractionUnit,
    FileTypeTruth,
    ProbeResult,
    QuarantineStatus,
)


_HEADER_NAMES = (
    "message-id",
    "references",
    "in-reply-to",
    "from",
    "sender",
    "reply-to",
    "to",
    "cc",
    "bcc",
    "date",
    "subject",
)
_KNOWN_VCARD_PROPERTIES = {
    "VERSION",
    "FN",
    "N",
    "NICKNAME",
    "EMAIL",
    "TEL",
    "ORG",
    "TITLE",
    "ROLE",
    "ADR",
    "BDAY",
    "ANNIVERSARY",
    "URL",
    "NOTE",
    "PHOTO",
    "GENDER",
    "LANG",
    "TZ",
    "GEO",
    "UID",
    "REV",
    "KIND",
}
_DATETIME_PROPERTIES = {"DTSTART", "DTEND", "DUE", "RECURRENCE-ID", "COMPLETED", "CREATED", "LAST-MODIFIED", "DTSTAMP"}


def _locator(locator_type: str, **locator: Any) -> EvidenceLocatorValue:
    return EvidenceLocatorValue(locator_type=locator_type, locator=locator)


def _decode_bytes(data: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "windows-1252", "latin-1"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replacement"


def _safe_header_value(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        return repr(value)


def _safe_addresses(value: Any) -> list[str]:
    if isinstance(value, AddressHeader):
        return [str(address) for address in value.addresses]
    return []


def _safe_date(value: str) -> str | None:
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed.isoformat() if parsed is not None else None


def _part_id(parent: str, child: int) -> str:
    return str(child) if not parent else f"{parent}.{child}"


def _leaf_parts(message: Message, parent: str = "") -> Iterable[tuple[str, Message]]:
    if parent and message.get_content_type() == "message/rfc822":
        yield parent, message
        nested = message.get_payload()
        if isinstance(nested, list):
            for nested_index, nested_message in enumerate(nested, start=1):
                yield from _leaf_parts(nested_message, _part_id(parent, nested_index))
        return
    if message.is_multipart():
        payload = message.get_payload()
        if isinstance(payload, list):
            for index, child in enumerate(payload, start=1):
                child_id = _part_id(parent, index)
                yield from _leaf_parts(child, child_id)
        return
    yield parent or "1", message


def _payload_bytes(part: Message) -> bytes:
    if part.get_content_type() == "message/rfc822":
        try:
            return part.as_bytes(policy=policy.default)
        except Exception:
            return b""
    try:
        payload = part.get_payload(decode=True)
    except Exception:
        payload = None
    if isinstance(payload, bytes):
        return payload
    raw = part.get_payload()
    if isinstance(raw, str):
        return raw.encode(part.get_content_charset() or "utf-8", errors="replace")
    return b""


def _body_text(part: Message) -> tuple[str | None, str | None]:
    if part.get_content_maintype() != "text":
        return None, None
    data = _payload_bytes(part)
    charset = part.get_content_charset() or "utf-8"
    try:
        return data.decode(charset), charset
    except (LookupError, UnicodeDecodeError):
        text, fallback = _decode_bytes(data)
        return text, fallback


def _split_content_line(line: str) -> tuple[str, dict[str, tuple[str, ...]], str] | None:
    quoted = False
    separator = -1
    for index, character in enumerate(line):
        if character == '"':
            quoted = not quoted
        elif character == ":" and not quoted:
            separator = index
            break
    if separator < 1:
        return None
    left, value = line[:separator], line[separator + 1 :]
    pieces: list[str] = []
    start = 0
    quoted = False
    for index, character in enumerate(left):
        if character == '"':
            quoted = not quoted
        elif character == ";" and not quoted:
            pieces.append(left[start:index])
            start = index + 1
    pieces.append(left[start:])
    name = pieces[0].upper()
    parameters: dict[str, tuple[str, ...]] = {}
    for parameter in pieces[1:]:
        key, equals, raw = parameter.partition("=")
        parameters[key.upper()] = tuple(item.strip('"') for item in raw.split(",")) if equals else ()
    return name, parameters, value


def _unfold_lines(text: str) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    lines: list[str] = []
    for physical in text.splitlines():
        if physical.startswith((" ", "\t")):
            if lines:
                lines[-1] += physical[1:]
            else:
                warnings.append("orphan folded content line")
        else:
            lines.append(physical.rstrip("\r"))
    return lines, warnings


def _calendar_value(name: str, parameters: dict[str, tuple[str, ...]], value: str) -> dict[str, Any]:
    result: dict[str, Any] = {"raw": value}
    if parameters:
        result["parameters"] = {key: list(values) for key, values in parameters.items()}
    if name in _DATETIME_PROPERTIES:
        value_type = (parameters.get("VALUE") or ("DATE-TIME",))[0].upper()
        tzid = (parameters.get("TZID") or (None,))[0]
        result["value_type"] = value_type
        if value_type == "DATE" or re.fullmatch(r"\d{8}", value):
            result["timezone_semantics"] = "date"
            try:
                result["normalised"] = datetime.strptime(value, "%Y%m%d").date().isoformat()
            except ValueError:
                result["invalid"] = True
        else:
            utc = value.endswith("Z")
            raw_datetime = value[:-1] if utc else value
            parsed: datetime | None = None
            for pattern in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
                try:
                    parsed = datetime.strptime(raw_datetime, pattern)
                    break
                except ValueError:
                    continue
            if utc:
                result["timezone_semantics"] = "utc"
                if parsed:
                    result["normalised"] = parsed.replace(tzinfo=ZoneInfo("UTC")).isoformat()
            elif tzid:
                result["timezone_semantics"] = "tzid"
                result["tzid"] = tzid
                if parsed:
                    try:
                        result["normalised"] = parsed.replace(tzinfo=ZoneInfo(tzid)).isoformat()
                    except ZoneInfoNotFoundError:
                        result["unknown_tzid"] = True
            else:
                result["timezone_semantics"] = "floating"
                if parsed:
                    result["normalised"] = parsed.isoformat()
    elif name == "RRULE":
        result["rule"] = {
            key.upper(): item
            for segment in value.split(";")
            if "=" in segment
            for key, item in (segment.split("=", 1),)
        }
        result["expanded"] = False
    return result


class EmailCalendarAdapter:
    adapter_id = "email_calendar"
    adapter_version = "1.0.0"
    family = "email_calendar"
    supported_mime_types = frozenset({"message/rfc822", "application/mbox", "text/calendar", "text/vcard", "text/x-vcard"})
    supported_extensions = frozenset({".eml", ".mbox", ".ics", ".vcf"})
    supports_streaming = True
    supports_nested_members = True
    locator_types = frozenset({"email_header", "email_mime_part", "email_attachment", "calendar_component", "vcard_property"})
    capability_flags = frozenset({"text", "structured_records", "attachments", "metadata", "timestamps"})

    def probe(self, path: str, truth: FileTypeTruth) -> ProbeResult:
        extension = Path(path).suffix.lower()
        try:
            sample = Path(path).read_bytes()[:65536]
        except OSError as exc:
            return ProbeResult(accepted=False, confidence=0.0, reason=f"unreadable: {exc}")
        upper = sample.upper()
        if b"BEGIN:VCALENDAR" in upper:
            return ProbeResult(accepted=True, confidence=1.0, detected_format="ics", reason="VCALENDAR marker")
        if b"BEGIN:VCARD" in upper:
            return ProbeResult(accepted=True, confidence=1.0, detected_format="vcf", reason="VCARD marker")
        if sample.startswith(b"From ") and (extension == ".mbox" or b"\nFrom " in sample):
            return ProbeResult(accepted=True, confidence=0.95, detected_format="mbox", reason="mbox separator")
        if re.search(br"(?im)^(message-id|from|to|subject|date):", sample):
            return ProbeResult(accepted=True, confidence=0.85, detected_format="eml", reason="RFC 5322 headers")
        truth_format = (truth.detected_format or "").lower()
        if extension in self.supported_extensions and truth_format in {extension[1:], "eml", "mbox", "ics", "vcf"}:
            return ProbeResult(accepted=True, confidence=0.5, detected_format=extension[1:], reason="compatible file-type truth")
        return ProbeResult(accepted=False, confidence=0.0, reason="no supported email/calendar/contact signature")

    def extract(self, path: str, context: ExtractionContext) -> ExtractionResult:
        detected_format = Path(path).suffix.lower().lstrip(".") or "eml"
        try:
            detected_format = self._format(path)
            if detected_format == "eml":
                message = BytesParser(policy=policy.default).parsebytes(Path(path).read_bytes())
                return self._email_result((message,), detected_format, context)
            if detected_format == "mbox":
                box = mailbox.mbox(path, factory=None, create=False)
                try:
                    messages = (
                        BytesParser(policy=policy.default).parsebytes(item.as_bytes(policy=policy.default))
                        for item in box
                    )
                    result = self._email_result(messages, detected_format, context)
                finally:
                    box.close()
                return result
            raw = Path(path).read_bytes()
            text, encoding = _decode_bytes(raw)
            if detected_format == "ics":
                return self._calendar_result(text, encoding, context)
            return self._vcard_result(text, encoding, context)
        except (OSError, mailbox.Error, ValueError) as exc:
            return ExtractionResult(
                artifact_id=context.artifact_id,
                adapter_id=self.adapter_id,
                adapter_version=self.adapter_version,
                family=self.family,
                detected_format=detected_format,
                warnings=(f"extraction failed: {exc}",),
                quarantine_status=QuarantineStatus.CORRUPT,
            )

    @staticmethod
    def _format(path: str) -> str:
        extension = Path(path).suffix.lower()
        if extension in {".eml", ".mbox", ".ics", ".vcf"}:
            return extension[1:]
        sample = Path(path).read_bytes()[:65536].upper()
        if b"BEGIN:VCALENDAR" in sample:
            return "ics"
        if b"BEGIN:VCARD" in sample:
            return "vcf"
        if sample.startswith(b"FROM "):
            return "mbox"
        return "eml"

    def _email_result(self, messages: Iterable[Message], detected_format: str, context: ExtractionContext) -> ExtractionResult:
        units: list[ExtractionUnit] = []
        members: list[EmbeddedMember] = []
        warnings: list[str] = []
        summaries: list[dict[str, Any]] = []
        ordinal = 0
        maximum_attachment_bytes = int(context.configuration.get("max_email_attachment_bytes", 64 * 1024 * 1024))
        if maximum_attachment_bytes < 0:
            raise ValueError("max_email_attachment_bytes must be non-negative")
        for message_index, message in enumerate(messages):
            defects = [str(defect) or defect.__class__.__name__ for defect in getattr(message, "defects", ())]
            warnings.extend(f"message {message_index}: {defect}" for defect in defects)
            summary: dict[str, Any] = {"message_index": message_index, "defects": defects}
            for header_name in _HEADER_NAMES:
                values = message.get_all(header_name, [])
                if values:
                    summary[header_name] = [_safe_header_value(value) for value in values]
                for occurrence, value in enumerate(values):
                    raw_value = _safe_header_value(value)
                    metadata: dict[str, Any] = {"header": header_name, "occurrence": occurrence}
                    addresses = _safe_addresses(value)
                    if addresses:
                        metadata["addresses"] = addresses
                    if header_name == "date":
                        metadata["parsed_date"] = _safe_date(raw_value)
                    units.append(
                        ExtractionUnit(
                            unit_id=f"message-{message_index}-header-{header_name}-{occurrence}",
                            unit_type="email_header",
                            ordinal=ordinal,
                            value=raw_value,
                            metadata=metadata,
                            evidence_locator=_locator("email_header", message=message_index, header=header_name, occurrence=occurrence),
                        )
                    )
                    ordinal += 1
            for part_id, part in _leaf_parts(message):
                filename = part.get_filename()
                disposition = part.get_content_disposition()
                content_type = part.get_content_type()
                is_attachment = disposition == "attachment" or filename is not None or content_type == "message/rfc822"
                part_metadata = {
                    "content_type": content_type,
                    "content_disposition": disposition,
                    "filename": filename,
                    "content_id": part.get("Content-ID"),
                    "content_transfer_encoding": part.get("Content-Transfer-Encoding"),
                }
                if is_attachment:
                    data = _payload_bytes(part)
                    member_path = filename or f"message-{message_index}/part-{part_id}"
                    member_ordinal = len(members)
                    attachment_locator = _locator(
                        "email_attachment", message=message_index, part=part_id,
                        **({"filename": filename} if filename else {}),
                    )
                    retained_content = data if len(data) <= maximum_attachment_bytes else None
                    if retained_content is None:
                        warnings.append(
                            f"message {message_index} attachment part {part_id}: payload exceeds "
                            f"max_email_attachment_bytes={maximum_attachment_bytes}"
                        )
                    members.append(
                        EmbeddedMember(
                            member_path=member_path,
                            ordinal=member_ordinal,
                            declared_size=len(data),
                            media_type=content_type,
                            content=retained_content,
                            evidence_locator=attachment_locator,
                            metadata={
                                "message": message_index, "part": part_id,
                                "content_retained": retained_content is not None,
                                **part_metadata,
                            },
                        )
                    )
                    units.append(
                        ExtractionUnit(
                            unit_id=f"message-{message_index}-attachment-{part_id}",
                            unit_type="email_attachment",
                            ordinal=ordinal,
                            structured_payload={"member_path": member_path, "size": len(data), **part_metadata},
                            evidence_locator=attachment_locator,
                        )
                    )
                    ordinal += 1
                else:
                    text, charset = _body_text(part)
                    if text is not None:
                        units.append(
                            ExtractionUnit(
                                unit_id=f"message-{message_index}-part-{part_id}",
                                unit_type="email_body",
                                ordinal=ordinal,
                                text=text,
                                metadata={**part_metadata, "charset": charset},
                                evidence_locator=_locator("email_mime_part", message=message_index, part=part_id),
                            )
                        )
                        ordinal += 1
            summaries.append(summary)
        return ExtractionResult(
            artifact_id=context.artifact_id,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            family=self.family,
            detected_format=detected_format,
            metadata={"message_count": len(summaries), "messages": summaries},
            units=tuple(units),
            embedded_members=tuple(members),
            warnings=tuple(warnings),
        )

    def _calendar_result(self, text: str, encoding: str, context: ExtractionContext) -> ExtractionResult:
        lines, warnings = _unfold_lines(text)
        stack: list[dict[str, Any]] = []
        components: list[dict[str, Any]] = []
        for line_number, line in enumerate(lines, start=1):
            parsed = _split_content_line(line)
            if parsed is None:
                if line.strip():
                    warnings.append(f"line {line_number}: malformed content line")
                continue
            name, parameters, value = parsed
            if name == "BEGIN":
                component = {"name": value.upper(), "properties": [], "children": [], "line": line_number}
                if stack:
                    stack[-1]["children"].append(component)
                stack.append(component)
            elif name == "END":
                if not stack or stack[-1]["name"] != value.upper():
                    warnings.append(f"line {line_number}: unmatched END:{value}")
                else:
                    completed = stack.pop()
                    if not stack:
                        components.append(completed)
            elif stack:
                stack[-1]["properties"].append((name, parameters, value, line_number))
            else:
                warnings.append(f"line {line_number}: property outside component")
        if stack:
            warnings.append("unterminated calendar component")

        units: list[ExtractionUnit] = []
        occurrence_counts: defaultdict[tuple[str, str | None, str], int] = defaultdict(int)
        ordinal = 0

        def emit(component: dict[str, Any], inherited_uid: str | None = None) -> None:
            nonlocal ordinal
            uid = next((value for name, _, value, _ in component["properties"] if name == "UID"), inherited_uid)
            component_name = component["name"]
            if component_name in {"VEVENT", "VTODO", "VJOURNAL", "VFREEBUSY", "VALARM"}:
                for name, parameters, value, line_number in component["properties"]:
                    key = (component_name, uid, name)
                    occurrence = occurrence_counts[key]
                    occurrence_counts[key] += 1
                    payload = _calendar_value(name, parameters, value)
                    payload.update({"name": name, "component": component_name})
                    units.append(
                        ExtractionUnit(
                            unit_id=f"calendar-{component_name.lower()}-{ordinal}",
                            unit_type="calendar_property",
                            ordinal=ordinal,
                            value=value,
                            structured_payload=payload,
                            metadata={"line": line_number, "property_occurrence": occurrence},
                            evidence_locator=_locator(
                                "calendar_component",
                                component=component_name,
                                occurrence=occurrence,
                                property=name,
                                **({"uid": uid} if uid else {}),
                            ),
                        )
                    )
                    ordinal += 1
            for child in component["children"]:
                emit(child, uid)

        for root in components:
            emit(root)
        return ExtractionResult(
            artifact_id=context.artifact_id,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            family=self.family,
            detected_format="ics",
            metadata={"encoding": encoding, "root_components": [component["name"] for component in components], "recurrence_expanded": False},
            units=tuple(units),
            warnings=tuple(warnings),
            quarantine_status=QuarantineStatus.CORRUPT if not components else QuarantineStatus.NONE,
        )

    def _vcard_result(self, text: str, encoding: str, context: ExtractionContext) -> ExtractionResult:
        lines, warnings = _unfold_lines(text)
        cards: list[list[tuple[str, dict[str, tuple[str, ...]], str, int]]] = []
        current: list[tuple[str, dict[str, tuple[str, ...]], str, int]] | None = None
        for line_number, line in enumerate(lines, start=1):
            parsed = _split_content_line(line)
            if parsed is None:
                if line.strip():
                    warnings.append(f"line {line_number}: malformed content line")
                continue
            raw_name, parameters, value = parsed
            name = raw_name.rsplit(".", 1)[-1]
            if name == "BEGIN" and value.upper() == "VCARD":
                if current is not None:
                    warnings.append(f"line {line_number}: nested VCARD")
                current = []
            elif name == "END" and value.upper() == "VCARD":
                if current is None:
                    warnings.append(f"line {line_number}: unmatched END:VCARD")
                else:
                    cards.append(current)
                    current = None
            elif current is not None:
                current.append((raw_name, parameters, value, line_number))
            elif line.strip():
                warnings.append(f"line {line_number}: property outside VCARD")
        if current is not None:
            warnings.append("unterminated VCARD")

        units: list[ExtractionUnit] = []
        ordinal = 0
        for card_index, card in enumerate(cards):
            occurrences: defaultdict[str, int] = defaultdict(int)
            for raw_name, parameters, value, line_number in card:
                group, dot, property_name = raw_name.rpartition(".")
                if not dot:
                    property_name, group = raw_name, ""
                property_name = property_name.upper()
                occurrence = occurrences[property_name]
                occurrences[property_name] += 1
                payload: dict[str, Any] = {
                    "property": property_name,
                    "value": value,
                    "classification": "known" if property_name in _KNOWN_VCARD_PROPERTIES else "unknown_property",
                }
                if group:
                    payload["group"] = group
                if parameters:
                    payload["parameters"] = {key: list(values) for key, values in parameters.items()}
                units.append(
                    ExtractionUnit(
                        unit_id=f"vcard-{card_index}-{property_name.lower()}-{occurrence}",
                        unit_type="vcard_property",
                        ordinal=ordinal,
                        value=value,
                        structured_payload=payload,
                        metadata={"line": line_number, "custom": property_name not in _KNOWN_VCARD_PROPERTIES},
                        evidence_locator=_locator("vcard_property", card=card_index, property=property_name, occurrence=occurrence),
                    )
                )
                ordinal += 1
        return ExtractionResult(
            artifact_id=context.artifact_id,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            family=self.family,
            detected_format="vcf",
            metadata={"encoding": encoding, "card_count": len(cards)},
            units=tuple(units),
            warnings=tuple(warnings),
            quarantine_status=QuarantineStatus.CORRUPT if not cards else QuarantineStatus.NONE,
        )
