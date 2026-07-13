from __future__ import annotations

import bz2
import gzip
import io
import lzma
import struct
import tarfile
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest

from ingestion.adapters.archives import ArchiveAdapter
from ingestion.inventory import ArchiveSafetyPolicy
from ingestion.models import (
    ExtractionContext,
    FileTypeEvidence,
    FileTypeTruth,
    FileTypeTruthValue,
    QuarantineStatus,
)


def _policy(root: Path, **overrides) -> ArchiveSafetyPolicy:
    values = {
        "workspace_root": root,
        "max_members": 20,
        "max_total_expanded_bytes": 100_000,
        "max_member_expanded_bytes": 100_000,
        "max_expansion_ratio": 1_000,
        "max_nesting_depth": 4,
        "stream_chunk_bytes": 32,
    }
    values.update(overrides)
    return ArchiveSafetyPolicy(**values)


def _context(path: Path, policy: ArchiveSafetyPolicy, **configuration):
    artifact_id = uuid4()
    return ExtractionContext(
        artifact_id=artifact_id,
        analysis_run_id=uuid4(),
        export_snapshot_id=uuid4(),
        source_path=str(path),
        archive_depth=configuration.pop("archive_depth", 0),
        configuration={"archive_safety_policy": policy, **configuration},
    )


def _truth(format_key: str):
    return FileTypeTruth(
        status=FileTypeTruthValue.MATCH,
        detected_format=format_key,
        evidence=(FileTypeEvidence(source="signature", candidate_format=format_key),),
        reason="fixture",
    )


def _write_tar(path: Path, mode: str = "w") -> None:
    with tarfile.open(path, mode) as bundle:
        payload = b"record"
        info = tarfile.TarInfo("folder/./record.json")
        info.size = len(payload)
        bundle.addfile(info, io.BytesIO(payload))


@pytest.mark.parametrize(
    "name,format_key,writer",
    [
        ("data.zip", "zip", lambda p: zipfile.ZipFile(p, "w")),
        ("data.tar", "tar", lambda p: (_write_tar(p), None)[1]),
        ("data.tar.gz", "tar.gz", lambda p: (_write_tar(p, "w:gz"), None)[1]),
        ("data.tgz", "tar.gz", lambda p: (_write_tar(p, "w:gz"), None)[1]),
        ("data.gz", "gzip", lambda p: p.write_bytes(gzip.compress(b"record"))),
        ("data.bz2", "bzip2", lambda p: p.write_bytes(bz2.compress(b"record"))),
        ("data.xz", "xz", lambda p: p.write_bytes(lzma.compress(b"record"))),
    ],
)
def test_all_p0_formats_probe_and_emit_member_locators(tmp_path, name, format_key, writer):
    path = tmp_path / name
    if format_key == "zip":
        with writer(path) as bundle:
            bundle.writestr("folder/./record.json", b"record")
    else:
        writer(path)

    adapter = ArchiveAdapter()
    assert adapter.probe(str(path), _truth(format_key)).accepted
    context = _context(path, _policy(tmp_path))
    result = adapter.extract(str(path), context)

    assert result.quarantine_status is QuarantineStatus.NONE
    assert len(result.embedded_members) == len(result.units) == 1
    expected_member = (
        "folder/record.json"
        if format_key == "zip" or format_key.startswith("tar")
        else path.stem
    )
    assert result.embedded_members[0].member_path == expected_member
    locator = result.units[0].evidence_locator
    assert locator.locator_type == "archive_member"
    assert locator.locator["outer_artifact_id"] == context.artifact_id
    assert locator.locator["member_ordinal"] == 0


def test_duplicate_members_keep_distinct_ordinals_and_occurrences(tmp_path):
    path = tmp_path / "duplicates.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("same.json", b"one")
        bundle.writestr("same.json", b"two")

    result = ArchiveAdapter().extract(str(path), _context(path, _policy(tmp_path)))

    assert [member.member_path for member in result.embedded_members] == ["same.json", "same.json"]
    assert [member.ordinal for member in result.embedded_members] == [0, 1]
    assert result.embedded_members[1].metadata["duplicate_path"] is True
    assert [unit.evidence_locator.locator["member_ordinal"] for unit in result.units] == [0, 1]


def test_traversal_quarantines_without_exposing_reentry_members(tmp_path):
    path = tmp_path / "traversal.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("safe.txt", b"safe")
        bundle.writestr("../escape.txt", b"escape")

    result = ArchiveAdapter().extract(str(path), _context(path, _policy(tmp_path)))

    assert result.quarantine_status is QuarantineStatus.POLICY_LIMIT
    assert "path_traversal" in result.metadata["violations"]
    assert result.embedded_members == ()
    assert result.units == ()
    assert not (tmp_path.parent / "escape.txt").exists()


def test_expansion_breach_is_quarantined_before_member_emission(tmp_path):
    path = tmp_path / "bomb.zip"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("zeros", b"0" * 20_000)
    policy = _policy(
        tmp_path,
        max_total_expanded_bytes=10_000,
        max_member_expanded_bytes=5_000,
        max_expansion_ratio=2,
    )

    result = ArchiveAdapter().extract(str(path), _context(path, policy))

    assert result.quarantine_status is QuarantineStatus.POLICY_LIMIT
    assert "expansion_ratio_limit" in result.metadata["violations"]
    assert result.embedded_members == ()


def test_nested_archive_emits_reentry_depth_and_complete_lineage(tmp_path):
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as bundle:
        bundle.writestr("record.json", b"{}")
    path = tmp_path / "outer.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("nested/inner.zip", inner.getvalue())
    root_artifact = uuid4()
    context = _context(
        path,
        _policy(tmp_path),
        outer_artifact_id=root_artifact,
        nested_member_chain=("parent.zip",),
        archive_depth=1,
    )

    result = ArchiveAdapter().extract(str(path), context)

    member = result.embedded_members[0]
    assert member.metadata["nested_archive"] is True
    assert member.metadata["next_archive_depth"] == 2
    assert member.metadata["nested_member_chain"] == ["parent.zip", "nested/inner.zip"]
    locator = result.units[0].evidence_locator.locator
    assert locator["outer_artifact_id"] == root_artifact
    assert locator["nested_member_chain"] == ("parent.zip",)


def test_corrupt_archive_remains_visible_with_no_members(tmp_path):
    path = tmp_path / "corrupt.zip"
    path.write_bytes(b"PK\x03\x04truncated")

    result = ArchiveAdapter().extract(str(path), _context(path, _policy(tmp_path)))

    assert result.quarantine_status is QuarantineStatus.CORRUPT
    assert result.metadata["violations"] == ["corrupt_archive"]
    assert result.embedded_members == ()


def test_encrypted_zip_is_password_required_and_never_bruteforced(tmp_path):
    path = tmp_path / "encrypted.zip"
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr("secret.txt", b"secret")
    raw = bytearray(path.read_bytes())
    local = raw.find(b"PK\x03\x04")
    central = raw.find(b"PK\x01\x02")
    assert local >= 0 and central >= 0
    local_flags = struct.unpack_from("<H", raw, local + 6)[0] | 1
    central_flags = struct.unpack_from("<H", raw, central + 8)[0] | 1
    struct.pack_into("<H", raw, local + 6, local_flags)
    struct.pack_into("<H", raw, central + 8, central_flags)
    path.write_bytes(raw)

    result = ArchiveAdapter().extract(str(path), _context(path, _policy(tmp_path)))

    assert result.quarantine_status is QuarantineStatus.ENCRYPTED
    assert result.metadata["password_required"] is True
    assert result.embedded_members == ()
    assert any("no password attempts" in warning for warning in result.warnings)
