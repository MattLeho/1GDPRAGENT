from __future__ import annotations

import hashlib
import importlib.util
from datetime import datetime, timezone

import pytest

from ingestion.storage import (
    OptionalDependencyError,
    StorageRoots,
    cleanup_temp_files,
    read_parquet_duckdb,
    read_parquet_polars,
    write_parquet_partition,
    write_raw_blob,
)


def test_storage_roots_are_configurable_and_created(tmp_path):
    roots = StorageRoots(
        blobs=tmp_path / "raw",
        event_lake=tmp_path / "events",
        analysis=tmp_path / "derived",
        cache=tmp_path / "scratch",
    ).ensure()
    assert all(path.is_dir() for path in (roots.blobs, roots.event_lake, roots.analysis, roots.cache))


def test_raw_blobs_are_atomic_content_addressed_and_reused(tmp_path):
    payload = b"private source bytes\n"
    first = write_raw_blob(tmp_path, payload)
    second = write_raw_blob(tmp_path, payload)
    expected = hashlib.sha256(payload).hexdigest()
    assert first.sha256 == expected
    assert first.path.read_bytes() == payload
    assert first.created is True
    assert second.path == first.path
    assert second.created is False
    assert not tuple(tmp_path.rglob("*.task3-tmp-*"))


def test_temp_cleanup_is_deterministic_and_scoped(tmp_path):
    stale_b = tmp_path / "b.task3-tmp-2"
    stale_a = tmp_path / "nested" / "a.task3-tmp-1"
    keep = tmp_path / "ordinary.tmp"
    stale_a.parent.mkdir()
    for path in (stale_b, stale_a, keep):
        path.write_bytes(b"x")
    removed = cleanup_temp_files(tmp_path)
    assert removed == tuple(sorted((stale_b, stale_a), key=lambda path: path.as_posix()))
    assert keep.exists()


@pytest.mark.skipif(importlib.util.find_spec("pyarrow") is None, reason="pyarrow not installed")
def test_parquet_partition_write_metadata_and_read(tmp_path):
    first = datetime(2025, 1, 1, tzinfo=timezone.utc)
    second = datetime(2025, 1, 2, tzinfo=timezone.utc)
    destination = tmp_path / "service=test" / "events.parquet"
    metadata = write_parquet_partition(
        destination,
        ({"event_id": str(index), "occurred_at": moment} for index, moment in enumerate((second, first))),
        schema_version="activity-event/1",
    )
    assert metadata.row_count == 2
    assert metadata.min_occurred_at == first
    assert metadata.max_occurred_at == second
    assert metadata.byte_size == destination.stat().st_size
    assert metadata.sha256 == hashlib.sha256(destination.read_bytes()).hexdigest()
    if importlib.util.find_spec("polars") is not None:
        assert read_parquet_polars(destination).collect().height == 2
    if importlib.util.find_spec("duckdb") is not None:
        assert read_parquet_duckdb(destination).count("*").fetchone()[0] == 2


@pytest.mark.skipif(importlib.util.find_spec("pyarrow") is None, reason="pyarrow not installed")
def test_empty_parquet_partition_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="empty"):
        write_parquet_partition(tmp_path / "empty.parquet", [], schema_version="1")


def test_optional_read_helpers_have_clear_dependency_errors(tmp_path):
    if importlib.util.find_spec("polars") is None:
        with pytest.raises(OptionalDependencyError, match="polars"):
            read_parquet_polars(tmp_path / "missing.parquet")
    if importlib.util.find_spec("duckdb") is None:
        with pytest.raises(OptionalDependencyError, match="duckdb"):
            read_parquet_duckdb(tmp_path / "missing.parquet")
