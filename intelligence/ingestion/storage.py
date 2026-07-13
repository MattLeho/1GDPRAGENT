"""Local analytical storage primitives for Task 3 ingestion.

This module deliberately owns files only.  It does not publish database or graph
truth, which keeps an interrupted ingestion run safe to resume and reconcile.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


TEMP_MARKER = ".task3-tmp-"


class OptionalDependencyError(RuntimeError):
    """Raised when an explicitly requested storage backend is not installed."""


@dataclass(frozen=True, slots=True)
class StorageRoots:
    """Configurable, independently placeable roots for local ingestion data."""

    blobs: Path
    event_lake: Path
    analysis: Path
    cache: Path

    def __post_init__(self) -> None:
        for field_name in ("blobs", "event_lake", "analysis", "cache"):
            object.__setattr__(self, field_name, Path(getattr(self, field_name)))

    @classmethod
    def from_base(cls, base: str | os.PathLike[str] = "data") -> "StorageRoots":
        base_path = Path(base)
        return cls(
            blobs=base_path / "blobs",
            event_lake=base_path / "event_lake",
            analysis=base_path / "analysis",
            cache=base_path / "cache",
        )

    @classmethod
    def from_env(
        cls,
        base: str | os.PathLike[str] | None = None,
        *,
        environ: Mapping[str, str] | None = None,
    ) -> "StorageRoots":
        values = os.environ if environ is None else environ
        default = Path(base or values.get("GDPR_DATA_ROOT", "data"))
        return cls(
            blobs=Path(values.get("GDPR_BLOB_ROOT", default / "blobs")),
            event_lake=Path(values.get("GDPR_EVENT_LAKE_ROOT", default / "event_lake")),
            analysis=Path(values.get("GDPR_ANALYSIS_ROOT", default / "analysis")),
            cache=Path(values.get("GDPR_CACHE_ROOT", default / "cache")),
        )

    def ensure(self) -> "StorageRoots":
        for root in (self.blobs, self.event_lake, self.analysis, self.cache):
            root.mkdir(parents=True, exist_ok=True)
        return self


@dataclass(frozen=True, slots=True)
class BlobWriteResult:
    path: Path
    sha256: str
    byte_size: int
    created: bool

    @property
    def file_hash(self) -> str:
        return self.sha256


@dataclass(frozen=True, slots=True)
class PartitionMetadata:
    path: Path
    row_count: int
    min_occurred_at: datetime | None
    max_occurred_at: datetime | None
    schema_version: str
    sha256: str
    byte_size: int

    @property
    def file_hash(self) -> str:
        return self.sha256

    @property
    def min_time(self) -> datetime | None:
        return self.min_occurred_at

    @property
    def max_time(self) -> datetime | None:
        return self.max_occurred_at


def _sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_copy_stream(source: Any, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination.name}{TEMP_MARKER}", dir=destination.parent
        )
        temporary = Path(temp_name)
        with os.fdopen(fd, "wb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except PermissionError:
                # A failed native writer can briefly retain a Windows handle.
                # Preserve the original exception; startup cleanup recognises
                # and removes this marked temporary file.
                pass


def write_raw_blob(
    root: str | os.PathLike[str],
    content: bytes | bytearray | memoryview | Any,
) -> BlobWriteResult:
    """Atomically store raw bytes under a SHA-256 content address.

    File-like inputs are spooled once so hashing never requires loading the whole
    source into memory.  Existing content addresses are reused.
    """

    root_path = Path(root)
    root_path.mkdir(parents=True, exist_ok=True)
    spool_fd, spool_name = tempfile.mkstemp(prefix=f".blob{TEMP_MARKER}", dir=root_path)
    spool_path = Path(spool_name)
    digest = hashlib.sha256()
    byte_size = 0
    try:
        with os.fdopen(spool_fd, "wb") as spool:
            if isinstance(content, (bytes, bytearray, memoryview)):
                chunks = (bytes(content),)
            elif hasattr(content, "read"):
                chunks = iter(lambda: content.read(1024 * 1024), b"")
            else:
                raise TypeError("content must be bytes-like or a binary file-like object")
            for chunk in chunks:
                if not isinstance(chunk, (bytes, bytearray, memoryview)):
                    raise TypeError("binary file-like object returned non-bytes data")
                raw = bytes(chunk)
                digest.update(raw)
                spool.write(raw)
                byte_size += len(raw)
            spool.flush()
            os.fsync(spool.fileno())

        sha256 = digest.hexdigest()
        destination = root_path / sha256[:2] / sha256[2:4] / sha256
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.stat().st_size != byte_size or _sha256_file(destination) != sha256:
                raise OSError(f"content-address collision or corrupt blob at {destination}")
            created = False
        else:
            os.replace(spool_path, destination)
            created = True
        return BlobWriteResult(destination, sha256, byte_size, created)
    finally:
        spool_path.unlink(missing_ok=True)


def cleanup_temp_files(root: str | os.PathLike[str]) -> tuple[Path, ...]:
    """Remove Task 3 temporary files in deterministic path order."""

    root_path = Path(root)
    if not root_path.exists():
        return ()
    removed: list[Path] = []
    for path in sorted(root_path.rglob(f"*{TEMP_MARKER}*"), key=lambda item: item.as_posix()):
        if path.is_file() or path.is_symlink():
            path.unlink(missing_ok=True)
            removed.append(path)
    return tuple(removed)


def _require_pyarrow() -> tuple[Any, Any]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:
        raise OptionalDependencyError(
            "Parquet support requires the optional 'pyarrow' dependency"
        ) from exc
    return pa, pq


def _coerce_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if hasattr(value, "as_py"):
        value = value.as_py()
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    raise ValueError(f"unsupported partition timestamp value: {value!r}")


def write_parquet_partition(
    path: str | os.PathLike[str],
    rows: Iterable[Mapping[str, Any]] | Sequence[Mapping[str, Any]] | Any,
    *,
    schema_version: str,
    time_column: str = "occurred_at",
    compression: str = "zstd",
) -> PartitionMetadata:
    """Atomically write one non-empty, batched Parquet partition."""

    if not schema_version:
        raise ValueError("schema_version must not be empty")
    pa, pq = _require_pyarrow()
    if isinstance(rows, pa.Table):
        table = rows
    elif hasattr(rows, "to_arrow"):
        table = rows.to_arrow()
    else:
        materialised = list(rows)
        if not materialised:
            raise ValueError("empty Parquet partitions are not allowed")
        table = pa.Table.from_pylist(materialised)
    if table.num_rows == 0:
        raise ValueError("empty Parquet partitions are not allowed")

    destination = Path(path)
    if destination.suffix.lower() != ".parquet":
        raise ValueError("Parquet partition path must end in .parquet")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{destination.name}{TEMP_MARKER}", dir=destination.parent
        )
        os.close(fd)
        temporary = Path(temp_name)
        pq.write_table(table, temporary, compression=compression)
        # Windows rejects fsync on a read-only descriptor; r+b is portable and
        # does not mutate the already-written Parquet bytes.
        with temporary.open("r+b") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except PermissionError:
                # A failed native Parquet writer can briefly retain a Windows
                # handle. Preserve the original error for the caller.
                pass

    minimum = maximum = None
    if time_column in table.column_names:
        times = [_coerce_time(item) for item in table[time_column] if item.as_py() is not None]
        if times:
            minimum, maximum = min(times), max(times)
    return PartitionMetadata(
        path=destination,
        row_count=table.num_rows,
        min_occurred_at=minimum,
        max_occurred_at=maximum,
        schema_version=schema_version,
        sha256=_sha256_file(destination),
        byte_size=destination.stat().st_size,
    )


def read_parquet_polars(paths: str | os.PathLike[str] | Sequence[str | os.PathLike[str]], **kwargs: Any) -> Any:
    """Read Parquet lazily with Polars."""

    try:
        import polars as pl
    except ImportError as exc:
        raise OptionalDependencyError(
            "Polars reads require the optional 'polars' dependency"
        ) from exc
    source = str(paths) if isinstance(paths, (str, os.PathLike)) else [str(path) for path in paths]
    return pl.scan_parquet(source, **kwargs)


def read_parquet_duckdb(
    paths: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
    *,
    connection: Any | None = None,
) -> Any:
    """Return a DuckDB relation over one or more Parquet partitions."""

    try:
        import duckdb
    except ImportError as exc:
        raise OptionalDependencyError(
            "DuckDB reads require the optional 'duckdb' dependency"
        ) from exc
    database = connection or duckdb.connect(database=":memory:")
    source = str(paths) if isinstance(paths, (str, os.PathLike)) else [str(path) for path in paths]
    return database.read_parquet(source)


# Clear compatibility names for callers that describe the operation rather than
# the on-disk format.
atomic_write_blob = write_raw_blob
atomic_write_parquet_partition = write_parquet_partition
cleanup_interrupted_writes = cleanup_temp_files
