from __future__ import annotations

import bz2
import gzip
import io
import lzma
import stat
import tarfile
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest

from ingestion.inventory import (
    ArchiveSafetyPolicy,
    InventorySecurityError,
    inspect_archive,
    iter_inventory,
)
from ingestion.models import QuarantineStatus


def policy(root: Path, **overrides) -> ArchiveSafetyPolicy:
    values = {
        "workspace_root": root,
        "max_members": 20,
        "max_total_expanded_bytes": 100_000,
        "max_member_expanded_bytes": 100_000,
        "max_expansion_ratio": 1_000,
        "max_nesting_depth": 3,
        "stream_chunk_bytes": 32,
    }
    values.update(overrides)
    return ArchiveSafetyPolicy(**values)


def test_directory_inventory_streams_relative_files_and_does_not_follow_symlinks(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    (source / "nested").mkdir()
    (source / "nested" / "event.json").write_text("{}", encoding="utf-8")
    link = source / "event-link"
    try:
        link.symlink_to(source / "nested" / "event.json")
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")

    iterator = iter_inventory(source, policy(tmp_path))
    assert not isinstance(iterator, (list, tuple))
    entries = {entry.relative_path: entry for entry in iterator}

    assert entries["nested/event.json"].size == 2
    assert entries["event-link"].is_symlink is True
    assert len(entries) == 2


def test_inventory_and_archive_targets_cannot_escape_workspace(tmp_path):
    outside = tmp_path.parent / "outside-inventory"
    outside.mkdir(exist_ok=True)
    with pytest.raises(InventorySecurityError, match="escapes workspace"):
        list(iter_inventory(outside, policy(tmp_path)))

    archive = outside / "outside.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("ok.txt", b"ok")
    with pytest.raises(InventorySecurityError, match="escapes workspace"):
        inspect_archive(archive, uuid4(), policy(tmp_path))


def test_zip_reports_sizes_ratios_duplicates_and_symlinks_without_extracting(tmp_path):
    archive = tmp_path / "metadata.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("record.json", b'{"a": 1}')
        bundle.writestr("record.json", b'{"a": 2}')
        symlink = zipfile.ZipInfo("link")
        symlink.create_system = 3
        symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
        bundle.writestr(symlink, "record.json")

    result = inspect_archive(archive, uuid4(), policy(tmp_path))

    assert result.accepted
    assert result.member_count == 3
    assert result.declared_expanded_bytes == sum(
        item.uncompressed_size or 0 for item in result.observations
    )
    assert result.observations[1].duplicate_path is True
    assert result.observations[2].symlink is True
    assert result.observations[0].compressed_size is not None
    assert result.observations[0].expansion_ratio is not None
    assert not (tmp_path / "record.json").exists()


def test_zip_quarantines_traversal_and_absolute_member_paths(tmp_path):
    archive = tmp_path / "paths.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escape.txt", b"escape")
        bundle.writestr("/absolute.txt", b"absolute")
        bundle.writestr("C:\\windows.txt", b"windows")

    result = inspect_archive(archive, uuid4(), policy(tmp_path))

    assert result.quarantine_status is QuarantineStatus.POLICY_LIMIT
    assert set(result.violations) == {"absolute_member_path", "path_traversal"}
    assert result.observations[0].traversal_attempt
    assert result.observations[1].absolute_path
    assert result.observations[2].absolute_path
    assert not (tmp_path.parent / "escape.txt").exists()


def test_tar_streaming_inspection_tracks_traversal_symlink_and_duplicates(tmp_path):
    archive = tmp_path / "malicious.tar"
    with tarfile.open(archive, "w") as bundle:
        for name in ("safe.txt", "safe.txt", "../../escape.txt"):
            payload = b"content"
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            bundle.addfile(info, io.BytesIO(payload))
        link = tarfile.TarInfo("link")
        link.type = tarfile.SYMTYPE
        link.linkname = "../../outside"
        bundle.addfile(link)

    result = inspect_archive(archive, uuid4(), policy(tmp_path))

    assert result.quarantine_status is QuarantineStatus.POLICY_LIMIT
    assert result.observations[1].duplicate_path
    assert result.observations[2].traversal_attempt
    assert result.observations[3].symlink
    assert all(item.compressed_size is None for item in result.observations)


@pytest.mark.parametrize("suffix", [".gz", ".bz2", ".xz"])
def test_single_stream_formats_are_bounded_and_report_observed_expansion(tmp_path, suffix):
    archive = tmp_path / f"payload{suffix}"
    payload = b"personal-data" * 50
    if suffix == ".gz":
        with gzip.open(archive, "wb") as stream:
            stream.write(payload)
    elif suffix == ".bz2":
        archive.write_bytes(bz2.compress(payload))
    else:
        archive.write_bytes(lzma.compress(payload))

    result = inspect_archive(archive, uuid4(), policy(tmp_path))

    assert result.accepted
    assert result.member_count == 1
    assert result.declared_expanded_bytes == len(payload)
    assert result.expansion_ratio and result.expansion_ratio > 1


def test_member_count_total_bytes_expansion_and_nesting_limits_quarantine(tmp_path):
    count_archive = tmp_path / "count.zip"
    with zipfile.ZipFile(count_archive, "w") as bundle:
        bundle.writestr("one", b"1")
        bundle.writestr("two", b"2")
    count = inspect_archive(count_archive, uuid4(), policy(tmp_path, max_members=1))
    assert "member_count_limit" in count.violations

    bomb_archive = tmp_path / "bomb.zip"
    with zipfile.ZipFile(bomb_archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("zeros", b"0" * 20_000)
    bomb = inspect_archive(
        bomb_archive,
        uuid4(),
        policy(
            tmp_path,
            max_total_expanded_bytes=10_000,
            max_member_expanded_bytes=5_000,
            max_expansion_ratio=2,
        ),
    )
    assert {
        "total_expanded_byte_limit",
        "member_expanded_byte_limit",
        "expansion_ratio_limit",
    }.issubset(bomb.violations)

    nested_archive = tmp_path / "nested.zip"
    with zipfile.ZipFile(nested_archive, "w") as bundle:
        bundle.writestr("inner.zip", b"not opened")
    nested = inspect_archive(
        nested_archive, uuid4(), policy(tmp_path, max_nesting_depth=1)
    )
    assert "nesting_depth_limit" in nested.violations
    assert nested.maximum_nesting_depth == 2


def test_corrupt_archives_are_catalogued_as_quarantined(tmp_path):
    archive = tmp_path / "corrupt.zip"
    archive.write_bytes(b"PK\x03\x04truncated")

    result = inspect_archive(archive, uuid4(), policy(tmp_path))

    assert result.quarantine_status is QuarantineStatus.CORRUPT
    assert result.violations == ("corrupt_archive",)
    assert result.member_count == 0
