"""Deterministic extraction for structured data, markup, and line-oriented text.

This adapter deliberately exposes syntax and record boundaries only.  It does
not infer a service, data domain, event type, or meaning from field names.
"""
from __future__ import annotations

import csv
import io
import json
import re
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Iterator

import yaml

from ..models import (
    EvidenceLocatorValue,
    ExtractionContext,
    ExtractionResult,
    ExtractionUnit,
    FileTypeTruth,
    ProbeResult,
    QuarantineStatus,
)

try:  # ijson is the approved bounded JSON-array reader.
    import ijson
except ImportError:  # pragma: no cover - constrained deployments get a safe fallback
    ijson = None


_FORMAT_BY_SUFFIX = {
    ".json": "json", ".jsonl": "ndjson", ".ndjson": "ndjson",
    ".csv": "csv", ".tsv": "tsv", ".xml": "xml", ".html": "html",
    ".htm": "html", ".yaml": "yaml", ".yml": "yaml", ".txt": "text",
    ".md": "markdown", ".markdown": "markdown", ".log": "text",
    ".dsv": "delimited", ".psv": "delimited",
}
_DELIMITERS = ",\t;|"
_PROBE_BYTES = 64 * 1024
_DEFAULT_MAX_UNITS = 250_000


def _format(path: str, context: ExtractionContext | None = None) -> str:
    configured = context.configuration.get("detected_format") if context else None
    return str(configured or _FORMAT_BY_SUFFIX.get(Path(path).suffix.lower(), "text")).lower()


def _encoding(raw: bytes) -> tuple[str, int]:
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8", 3
    if raw.startswith(b"\xff\xfe\x00\x00"):
        return "utf-32-le", 4
    if raw.startswith(b"\x00\x00\xfe\xff"):
        return "utf-32-be", 4
    if raw.startswith(b"\xff\xfe"):
        return "utf-16-le", 2
    if raw.startswith(b"\xfe\xff"):
        return "utf-16-be", 2
    try:
        raw.decode("utf-8")
        return "utf-8", 0
    except UnicodeDecodeError:
        # Windows exports commonly contain CP-1252.  It is a deterministic,
        # single-byte fallback and therefore preserves exact byte spans.
        return "cp1252", 0


def _read_text(path: str) -> tuple[bytes, str, str, int, tuple[str, ...]]:
    raw = Path(path).read_bytes()
    encoding, bom = _encoding(raw)
    warnings: list[str] = []
    try:
        text = raw[bom:].decode(encoding)
    except UnicodeDecodeError as exc:
        text = raw[bom:].decode(encoding, errors="replace")
        warnings.append(f"undecodable byte sequence replaced at byte {bom + exc.start}")
    return raw, text, encoding, bom, tuple(warnings)


def _pointer_token(value: object) -> str:
    return str(value).replace("~", "~0").replace("/", "~1")


def _unit(unit_id: str, unit_type: str, ordinal: int, locator_type: str,
          locator: dict[str, Any], *, text: str | None = None, value: Any = None,
          structured_payload: dict[str, Any] | list[Any] | None = None,
          metadata: dict[str, Any] | None = None, parent: str | None = None) -> ExtractionUnit:
    return ExtractionUnit(
        unit_id=unit_id, unit_type=unit_type, ordinal=ordinal, text=text, value=value,
        structured_payload=structured_payload, metadata=metadata or {},
        evidence_locator=EvidenceLocatorValue(locator_type=locator_type, locator=locator),
        parent_unit_id=parent,
    )


def _json_items(path: str, root: str, encoding: str, bom: int) -> Iterator[Any]:
    if root == "[" and ijson is not None and encoding == "utf-8":
        with open(path, "rb") as stream:
            stream.seek(bom)
            yield from ijson.items(stream, "item")
        return
    _, text, _, _, _ = _read_text(path)
    data = json.loads(text)
    if root == "[":
        yield from data
    else:
        yield data


class _DOMExtractor(HTMLParser):
    def __init__(self, text: str, max_units: int):
        super().__init__(convert_charrefs=True)
        self.text = text
        self.max_units = max_units
        self.stack: list[tuple[str, str]] = []
        self.counts: list[defaultdict[str, int]] = [defaultdict(int)]
        self.units: list[ExtractionUnit] = []
        self.unmatched_end_tags = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        counts = self.counts[-1]
        counts[tag] += 1
        segment = f"{tag}:nth-of-type({counts[tag]})"
        self.stack.append((tag, segment))
        self.counts.append(defaultdict(int))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                del self.counts[index + 1:]
                return
        self.unmatched_end_tags += 1

    def handle_data(self, data: str) -> None:
        if not data or not data.strip() or len(self.units) >= self.max_units:
            return
        line, column = self.getpos()
        path = " > ".join(segment for _, segment in self.stack) or ":root"
        ordinal = len(self.units)
        self.units.append(_unit(
            f"html-text-{ordinal}", "text", ordinal, "html_dom_span",
            {"selector": path}, text=data,
            metadata={"start_line":line,"start_column":column,"end_line":line+data.count("\n"),
                      "end_column":(len(data.rsplit("\n",1)[-1]) if "\n" in data else column+len(data))},
        ))


class StructuredTextAdapter:
    adapter_id = "structured_text"
    adapter_version = "1"
    family = "structured_text"
    supported_mime_types = frozenset({
        "application/json", "application/x-ndjson", "text/csv",
        "text/tab-separated-values", "application/xml", "text/xml", "text/html",
        "application/yaml", "text/yaml", "text/plain", "text/markdown",
        "text/x-delimited",
    })
    supported_extensions = frozenset(_FORMAT_BY_SUFFIX)
    supports_streaming = True
    supports_nested_members = False
    locator_types = frozenset({
        "json_pointer", "json_record", "csv_row", "csv_cell", "xml_element",
        "html_dom_span", "text_line", "text_byte_span",
    })
    capability_flags = frozenset({"text", "tables", "structured_records", "metadata"})

    def probe(self, path: str, truth: FileTypeTruth) -> ProbeResult:
        format_key = (truth.detected_format or _format(path)).lower()
        if format_key not in {"json", "ndjson", "csv", "tsv", "delimited", "xml", "html", "yaml", "text", "markdown"}:
            return ProbeResult(accepted=False, confidence=0, detected_format=None,
                               reason=f"structured_text does not support {format_key}")
        try:
            raw = Path(path).read_bytes()[:_PROBE_BYTES]
            encoding, bom = _encoding(raw)
            text = raw[bom:].decode(encoding, errors="strict")
            if "\x00" in text:
                raise ValueError("NUL bytes indicate non-text content")
            if format_key == "json":
                stripped = text.lstrip()
                if not stripped or stripped[0] not in "[{":
                    raise ValueError("JSON must begin with an object or array")
                if Path(path).stat().st_size <= _PROBE_BYTES:
                    json.loads(text)
            elif format_key == "ndjson":
                lines = [line for line in text.splitlines()[:100] if line.strip()]
                if not lines:
                    raise ValueError("no NDJSON records")
                valid = sum(1 for line in lines if _valid_json_line(line))
                if not valid:
                    raise ValueError("sample contains no valid JSON records")
                confidence = 1.0 if valid == len(lines) else 0.8
                return ProbeResult(accepted=True, confidence=confidence, detected_format="ndjson",
                                   reason=f"{valid}/{len(lines)} sampled records parsed")
            elif format_key in {"csv", "tsv", "delimited"}:
                delimiter = "\t" if format_key == "tsv" else _sniff_delimiter(text)
                next(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))
            elif format_key == "xml":
                if re.search(r"<!DOCTYPE", text, re.I):
                    raise ValueError("DOCTYPE is not permitted")
                if Path(path).stat().st_size <= _PROBE_BYTES:
                    import xml.etree.ElementTree as ET
                    ET.fromstring(text)
                elif not re.search(r"<(?:[A-Za-z_]|[A-Za-z_][\w.-]*:)[\w.:-]*(?:\s|/?>)", text):
                    raise ValueError("no XML root element in bounded sample")
            elif format_key == "html":
                parser = HTMLParser()
                parser.feed(text)
            elif format_key == "yaml":
                if Path(path).stat().st_size <= _PROBE_BYTES:
                    list(yaml.safe_load_all(text))
        except (OSError, UnicodeError, ValueError, csv.Error, json.JSONDecodeError, yaml.YAMLError) as exc:
            return ProbeResult(accepted=False, confidence=0, detected_format=format_key,
                               reason=f"probe rejected content: {exc}")
        return ProbeResult(accepted=True, confidence=0.95, detected_format=format_key,
                           reason=f"bounded {format_key} probe accepted content")

    def extract(self, path: str, context: ExtractionContext) -> ExtractionResult:
        format_key = _format(path, context)
        maximum = int(context.configuration.get("max_units", _DEFAULT_MAX_UNITS))
        try:
            if format_key == "json":
                units, metadata, warnings = self._json(path, maximum)
            elif format_key == "ndjson":
                units, metadata, warnings = self._ndjson(path, maximum)
            elif format_key in {"csv", "tsv", "delimited"}:
                units, metadata, warnings = self._delimited(path, format_key, maximum)
            elif format_key == "xml":
                units, metadata, warnings = self._xml(path, maximum)
            elif format_key == "html":
                units, metadata, warnings = self._html(path, maximum)
            elif format_key == "yaml":
                units, metadata, warnings = self._yaml(path, maximum)
            else:
                units, metadata, warnings = self._lines(path, format_key, maximum)
            quarantine = QuarantineStatus.NONE
        except Exception as exc:  # extraction failures stay visible to the pipeline
            units, metadata = [], {}
            warnings = [f"{format_key} extraction failed: {type(exc).__name__}: {exc}"]
            quarantine = QuarantineStatus.CORRUPT
        return ExtractionResult(
            artifact_id=context.artifact_id, adapter_id=self.adapter_id,
            adapter_version=self.adapter_version, family=self.family,
            detected_format=format_key, metadata=metadata, units=tuple(units),
            warnings=tuple(warnings), quarantine_status=quarantine,
        )

    def _json(self, path: str, maximum: int):
        with open(path, "rb") as stream:
            prefix = stream.read(_PROBE_BYTES)
        encoding, bom = _encoding(prefix)
        root = prefix[bom:].decode(encoding).lstrip()[:1]
        units: list[ExtractionUnit] = []
        warnings: list[str] = []
        for index, value in enumerate(_json_items(path, root, encoding, bom)):
            if index >= maximum:
                warnings.append(f"unit limit {maximum} reached")
                break
            pointer = f"/{index}" if root == "[" else ""
            payload = value if isinstance(value, (dict, list)) else None
            units.append(_unit(
                f"json-record-{index}", "record", index,
                "json_record" if root == "[" else "json_pointer",
                ({"record":index,"pointer":""} if root == "[" else {"pointer":pointer}),
                text="null" if value is None else None,
                value=value if payload is None and value is not None else None,
                structured_payload=payload,
            ))
        return units, {"top_level_type": "array" if root == "[" else "object",
                       "record_count": len(units), "encoding": encoding,
                       "bom_bytes": bom}, warnings

    def _ndjson(self, path: str, maximum: int):
        with open(path, "rb") as raw_stream:
            prefix = raw_stream.read(_PROBE_BYTES)
        encoding, bom = _encoding(prefix)
        units: list[ExtractionUnit] = []
        warnings: list[str] = []
        record_index = 0
        with open(path, "rb") as raw_stream:
            raw_stream.seek(bom)
            with io.TextIOWrapper(raw_stream, encoding=encoding, errors="replace", newline="") as stream:
                for line_number, physical_line in enumerate(stream, 1):
                    line = physical_line.rstrip("\r\n")
                    if not line.strip():
                        continue
                    if len(units) >= maximum:
                        warnings.append(f"unit limit {maximum} reached")
                        break
                    if "\ufffd" in line:
                        warnings.append(f"undecodable byte sequence replaced at line {line_number}")
                    locator = {"record":record_index,"pointer":""}
                    try:
                        value = json.loads(line)
                        payload = value if isinstance(value, (dict, list)) else None
                        units.append(_unit(f"json-record-{record_index}", "record", len(units),
                                           "json_record", locator, value=value if payload is None else None,
                                           text="null" if value is None else None,
                                           structured_payload=payload))
                    except json.JSONDecodeError as exc:
                        units.append(_unit(f"json-malformed-{record_index}", "malformed_record", len(units),
                                           "text_line", {"line":line_number}, text=line,
                                           metadata={"malformed":True,"error":exc.msg,"record":record_index,"parse_error_column":exc.colno}))
                        warnings.append(f"malformed NDJSON record at line {line_number}: {exc.msg}")
                    record_index += 1
        return units, {"encoding": encoding, "bom_bytes": bom, "record_count": record_index}, warnings

    def _delimited(self, path: str, format_key: str, maximum: int):
        with open(path, "rb") as raw_stream:
            prefix = raw_stream.read(_PROBE_BYTES)
        encoding, bom = _encoding(prefix)
        sample = prefix[bom:].decode(encoding, errors="replace")
        delimiter = "\t" if format_key == "tsv" else _sniff_delimiter(sample)
        units: list[ExtractionUnit] = []
        warnings: list[str] = []
        previous_end = 0
        logical_row = 0
        with open(path, "rb") as raw_stream:
            raw_stream.seek(bom)
            with io.TextIOWrapper(raw_stream, encoding=encoding, errors="replace", newline="") as stream:
                reader = csv.reader(stream, delimiter=delimiter)
                for row in reader:
                    if len(units) >= maximum:
                        warnings.append(f"unit limit {maximum} reached")
                        break
                    start_line, end_line = previous_end + 1, reader.line_num
                    previous_end = end_line
                    row_id = f"csv-row-{logical_row}"
                    canonical_row=logical_row+1
                    units.append(_unit(row_id, "row", len(units), "csv_row",
                                       {"row":canonical_row}, structured_payload=list(row),
                                       metadata={"physical_line_start":start_line,"physical_line_end":end_line}))
                    if any("\ufffd" in cell for cell in row):
                        warnings.append(f"undecodable byte sequence replaced in row {logical_row}")
                    for column, cell in enumerate(row):
                        if len(units) >= maximum:
                            warnings.append(f"unit limit {maximum} reached")
                            break
                        units.append(_unit(f"csv-cell-{logical_row}-{column}", "cell", len(units), "csv_cell",
                                           {"row":canonical_row,"column":column},text=cell,parent=row_id,
                                           metadata={"physical_line_start":start_line,"physical_line_end":end_line}))
                    logical_row += 1
        return units, {"encoding": encoding, "bom_bytes": bom, "delimiter": delimiter,
                       "row_count": logical_row}, warnings

    def _xml(self, path: str, maximum: int):
        import xml.etree.ElementTree as ET
        raw = Path(path).read_bytes()
        if re.search(br"<!DOCTYPE", raw[:_PROBE_BYTES], re.I):
            raise ValueError("DOCTYPE is not permitted")
        units: list[ExtractionUnit] = []
        warnings: list[str] = []
        stack: list[tuple[str, int]] = []
        child_counts: list[defaultdict[str, int]] = [defaultdict(int)]
        for event, element in ET.iterparse(path, events=("start", "end")):
            tag = str(element.tag)
            if event == "start":
                child_counts[-1][tag] += 1
                stack.append((tag, child_counts[-1][tag]))
                child_counts.append(defaultdict(int))
                continue
            xml_path = "/" + "/".join(f"{tag}[{index}]" for tag, index in stack)
            if len(units) < maximum:
                payload = {"tag": tag, "attributes": dict(element.attrib)}
                text_value = (element.text or "").strip() or None
                units.append(_unit(f"xml-element-{len(units)}", "element", len(units),
                                   "xml_element", {"xpath":xml_path}, text=text_value,
                                   structured_payload=payload if text_value is None else None,
                                   metadata={"attributes": dict(element.attrib)}))
                for attribute, value in element.attrib.items():
                    if len(units) >= maximum:
                        break
                    units.append(_unit(f"xml-attribute-{len(units)}", "attribute", len(units),
                                       "xml_element", {"xpath":xml_path,"attribute":attribute},
                                       text=value))
            stack.pop()
            child_counts.pop()
            element.clear()
        if len(units) >= maximum:
            warnings.append(f"unit limit {maximum} reached")
        return units, {"element_count": len(units)}, warnings

    def _html(self, path: str, maximum: int):
        raw, text, encoding, bom, decode_warnings = _read_text(path)
        parser = _DOMExtractor(text, maximum)
        parser.feed(text)
        parser.close()
        warnings = list(decode_warnings)
        if parser.unmatched_end_tags or parser.stack:
            warnings.append("malformed HTML recovered by tolerant parser")
        if len(parser.units) >= maximum:
            warnings.append(f"unit limit {maximum} reached")
        return parser.units, {"encoding": encoding, "bom_bytes": bom,
                              "text_node_count": len(parser.units)}, warnings

    def _yaml(self, path: str, maximum: int):
        raw, text, encoding, bom, decode_warnings = _read_text(path)
        documents = list(yaml.safe_load_all(text))
        units: list[ExtractionUnit] = []
        for index, value in enumerate(documents[:maximum]):
            payload = value if isinstance(value, (dict, list)) else None
            units.append(_unit(f"yaml-document-{index}", "document", index, "text_byte_span",
                               {"byte_start":bom,"byte_end":len(raw)},
                               text="null" if value is None else None,
                               value=value if payload is None and value is not None else None,
                               structured_payload=payload,metadata={"document_index":index}))
        warnings = list(decode_warnings)
        if len(documents) > maximum:
            warnings.append(f"unit limit {maximum} reached")
        return units, {"encoding": encoding, "bom_bytes": bom,
                       "document_count": len(documents)}, warnings

    def _lines(self, path: str, format_key: str, maximum: int):
        total_bytes = Path(path).stat().st_size
        with open(path, "rb") as raw_stream:
            prefix = raw_stream.read(_PROBE_BYTES)
        encoding, bom = _encoding(prefix)
        units: list[ExtractionUnit] = []
        offset = bom
        warnings: list[str] = []
        with open(path, "rb") as raw_stream:
            raw_stream.seek(bom)
            with io.TextIOWrapper(raw_stream, encoding=encoding, errors="replace", newline="") as stream:
                for line_number, line in enumerate(stream, 1):
                    if len(units) >= maximum:
                        break
                    byte_length = len(line.encode(encoding, errors="replace"))
                    display = line.rstrip("\r\n")
                    if "\ufffd" in display:
                        warnings.append(f"undecodable byte sequence replaced at line {line_number}")
                    units.append(_unit(f"text-line-{line_number}", "line", len(units), "text_line",
                                       {"line":line_number},text=display,
                                       metadata={"byte_start":offset,"byte_end":offset+byte_length}))
                    offset += byte_length
        if len(units) >= maximum and offset < total_bytes:
            warnings.append(f"unit limit {maximum} reached")
        return units, {"encoding": encoding, "bom_bytes": bom, "line_count": len(units),
                       "content_bytes": total_bytes}, warnings


def _valid_json_line(line: str) -> bool:
    try:
        json.loads(line)
        return True
    except json.JSONDecodeError:
        return False


def _sniff_delimiter(sample: str) -> str:
    bounded = sample[:_PROBE_BYTES]
    try:
        return csv.Sniffer().sniff(bounded, delimiters=_DELIMITERS).delimiter
    except csv.Error:
        # Deterministic frequency fallback, constrained to approved delimiters.
        counts = {delimiter: bounded.count(delimiter) for delimiter in _DELIMITERS}
        best = max(counts, key=counts.get)
        return best if counts[best] else ","
