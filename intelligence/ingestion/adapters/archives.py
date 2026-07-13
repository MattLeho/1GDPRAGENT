"""Safe archive/container adapter for the Task 3 ingestion pipeline.

The adapter never extracts members to disk and never retains member payloads in
memory.  It delegates all admission decisions to :mod:`ingestion.inventory`,
then emits resolvable member occurrences for a caller-controlled re-entry step.
"""
from __future__ import annotations

import mimetypes
import tarfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID

from ..inventory import ArchiveInspection, ArchiveSafetyPolicy, inspect_archive
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


_FORMAT_BY_SUFFIX = (
    (".tar.gz", "tar.gz"),
    (".tgz", "tar.gz"),
    (".zip", "zip"),
    (".tar", "tar"),
    (".gz", "gzip"),
    (".bz2", "bzip2"),
    (".xz", "xz"),
)
_SUPPORTED_FORMATS = frozenset({"zip", "tar", "tar.gz", "tgz", "gzip", "bzip2", "xz"})
_NESTED_SUFFIXES = tuple(suffix for suffix, _ in _FORMAT_BY_SUFFIX)
_PROBE_BYTES = 512


def _suffix_format(path: str) -> str | None:
    lowered = Path(path).name.lower()
    for suffix, format_key in _FORMAT_BY_SUFFIX:
        if lowered.endswith(suffix):
            return format_key
    return None


def _normalise_format(value: str | None) -> str | None:
    if value is None:
        return None
    normalised = value.lower().replace("_", ".")
    aliases = {
        "tgz": "tar.gz",
        "gz": "gzip",
        "bz2": "bzip2",
        "tar.gzip": "tar.gz",
    }
    return aliases.get(normalised, normalised)


def _signature_format(path: str) -> str | None:
    with open(path, "rb") as stream:
        prefix = stream.read(_PROBE_BYTES)
    if prefix.startswith(b"PK\x03\x04") or prefix.startswith(b"PK\x05\x06") or prefix.startswith(b"PK\x07\x08"):
        return "zip"
    if prefix.startswith(b"\x1f\x8b"):
        return "gzip"
    if prefix.startswith(b"BZh"):
        return "bzip2"
    if prefix.startswith(b"\xfd7zXZ\x00"):
        return "xz"
    if len(prefix) >= 262 and prefix[257:262] == b"ustar":
        return "tar"
    return None


def _canonical_member_path(raw: str) -> str:
    """Return the portable canonical spelling of an already-admitted path."""

    portable = raw.replace("\\", "/")
    parts: list[str] = []
    for part in PurePosixPath(portable).parts:
        if part in ("", ".", "/"):
            continue
        if part == "..":
            if not parts:
                raise ValueError("archive member path escapes its container")
            parts.pop()
        else:
            parts.append(part)
    if not parts:
        raise ValueError("archive member path is empty")
    return "/".join(parts)


def _is_nested(path: str) -> bool:
    lowered = path.lower()
    return any(lowered.endswith(suffix) for suffix in _NESTED_SUFFIXES)


def _policy(path: str, context: ExtractionContext) -> ArchiveSafetyPolicy:
    configured = context.configuration.get("archive_safety_policy")
    if configured is not None:
        if not isinstance(configured, ArchiveSafetyPolicy):
            raise TypeError("archive_safety_policy must be an ArchiveSafetyPolicy")
        return configured

    values: dict[str, Any] = {}
    for name in (
        "max_members",
        "max_total_expanded_bytes",
        "max_member_expanded_bytes",
        "max_expansion_ratio",
        "max_nesting_depth",
        "stream_chunk_bytes",
    ):
        if name in context.configuration:
            values[name] = context.configuration[name]
    workspace = context.configuration.get("workspace_root", Path(path).resolve().parent)
    return ArchiveSafetyPolicy(workspace_root=Path(workspace), **values)


def _lineage(context: ExtractionContext) -> tuple[UUID, tuple[str, ...]]:
    outer = context.configuration.get("outer_artifact_id", context.artifact_id)
    if not isinstance(outer, UUID):
        outer = UUID(str(outer))
    raw_chain = context.configuration.get("nested_member_chain", ())
    chain = tuple(_canonical_member_path(str(item)) for item in raw_chain)
    return outer, chain


class ArchiveAdapter:
    adapter_id = "archives"
    adapter_version = "1"
    family = "archives"
    supported_mime_types = frozenset(
        {
            "application/zip",
            "application/x-tar",
            "application/gzip",
            "application/x-gzip",
            "application/x-bzip2",
            "application/x-xz",
        }
    )
    supported_extensions = frozenset(suffix for suffix, _ in _FORMAT_BY_SUFFIX)
    supports_streaming = True
    supports_nested_members = True
    locator_types = frozenset({"archive_member"})
    capability_flags = frozenset({"archive_members", "metadata"})

    def probe(self, path: str, truth: FileTypeTruth) -> ProbeResult:
        suffix_claim=_suffix_format(path)
        claimed = _normalise_format(truth.detected_format) or suffix_claim
        if claimed not in _SUPPORTED_FORMATS:
            return ProbeResult(
                accepted=False,
                confidence=0,
                detected_format=None,
                reason=f"archives does not support {claimed or 'unknown content'}",
            )
        try:
            signature = _signature_format(path)
            if signature is None:
                raise ValueError("no supported archive signature")
            if signature=="gzip" and suffix_claim=="tar.gz" and tarfile.is_tarfile(path):
                claimed="tar.gz"
            if claimed in {"tar.gz", "gzip"} and signature == "gzip":
                detected = claimed
            else:
                detected = signature
            if detected != claimed:
                return ProbeResult(
                    accepted=False,
                    confidence=0,
                    detected_format=detected,
                    reason=f"archive signature {detected} conflicts with {claimed}",
                )
            # Library probes reject truncated/corrupt headers without extracting.
            if detected == "zip" and not zipfile.is_zipfile(path):
                raise ValueError("invalid ZIP structure")
            if detected in {"tar", "tar.gz"} and not tarfile.is_tarfile(path):
                raise ValueError("invalid TAR structure")
        except (OSError, EOFError, ValueError, tarfile.TarError):
            return ProbeResult(
                accepted=False,
                confidence=0,
                detected_format=claimed,
                reason="bounded archive probe rejected content",
            )
        return ProbeResult(
            accepted=True,
            confidence=1.0,
            detected_format=claimed,
            reason=f"signature and bounded {claimed} probe accepted content",
        )

    def extract(self, path: str, context: ExtractionContext) -> ExtractionResult:
        format_key = _normalise_format(context.configuration.get("detected_format")) or _suffix_format(path) or "unknown"
        try:
            policy = _policy(path, context)
            inspection = inspect_archive(
                path,
                context.artifact_id,
                policy,
                archive_depth=context.archive_depth,
            )
            return self._result(inspection, format_key, context)
        except Exception as exc:
            return ExtractionResult(
                artifact_id=context.artifact_id,
                adapter_id=self.adapter_id,
                adapter_version=self.adapter_version,
                family=self.family,
                detected_format=format_key,
                metadata={},
                warnings=(f"archive extraction failed: {type(exc).__name__}: {exc}",),
                quarantine_status=QuarantineStatus.CORRUPT,
            )

    def _result(
        self,
        inspection: ArchiveInspection,
        format_key: str,
        context: ExtractionContext,
    ) -> ExtractionResult:
        metadata: dict[str, Any] = {
            "compressed_size": inspection.compressed_size,
            "declared_expanded_bytes": inspection.declared_expanded_bytes,
            "member_count": inspection.member_count,
            "maximum_nesting_depth": inspection.maximum_nesting_depth,
            "expansion_ratio": inspection.expansion_ratio,
            "violations": list(inspection.violations),
            "password_required": inspection.quarantine_status
            in {QuarantineStatus.ENCRYPTED, QuarantineStatus.PASSWORD_REQUIRED},
        }
        warnings = list(inspection.violations)

        # A non-admitted archive must not expose re-entry-ready occurrences.
        if not inspection.accepted:
            if metadata["password_required"]:
                warnings.append("encrypted archive requires a password; no password attempts were made")
            return ExtractionResult(
                artifact_id=context.artifact_id,
                adapter_id=self.adapter_id,
                adapter_version=self.adapter_version,
                family=self.family,
                detected_format=inspection.archive_format or format_key,
                metadata=metadata,
                warnings=tuple(dict.fromkeys(warnings)),
                quarantine_status=inspection.quarantine_status,
            )

        outer_artifact_id, parent_chain = _lineage(context)
        members: list[EmbeddedMember] = []
        units: list[ExtractionUnit] = []
        for observation in inspection.observations:
            if observation.member_path.replace("\\", "/").endswith("/"):
                continue
            if observation.symlink:
                warnings.append(f"symlink member omitted: {observation.member_path}")
                continue
            try:
                member_path = _canonical_member_path(observation.member_path)
            except ValueError:
                warnings.append(f"unsafe member omitted: {observation.member_path}")
                continue
            nested = _is_nested(member_path)
            media_type, _ = mimetypes.guess_type(member_path)
            member_metadata = {
                "compressed_size": observation.compressed_size,
                "uncompressed_size": observation.uncompressed_size,
                "expansion_ratio": observation.expansion_ratio,
                "duplicate_path": observation.duplicate_path,
                "archive_depth": observation.nesting_depth,
                "nested_archive": nested,
                "next_archive_depth": observation.nesting_depth if nested else None,
                "nested_member_chain": [*parent_chain, member_path] if nested else list(parent_chain),
            }
            members.append(
                EmbeddedMember(
                    member_path=member_path,
                    ordinal=observation.member_ordinal,
                    declared_size=observation.uncompressed_size,
                    media_type=media_type,
                    metadata=member_metadata,
                )
            )
            locator = {
                "member_path": member_path,
                "outer_artifact_id": outer_artifact_id,
                "nested_member_chain": parent_chain,
                "member_ordinal": observation.member_ordinal,
            }
            units.append(
                ExtractionUnit(
                    unit_id=f"archive-member-{observation.member_ordinal}",
                    unit_type="archive_member",
                    ordinal=observation.member_ordinal,
                    structured_payload={"member_path": member_path, **member_metadata},
                    evidence_locator=EvidenceLocatorValue(
                        locator_type="archive_member", locator=locator
                    ),
                )
            )
        return ExtractionResult(
            artifact_id=context.artifact_id,
            adapter_id=self.adapter_id,
            adapter_version=self.adapter_version,
            family=self.family,
            detected_format=inspection.archive_format or format_key,
            metadata=metadata,
            units=tuple(units),
            embedded_members=tuple(members),
            warnings=tuple(dict.fromkeys(warnings)),
            quarantine_status=QuarantineStatus.NONE,
        )


__all__ = ["ArchiveAdapter"]
