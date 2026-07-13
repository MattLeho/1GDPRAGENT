"""Non-semantic file-type evidence collection and truth reconciliation."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from .models import FileTypeEvidence, FileTypeTruth, FileTypeTruthValue
from .registry import FORMAT_SUPPORT_REGISTRY


EXTENSION_FORMATS={extension.lower():record.format_key for record in FORMAT_SUPPORT_REGISTRY for extension in record.supported_extensions}
MIME_FORMATS={mime.lower():record.format_key for record in FORMAT_SUPPORT_REGISTRY for mime in record.supported_mime_types}
FORMAT_MIMES={record.format_key:(record.supported_mime_types[0] if record.supported_mime_types else None) for record in FORMAT_SUPPORT_REGISTRY}
_SORTED_EXTENSIONS=tuple(sorted(EXTENSION_FORMATS,key=len,reverse=True))


def _signature_format(data: bytes) -> tuple[str, float] | None:
    signatures = (
        (b"%PDF-", "pdf"), (b"PK\x03\x04", "zip"), (b"\x1f\x8b", "gzip"),
        (b"\x89PNG\r\n\x1a\n", "png"), (b"\xff\xd8\xff", "jpeg"),
        (b"GIF87a", "gif"), (b"GIF89a", "gif"), (b"SQLite format 3\x00", "sqlite"),
    )
    for prefix, format_key in signatures:
        if data.startswith(prefix):
            return format_key, 1.0
    # Markup prologs are structural signatures, but less decisive than binary magic.
    sample = data[:4096].lstrip(b"\xef\xbb\xbf\x00\t\r\n ").lower()
    if sample.startswith(b"<?xml"):
        return "xml", 0.9
    if sample.startswith(b"<!doctype html") or sample.startswith(b"<html"):
        return "html", 0.9
    return None


def collect_file_type_evidence(
    path: str | Path,
    *,
    declared_mime: str | None = None,
    data: bytes | None = None,
    parser_probe_evidence: Iterable[FileTypeEvidence] = (),
) -> tuple[FileTypeEvidence, ...]:
    lowered=str(path).lower()
    suffix=next((extension for extension in _SORTED_EXTENSIONS if lowered.endswith(extension)),Path(path).suffix.lower())
    evidence: list[FileTypeEvidence] = [FileTypeEvidence(
        source="extension", value=suffix or None, candidate_format=EXTENSION_FORMATS.get(suffix),
        confidence=1.0 if suffix in EXTENSION_FORMATS else 0.0,
    )]
    if declared_mime is not None:
        mime = declared_mime.split(";", 1)[0].strip().lower()
        evidence.append(FileTypeEvidence(
            source="declared_mime", value=declared_mime, candidate_format=MIME_FORMATS.get(mime),
            confidence=1.0 if mime in MIME_FORMATS else 0.0,
        ))
    if data is not None:
        match = _signature_format(data)
        evidence.append(FileTypeEvidence(
            source="signature", value=match[0] if match else None,
            candidate_format=match[0] if match else None, confidence=match[1] if match else 0.0,
        ))
    for item in parser_probe_evidence:
        if item.source != "parser_probe":
            raise ValueError("parser_probe_evidence must have source='parser_probe'")
        evidence.append(item)
    return tuple(evidence)


def determine_file_type_truth(evidence: Iterable[FileTypeEvidence]) -> FileTypeTruth:
    items = tuple(evidence)
    candidates = [(item.source, item.candidate_format, item.confidence) for item in items
                  if item.candidate_format and item.confidence > 0]
    formats = {candidate for _, candidate, _ in candidates}
    strong = {candidate for source, candidate, confidence in candidates
              if source in {"signature", "parser_probe"} and confidence >= 0.7}
    corroborated = {candidate for candidate in formats
                    if len({source for source, value, _ in candidates if value == candidate}) >= 2}

    if not candidates or (len(candidates) == 1 and candidates[0][0] == "extension"):
        return FileTypeTruth(status=FileTypeTruthValue.UNKNOWN, evidence=items,
                             reason="no corroborated content evidence")
    if len(strong) > 1:
        return FileTypeTruth(status=FileTypeTruthValue.AMBIGUOUS, evidence=items,
                             reason="content probes disagree")
    if strong:
        detected = next(iter(strong))
        conflicts = {value for source, value, _ in candidates if source != "parser_probe" and value != detected}
        status = FileTypeTruthValue.MISMATCH if conflicts else (
            FileTypeTruthValue.MATCH if detected in corroborated else FileTypeTruthValue.AMBIGUOUS
        )
        reason = "content evidence conflicts with declared metadata" if conflicts else (
            "independent evidence agrees" if status == FileTypeTruthValue.MATCH else "content evidence is uncorroborated"
        )
        return FileTypeTruth(status=status, detected_format=detected,
                             detected_mime=FORMAT_MIMES.get(detected), evidence=items, reason=reason)
    if len(formats) > 1:
        return FileTypeTruth(status=FileTypeTruthValue.AMBIGUOUS, evidence=items,
                             reason="metadata evidence disagrees")
    detected = next(iter(formats))
    if detected in corroborated:
        return FileTypeTruth(status=FileTypeTruthValue.MATCH, detected_format=detected,
                             detected_mime=FORMAT_MIMES.get(detected), evidence=items,
                             reason="independent metadata evidence agrees")
    return FileTypeTruth(status=FileTypeTruthValue.UNKNOWN, evidence=items,
                         reason="insufficient independent evidence")


def classify_file_type(path: str | Path, *, declared_mime: str | None = None,
                       data: bytes | None = None,
                       parser_probe_evidence: Iterable[FileTypeEvidence] = ()) -> FileTypeTruth:
    return determine_file_type_truth(collect_file_type_evidence(
        path, declared_mime=declared_mime, data=data, parser_probe_evidence=parser_probe_evidence
    ))
