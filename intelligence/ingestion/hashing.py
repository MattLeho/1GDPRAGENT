"""Byte-exact and format-specific canonical hashing primitives.

Canonical hashes are deliberately separate from raw hashes.  A canonicaliser may
normalise representation, but it never replaces or mutates the source bytes.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Callable
from html.parser import HTMLParser
from pathlib import Path
import re
import xml.etree.ElementTree as ET


Canonicaliser = Callable[[bytes], bytes]


def raw_sha256(data: bytes | bytearray | memoryview) -> str:
    """Return the SHA-256 of the exact supplied bytes."""
    return hashlib.sha256(bytes(data)).hexdigest()


def raw_file_sha256(path: str | Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Stream a file into SHA-256 without materialising it in memory."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        while chunk := source.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_json_loads(text: str):
    def reject_constant(value: str):
        raise ValueError(f"non-standard JSON constant: {value}")

    def reject_duplicate_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON object key: {key}")
            result[key] = value
        return result

    return json.loads(
        text, parse_constant=reject_constant, object_pairs_hook=reject_duplicate_keys
    )


def canonicalise_json(data: bytes) -> bytes:
    value = _strict_json_loads(data.decode("utf-8-sig"))
    return json.dumps(
        value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


def _canonicalise_delimited(data: bytes, delimiter: str) -> bytes:
    text = data.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True)
    output = io.StringIO(newline="")
    writer = csv.writer(output, delimiter=delimiter, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    for row in reader:
        writer.writerow(row)
    return output.getvalue().encode("utf-8")


def canonicalise_csv(data: bytes) -> bytes:
    return _canonicalise_delimited(data, ",")


def canonicalise_tsv(data: bytes) -> bytes:
    return _canonicalise_delimited(data, "\t")


_UNSAFE_XML = re.compile(br"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)


def canonicalise_xml(data: bytes) -> bytes:
    """Canonicalise XML while refusing DTD/entity declarations."""
    if _UNSAFE_XML.search(data):
        raise ValueError("DTD and entity declarations are not accepted")
    text = data.decode("utf-8-sig")
    # stdlib C14N normalises attributes, namespaces and insignificant syntax.
    try:
        canonical = ET.canonicalize(xml_data=text, strip_text=False, with_comments=False)
    except (ET.ParseError, ValueError) as exc:
        raise ValueError(f"invalid XML: {exc}") from exc
    return canonical.encode("utf-8")


class _CanonicalHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tokens: list[object] = []

    def handle_starttag(self, tag: str, attrs):
        self.tokens.append(["start", tag.lower(), sorted((k.lower(), v or "") for k, v in attrs)])

    def handle_startendtag(self, tag: str, attrs):
        self.tokens.append(["empty", tag.lower(), sorted((k.lower(), v or "") for k, v in attrs)])

    def handle_endtag(self, tag: str):
        self.tokens.append(["end", tag.lower()])

    def handle_data(self, data: str):
        if data:
            self.tokens.append(["text", data])

    def handle_comment(self, data: str):
        # Comments do not affect extracted document structure.
        return

    def handle_decl(self, decl: str):
        self.tokens.append(["decl", decl.lower()])


def canonicalise_html(data: bytes) -> bytes:
    parser = _CanonicalHTMLParser()
    try:
        parser.feed(data.decode("utf-8-sig"))
        parser.close()
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"invalid HTML input: {exc}") from exc
    return json.dumps(parser.tokens, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class CanonicalHashRegistry:
    """Explicit registry; unknown formats never receive an invented canonical hash."""

    def __init__(self) -> None:
        self._canonicalisers: dict[str, Canonicaliser] = {}

    def register(self, format_key: str, canonicaliser: Canonicaliser, *, replace: bool = False) -> None:
        key = format_key.strip().lower()
        if not key:
            raise ValueError("format_key is required")
        if key in self._canonicalisers and not replace:
            raise ValueError(f"canonicaliser already registered for {key}")
        self._canonicalisers[key] = canonicaliser

    def formats(self) -> tuple[str, ...]:
        return tuple(sorted(self._canonicalisers))

    def canonical_bytes(self, format_key: str, data: bytes) -> bytes:
        try:
            canonicaliser = self._canonicalisers[format_key.strip().lower()]
        except KeyError as exc:
            raise KeyError(f"no canonicaliser registered for {format_key!r}") from exc
        return canonicaliser(data)

    def hash(self, format_key: str, data: bytes) -> str:
        return raw_sha256(self.canonical_bytes(format_key, data))


CANONICAL_HASH_REGISTRY = CanonicalHashRegistry()
for _key, _function in {
    "json": canonicalise_json,
    "geojson": canonicalise_json,
    "csv": canonicalise_csv,
    "tsv": canonicalise_tsv,
    "xml": canonicalise_xml,
    "html": canonicalise_html,
}.items():
    CANONICAL_HASH_REGISTRY.register(_key, _function)


def canonical_hash(data: bytes, format_key: str) -> str:
    return CANONICAL_HASH_REGISTRY.hash(format_key, data)


# US-spelling aliases for callers that use "canonicalize".
canonicalize_json = canonicalise_json
canonicalize_csv = canonicalise_csv
canonicalize_tsv = canonicalise_tsv
canonicalize_xml = canonicalise_xml
canonicalize_html = canonicalise_html
sha256_bytes = raw_sha256
sha256_file = raw_file_sha256
