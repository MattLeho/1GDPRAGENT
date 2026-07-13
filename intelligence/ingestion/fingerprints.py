"""Deterministic, non-semantic structure fingerprint providers."""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Sequence
import csv
import hashlib
from html.parser import HTMLParser
import io
import json
import re
import xml.etree.ElementTree as ET

from .models import StructureFingerprint


def _type_name(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "number"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    return "unknown"


def _fingerprint(family: str, provider_id: str, provider_version: str,
                 shape: dict[str, object], sample_count: int) -> StructureFingerprint:
    canonical = json.dumps(shape, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
    return StructureFingerprint(
        fingerprint_id=hashlib.sha256(canonical).hexdigest(), family=family,
        provider_id=provider_id, provider_version=provider_version,
        canonical_shape=shape, sample_count=sample_count,
    )


def _representative(value: object, depth: int = 0, max_depth: int = 8) -> object:
    if depth >= max_depth:
        return _type_name(value)
    if isinstance(value, dict):
        return {key: _representative(value[key], depth + 1, max_depth) for key in sorted(value)}
    if isinstance(value, list):
        shapes = {_shape_token(item, depth + 1, max_depth) for item in value[:100]}
        return {"array_items": sorted(shapes)}
    return _type_name(value)


def _shape_token(value: object, depth: int, max_depth: int) -> str:
    return json.dumps(_representative(value, depth, max_depth), sort_keys=True,
                      separators=(",", ":"))


def json_structure_fingerprint(data: bytes | str | object, *, sample_limit: int = 1000,
                               include_optional_frequencies: bool = True) -> StructureFingerprint:
    if sample_limit <= 0:
        raise ValueError("sample_limit must be positive")
    if isinstance(data, bytes):
        value = json.loads(data.decode("utf-8-sig"))
    elif isinstance(data, str):
        value = json.loads(data)
    else:
        value = data
    paths: set[str] = set()
    distribution: Counter[str] = Counter()
    max_array_depth = 0

    def walk(item: object, path: str, array_depth: int) -> None:
        nonlocal max_array_depth
        distribution[_type_name(item)] += 1
        if isinstance(item, dict):
            for key in sorted(item):
                child = f"{path}.{key}" if path else f"$.{key}"
                paths.add(child)
                walk(item[key], child, array_depth)
        elif isinstance(item, list):
            max_array_depth = max(max_array_depth, array_depth + 1)
            child = f"{path}[]" if path else "$[]"
            paths.add(child)
            for element in item[:sample_limit]:
                walk(element, child, array_depth + 1)

    walk(value, "$", 0)
    records = value[:sample_limit] if isinstance(value, list) else [value]
    object_records = [record for record in records if isinstance(record, dict)]
    shape: dict[str, object] = {
        "top_level_type": _type_name(value),
        "key_paths": sorted(paths),
        "array_depth": max_array_depth,
        "value_type_distribution": dict(sorted(distribution.items())),
        "representative_shape": _representative(value),
    }
    if include_optional_frequencies and object_records:
        counts = Counter(key for record in object_records for key in record)
        total = len(object_records)
        shape["top_level_field_frequencies"] = {
            key: {"present": counts[key], "sampled_records": total}
            for key in sorted(counts)
        }
    return _fingerprint("json", "json_structure", "1", shape, len(records))


_INTEGER = re.compile(r"^[+-]?\d+$")
_NUMBER = re.compile(r"^[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?$")


def _cell_type(value: str) -> str:
    if value == "":
        return "empty"
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return "boolean"
    if _INTEGER.fullmatch(value):
        return "integer"
    if _NUMBER.fullmatch(value):
        return "number"
    return "string"


def tabular_structure_fingerprint(data: bytes | str | Iterable[Sequence[str]], *,
                                  delimiter: str = ",", has_header: bool = True,
                                  sample_limit: int = 1000) -> StructureFingerprint:
    if len(delimiter) != 1:
        raise ValueError("delimiter must be one character")
    if isinstance(data, bytes):
        rows = csv.reader(io.StringIO(data.decode("utf-8-sig"), newline=""), delimiter=delimiter)
    elif isinstance(data, str):
        rows = csv.reader(io.StringIO(data, newline=""), delimiter=delimiter)
    else:
        rows = iter(data)
    sampled: list[list[str]] = []
    for row in rows:
        sampled.append([str(cell) for cell in row])
        if len(sampled) >= sample_limit + (1 if has_header else 0):
            break
    header = sampled.pop(0) if has_header and sampled else []
    width = max([len(header), *(len(row) for row in sampled)], default=0)
    columns = header + [f"column_{index + 1}" for index in range(len(header), width)]
    types: dict[str, Counter[str]] = {column: Counter() for column in columns}
    widths = Counter()
    for row in sampled:
        widths[str(len(row))] += 1
        for index, column in enumerate(columns):
            types[column][_cell_type(row[index] if index < len(row) else "")] += 1
    shape: dict[str, object] = {
        "delimiter": delimiter, "has_header": has_header, "columns": columns,
        "column_count": width, "row_width_distribution": dict(sorted(widths.items())),
        "column_type_distribution": {
            column: dict(sorted(types[column].items())) for column in columns
        },
    }
    return _fingerprint("tabular", "tabular_structure", "1", shape, len(sampled))


class _HTMLShapeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.paths: Counter[str] = Counter()
        self.attributes: dict[str, set[str]] = {}
        self.max_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        self.stack.append(tag)
        self.paths["/" + "/".join(self.stack)] += 1
        self.attributes.setdefault(tag, set()).update(key.lower() for key, _ in attrs)
        self.max_depth = max(self.max_depth, len(self.stack))

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in self.stack:
            reverse_index = self.stack[::-1].index(lowered)
            del self.stack[len(self.stack) - reverse_index - 1:]


def html_structure_fingerprint(data: bytes | str) -> StructureFingerprint:
    text = data.decode("utf-8-sig") if isinstance(data, bytes) else data
    parser = _HTMLShapeParser()
    parser.feed(text)
    parser.close()
    shape: dict[str, object] = {
        "element_paths": dict(sorted(parser.paths.items())),
        "attributes_by_element": {tag: sorted(values) for tag, values in sorted(parser.attributes.items())},
        "max_depth": parser.max_depth,
    }
    return _fingerprint("html", "html_structure", "1", shape, sum(parser.paths.values()))


_UNSAFE_XML = re.compile(br"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


def xml_structure_fingerprint(data: bytes | str) -> StructureFingerprint:
    raw = data.encode("utf-8") if isinstance(data, str) else data
    if _UNSAFE_XML.search(raw):
        raise ValueError("DTD and entity declarations are not accepted")
    root = ET.fromstring(raw)
    paths: Counter[str] = Counter()
    attributes: dict[str, set[str]] = {}
    max_depth = 0

    def walk(element: ET.Element, parent: str, depth: int) -> None:
        nonlocal max_depth
        path = f"{parent}/{element.tag}"
        paths[path] += 1
        attributes.setdefault(str(element.tag), set()).update(map(str, element.attrib))
        max_depth = max(max_depth, depth)
        for child in element:
            walk(child, path, depth + 1)

    walk(root, "", 1)
    shape: dict[str, object] = {
        "root_tag": root.tag, "element_paths": dict(sorted(paths.items())),
        "attributes_by_element": {tag: sorted(values) for tag, values in sorted(attributes.items())},
        "max_depth": max_depth,
    }
    return _fingerprint("xml", "xml_structure", "1", shape, sum(paths.values()))


# Concise aliases for callers selecting providers by family.
fingerprint_json = json_structure_fingerprint
fingerprint_tabular = tabular_structure_fingerprint
fingerprint_html = html_structure_fingerprint
fingerprint_xml = xml_structure_fingerprint

