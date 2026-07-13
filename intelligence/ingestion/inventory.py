"""Streaming filesystem inventory and archive safety inspection.

This module deliberately stops at inventory.  It never extracts archive members
to disk and does not decide which file-family adapter should process them.
"""

from __future__ import annotations

import bz2
import gzip
import lzma
import os
import re
import stat
import tarfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Iterator
from uuid import UUID

from .models import ArchiveMemberObservation, InventoryEntry, QuarantineStatus


_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")
_ARCHIVE_SUFFIXES = (
    ".zip",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".gz",
    ".bz2",
    ".xz",
)


class InventorySecurityError(ValueError):
    """Raised when the requested inventory target escapes its workspace."""


@dataclass(frozen=True, slots=True)
class ArchiveSafetyPolicy:
    """Global limits applied before archive contents can enter ingestion."""

    workspace_root: Path
    max_members: int = 100_000
    max_total_expanded_bytes: int = 10 * 1024 * 1024 * 1024
    max_member_expanded_bytes: int = 2 * 1024 * 1024 * 1024
    max_expansion_ratio: float = 1_000.0
    max_nesting_depth: int = 5
    stream_chunk_bytes: int = 1024 * 1024

    def __post_init__(self) -> None:
        root = Path(self.workspace_root).expanduser().resolve(strict=False)
        object.__setattr__(self, "workspace_root", root)
        for name in (
            "max_members",
            "max_total_expanded_bytes",
            "max_member_expanded_bytes",
            "max_nesting_depth",
            "stream_chunk_bytes",
        ):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.max_expansion_ratio <= 0:
            raise ValueError("max_expansion_ratio must be positive")


@dataclass(frozen=True, slots=True)
class ArchiveInspection:
    """Metadata-only result suitable for catalogue/quarantine decisions."""

    archive_format: str
    observations: tuple[ArchiveMemberObservation, ...]
    compressed_size: int
    declared_expanded_bytes: int
    member_count: int
    maximum_nesting_depth: int
    quarantine_status: QuarantineStatus = QuarantineStatus.NONE
    violations: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.quarantine_status is QuarantineStatus.NONE

    @property
    def expansion_ratio(self) -> float | None:
        if self.compressed_size == 0:
            return None if self.declared_expanded_bytes == 0 else float("inf")
        return self.declared_expanded_bytes / self.compressed_size


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_target(path: str | os.PathLike[str], policy: ArchiveSafetyPolicy) -> Path:
    target = Path(path).expanduser().resolve(strict=False)
    if not _is_within(target, policy.workspace_root):
        raise InventorySecurityError(
            f"inventory target {target} escapes workspace {policy.workspace_root}"
        )
    return target


def iter_inventory(
    root: str | os.PathLike[str],
    policy: ArchiveSafetyPolicy,
    *,
    parent_artifact_id: UUID | None = None,
) -> Iterator[InventoryEntry]:
    """Yield file and symlink inventory entries without retaining the tree.

    Directory symlinks are reported but never followed.  Only the current
    directory iterator is retained, including for directories with many files.
    """

    inventory_root = _safe_target(root, policy)
    if not inventory_root.is_dir():
        raise NotADirectoryError(inventory_root)

    def walk(directory: Path) -> Iterator[InventoryEntry]:
        # Do not sort: retaining a million-entry directory defeats streaming.
        with os.scandir(directory) as entries:
            for entry in entries:
                entry_path = Path(entry.path)
                relative_path = entry_path.relative_to(inventory_root).as_posix()
                is_symlink = entry.is_symlink()
                info = entry.stat(follow_symlinks=False)
                if is_symlink or entry.is_file(follow_symlinks=False):
                    yield InventoryEntry(
                        relative_path=relative_path,
                        size=info.st_size,
                        modified_at=datetime.fromtimestamp(info.st_mtime, timezone.utc),
                        is_symlink=is_symlink,
                        parent_artifact_id=parent_artifact_id,
                    )
                elif entry.is_dir(follow_symlinks=False):
                    resolved = entry_path.resolve(strict=False)
                    if not _is_within(resolved, policy.workspace_root):
                        raise InventorySecurityError(
                            f"directory {entry_path} resolves outside configured workspace"
                        )
                    yield from walk(entry_path)

    yield from walk(inventory_root)


def _member_path_flags(name: str) -> tuple[bool, bool]:
    portable = name.replace("\\", "/")
    absolute = (
        portable.startswith("/")
        or portable.startswith("//")
        or bool(_DRIVE_PATH.match(name))
    )
    depth = 0
    traversal = False
    for part in PurePosixPath(portable).parts:
        if part in ("", ".", "/"):
            continue
        if part == "..":
            if depth == 0:
                traversal = True
            else:
                depth -= 1
        else:
            depth += 1
    return traversal, absolute


def _is_nested_archive(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith(_ARCHIVE_SUFFIXES)


def _ratio(uncompressed: int | None, compressed: int | None) -> float | None:
    if uncompressed is None or compressed is None:
        return None
    if compressed == 0:
        return None if uncompressed == 0 else float("inf")
    return uncompressed / compressed


def _zip_symlink(member: zipfile.ZipInfo) -> bool:
    unix_mode = member.external_attr >> 16
    return stat.S_ISLNK(unix_mode)


def _bounded_decompressed_size(stream: BinaryIO, policy: ArchiveSafetyPolicy) -> int:
    total = 0
    while True:
        chunk = stream.read(
            min(policy.stream_chunk_bytes, policy.max_total_expanded_bytes - total + 1)
        )
        if not chunk:
            return total
        total += len(chunk)
        if total > policy.max_member_expanded_bytes:
            raise OverflowError("member_expanded_byte_limit")
        if total > policy.max_total_expanded_bytes:
            raise OverflowError("total_expanded_byte_limit")


def _quarantine(violations: set[str], *, encrypted: bool = False) -> QuarantineStatus:
    if encrypted:
        return QuarantineStatus.ENCRYPTED
    if violations:
        return QuarantineStatus.POLICY_LIMIT
    return QuarantineStatus.NONE


def _apply_limits(
    *,
    policy: ArchiveSafetyPolicy,
    member_count: int,
    total_expanded: int,
    expanded: int | None,
    ratio: float | None,
    depth: int,
    violations: set[str],
) -> None:
    if member_count > policy.max_members:
        violations.add("member_count_limit")
    if total_expanded > policy.max_total_expanded_bytes:
        violations.add("total_expanded_byte_limit")
    if expanded is not None and expanded > policy.max_member_expanded_bytes:
        violations.add("member_expanded_byte_limit")
    if ratio is not None and ratio > policy.max_expansion_ratio:
        violations.add("expansion_ratio_limit")
    if depth > policy.max_nesting_depth:
        violations.add("nesting_depth_limit")


def inspect_archive(
    path: str | os.PathLike[str],
    outer_artifact_id: UUID,
    policy: ArchiveSafetyPolicy,
    *,
    archive_depth: int = 0,
) -> ArchiveInspection:
    """Inspect a P0 archive without materialising archive members to disk."""

    if archive_depth < 0:
        raise ValueError("archive_depth cannot be negative")
    archive_path = _safe_target(path, policy)
    if not archive_path.is_file():
        raise FileNotFoundError(archive_path)
    compressed_size = archive_path.stat().st_size
    lowered = archive_path.name.lower()
    archive_format = "unknown"
    try:
        if lowered.endswith(".zip"):
            archive_format = "zip"
            return _inspect_zip(
                archive_path, outer_artifact_id, policy, archive_depth, compressed_size
            )
        if lowered.endswith((".tar", ".tar.gz", ".tgz")):
            archive_format = "tar.gz" if lowered.endswith((".tar.gz", ".tgz")) else "tar"
            return _inspect_tar(
                archive_path,
                outer_artifact_id,
                policy,
                archive_depth,
                compressed_size,
                archive_format,
            )
        if lowered.endswith(".gz"):
            opener, archive_format, member_name = gzip.open, "gzip", archive_path.stem
        elif lowered.endswith(".bz2"):
            opener, archive_format, member_name = bz2.open, "bzip2", archive_path.stem
        elif lowered.endswith(".xz"):
            opener, archive_format, member_name = lzma.open, "xz", archive_path.stem
        else:
            raise ValueError(f"unsupported archive format: {archive_path.name}")
        return _inspect_single_stream(
            archive_path,
            outer_artifact_id,
            policy,
            archive_depth,
            compressed_size,
            opener,
            archive_format,
            member_name,
        )
    except (zipfile.BadZipFile, tarfile.TarError, EOFError, OSError, lzma.LZMAError):
        return ArchiveInspection(
            archive_format=archive_format,
            observations=(),
            compressed_size=compressed_size,
            declared_expanded_bytes=0,
            member_count=0,
            maximum_nesting_depth=archive_depth + 1,
            quarantine_status=QuarantineStatus.CORRUPT,
            violations=("corrupt_archive",),
        )


def _inspect_zip(
    path: Path,
    artifact_id: UUID,
    policy: ArchiveSafetyPolicy,
    archive_depth: int,
    compressed_size: int,
) -> ArchiveInspection:
    observations: list[ArchiveMemberObservation] = []
    violations: set[str] = set()
    if archive_depth + 1 > policy.max_nesting_depth:
        violations.add("nesting_depth_limit")
    seen: set[str] = set()
    total_expanded = 0
    encrypted = False
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        declared_member_count = len(members)
        if declared_member_count > policy.max_members:
            violations.add("member_count_limit")
        # Once the count is unsafe, retain only enough observations to prove it.
        for ordinal, member in enumerate(members[: policy.max_members + 1]):
            name = member.filename
            canonical_name = name.replace("\\", "/")
            duplicate = canonical_name in seen
            seen.add(canonical_name)
            traversal, absolute = _member_path_flags(name)
            nested_depth = archive_depth + 1 + int(_is_nested_archive(name))
            ratio = _ratio(member.file_size, member.compress_size)
            total_expanded += member.file_size
            encrypted = encrypted or bool(member.flag_bits & 0x1)
            if traversal:
                violations.add("path_traversal")
            if absolute:
                violations.add("absolute_member_path")
            _apply_limits(
                policy=policy,
                member_count=ordinal + 1,
                total_expanded=total_expanded,
                expanded=member.file_size,
                ratio=ratio,
                depth=nested_depth,
                violations=violations,
            )
            observations.append(
                ArchiveMemberObservation(
                    outer_artifact_id=artifact_id,
                    member_path=name,
                    member_ordinal=ordinal,
                    compressed_size=member.compress_size,
                    uncompressed_size=member.file_size,
                    expansion_ratio=ratio,
                    nesting_depth=archive_depth + 1,
                    duplicate_path=duplicate,
                    traversal_attempt=traversal,
                    absolute_path=absolute,
                    symlink=_zip_symlink(member),
                )
            )
    return ArchiveInspection(
        archive_format="zip",
        observations=tuple(observations),
        compressed_size=compressed_size,
        declared_expanded_bytes=total_expanded,
        member_count=declared_member_count,
        maximum_nesting_depth=max(
            (archive_depth + 1 + int(_is_nested_archive(o.member_path)) for o in observations),
            default=archive_depth + 1,
        ),
        quarantine_status=_quarantine(violations, encrypted=encrypted),
        violations=tuple(sorted(violations)),
    )


def _inspect_tar(
    path: Path,
    artifact_id: UUID,
    policy: ArchiveSafetyPolicy,
    archive_depth: int,
    compressed_size: int,
    archive_format: str,
) -> ArchiveInspection:
    observations: list[ArchiveMemberObservation] = []
    violations: set[str] = set()
    if archive_depth + 1 > policy.max_nesting_depth:
        violations.add("nesting_depth_limit")
    seen: set[str] = set()
    total_expanded = 0
    # Streaming mode reads headers sequentially and never seeks into/extracts members.
    with tarfile.open(path, mode="r|*") as archive:
        for ordinal, member in enumerate(archive):
            name = member.name
            canonical_name = name.replace("\\", "/")
            duplicate = canonical_name in seen
            seen.add(canonical_name)
            traversal, absolute = _member_path_flags(name)
            nested_depth = archive_depth + 1 + int(_is_nested_archive(name))
            expanded = member.size if member.isfile() else 0
            total_expanded += expanded
            if traversal:
                violations.add("path_traversal")
            if absolute:
                violations.add("absolute_member_path")
            if member.issym() or member.islnk():
                link_traversal, link_absolute = _member_path_flags(member.linkname)
                if link_traversal or link_absolute:
                    violations.add("symlink_target_escape")
            _apply_limits(
                policy=policy,
                member_count=ordinal + 1,
                total_expanded=total_expanded,
                expanded=expanded,
                ratio=None,
                depth=nested_depth,
                violations=violations,
            )
            observations.append(
                ArchiveMemberObservation(
                    outer_artifact_id=artifact_id,
                    member_path=name,
                    member_ordinal=ordinal,
                    compressed_size=None,
                    uncompressed_size=expanded,
                    expansion_ratio=None,
                    nesting_depth=archive_depth + 1,
                    duplicate_path=duplicate,
                    traversal_attempt=traversal,
                    absolute_path=absolute,
                    symlink=member.issym() or member.islnk(),
                )
            )
            if ordinal + 1 > policy.max_members:
                # Do not scan an attacker-controlled unbounded header stream.
                break
    return ArchiveInspection(
        archive_format=archive_format,
        observations=tuple(observations),
        compressed_size=compressed_size,
        declared_expanded_bytes=total_expanded,
        member_count=len(observations),
        maximum_nesting_depth=max(
            (archive_depth + 1 + int(_is_nested_archive(o.member_path)) for o in observations),
            default=archive_depth + 1,
        ),
        quarantine_status=_quarantine(violations),
        violations=tuple(sorted(violations)),
    )


def _inspect_single_stream(
    path: Path,
    artifact_id: UUID,
    policy: ArchiveSafetyPolicy,
    archive_depth: int,
    compressed_size: int,
    opener,
    archive_format: str,
    member_name: str,
) -> ArchiveInspection:
    violations: set[str] = set()
    depth = archive_depth + 1 + int(_is_nested_archive(member_name))
    expanded = 0
    try:
        with opener(path, "rb") as stream:
            expanded = _bounded_decompressed_size(stream, policy)
    except OverflowError as error:
        violations.add(str(error))
        expanded = policy.max_total_expanded_bytes + 1
    ratio = _ratio(expanded, compressed_size)
    _apply_limits(
        policy=policy,
        member_count=1,
        total_expanded=expanded,
        expanded=expanded,
        ratio=ratio,
        depth=depth,
        violations=violations,
    )
    observation = ArchiveMemberObservation(
        outer_artifact_id=artifact_id,
        member_path=member_name,
        member_ordinal=0,
        compressed_size=compressed_size,
        uncompressed_size=expanded,
        expansion_ratio=ratio,
        nesting_depth=archive_depth + 1,
    )
    return ArchiveInspection(
        archive_format=archive_format,
        observations=(observation,),
        compressed_size=compressed_size,
        declared_expanded_bytes=expanded,
        member_count=1,
        maximum_nesting_depth=depth,
        quarantine_status=_quarantine(violations),
        violations=tuple(sorted(violations)),
    )


__all__ = [
    "ArchiveInspection",
    "ArchiveSafetyPolicy",
    "InventorySecurityError",
    "inspect_archive",
    "iter_inventory",
]
