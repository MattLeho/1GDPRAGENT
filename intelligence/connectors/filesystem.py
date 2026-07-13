"""User-root-scoped filesystem and photo/media SourceConnectors."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import fnmatch
import hashlib
import mimetypes
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .definitions import FILESYSTEM_DEFINITION, PHOTO_FOLDER_DEFINITION
from .models import ConnectorInstance, ConnectorRawRecord
from .registry import ConnectorSyncBatch, ConnectorSyncRequest
from .signatures import canonical_json, connector_record_signature


class PhotoAnalysisMode(str, Enum):
    METADATA_ONLY = "metadata_only"
    SELECTED_VISUAL_ANALYSIS = "selected_visual_analysis"
    FULL_VISUAL_ANALYSIS = "full_visual_analysis"


class FolderConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    roots: tuple[str, ...]
    include: tuple[str, ...] = ("**/*", "*")
    exclude: tuple[str, ...] = ()
    max_size: int = Field(default=256 * 1024 * 1024, ge=1)
    supported_types: tuple[str, ...] = ()
    metadata_only_paths: tuple[str, ...] = ()
    content_analysis_paths: tuple[str, ...] = ()
    mode: PhotoAnalysisMode | None = None
    visual_analysis_paths: tuple[str, ...] = ()

    @model_validator(mode="after")
    def explicit_roots(self):
        if not self.roots:
            raise ValueError("at least one user-selected root is required")
        for value in self.roots:
            path = Path(value).expanduser()
            if not path.is_absolute():
                raise ValueError("filesystem connector roots must be absolute")
        return self


_PHOTO_TYPES = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".heic", ".heif", ".gif", ".bmp", ".mp4", ".mov", ".mkv", ".webm"}


class FolderConnector:
    def __init__(self, instance: ConnectorInstance) -> None:
        self.instance = instance
        self.photo = instance.definition_key == PHOTO_FOLDER_DEFINITION.key
        self.definition = PHOTO_FOLDER_DEFINITION if self.photo else FILESYSTEM_DEFINITION
        raw = dict(instance.configuration)
        if self.photo:
            raw.setdefault("mode", PhotoAnalysisMode.METADATA_ONLY.value)
            raw.pop("supported_types", None); raw.pop("metadata_only_paths", None); raw.pop("content_analysis_paths", None)
        else:
            raw.pop("mode", None); raw.pop("visual_analysis_paths", None)
        self.config = FolderConfiguration.model_validate(raw)

    def acquire(self, request: ConnectorSyncRequest) -> ConnectorSyncBatch:
        before = dict(request.cursor.position.get("files") or {}) if request.cursor else {}
        current: dict[str, dict[str, Any]] = {}
        records: list[ConnectorRawRecord] = []
        for root_value in self.config.roots:
            root = Path(root_value).expanduser().resolve(strict=True)
            if not root.is_dir():
                raise ValueError(f"selected connector root is not a directory: {root}")
            root_id = hashlib.sha256(str(root).casefold().encode()).hexdigest()[:16]
            for source in root.rglob("*"):
                if not source.is_file():
                    continue
                resolved = source.resolve(strict=True)
                try:
                    relative = resolved.relative_to(root).as_posix()
                except ValueError:
                    continue  # symlink escaped the user-selected root
                key = f"{root_id}/{relative}"
                if not self._selected(relative, resolved):
                    continue
                stat = resolved.stat()
                if stat.st_size > self.config.max_size:
                    continue
                payload = resolved.read_bytes()
                digest = hashlib.sha256(payload).hexdigest()
                state = {"sha256": digest, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "relative_path": relative, "root_id": root_id}
                current[key] = state
                previous = before.get(key)
                if previous and previous.get("sha256") == digest:
                    continue
                records.append(self._file_record(resolved, relative, root_id, payload, digest, "modified" if previous else "created", stat.st_mtime))
        for key, previous in before.items():
            if key not in current:
                records.append(self._removed_record(key, previous))
        watermark = hashlib.sha256(canonical_json(current)).hexdigest()
        return ConnectorSyncBatch(
            records=tuple(sorted(records, key=lambda item: item.source_record_id)),
            cursor_position={"files": current}, source_watermark=watermark,
        )

    def _selected(self, relative: str, path: Path) -> bool:
        if self.photo:
            suffix = path.suffix.casefold()
            is_sidecar = suffix == ".json" and path.with_suffix("").suffix.casefold() in _PHOTO_TYPES and path.with_suffix("").is_file()
            if suffix not in _PHOTO_TYPES and not is_sidecar:
                return False
        if self.config.supported_types and path.suffix.casefold().lstrip(".") not in {value.casefold().lstrip(".") for value in self.config.supported_types}:
            return False
        included = any(fnmatch.fnmatch(relative, pattern) for pattern in self.config.include)
        excluded = any(fnmatch.fnmatch(relative, pattern) for pattern in self.config.exclude)
        return included and not excluded

    def _file_record(self, path, relative, root_id, payload, digest, change_kind, modified):
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        sidecar = self.photo and path.suffix.casefold() == ".json"
        data_class = "photo.media_sidecar" if sidecar else "photo.media" if self.photo else "filesystem.file"
        requested_tasks: tuple[str, ...] = ()
        required = ["media.metadata"] if self.photo else ["files.read"]
        if self.photo and not sidecar:
            mode = self.config.mode or PhotoAnalysisMode.METADATA_ONLY
            selected = mode is PhotoAnalysisMode.FULL_VISUAL_ANALYSIS or (
                mode is PhotoAnalysisMode.SELECTED_VISUAL_ANALYSIS and
                any(fnmatch.fnmatch(relative, pattern) for pattern in self.config.visual_analysis_paths)
            )
            if selected:
                required.append("media.visual_analysis")
                requested_tasks = ("image.caption",) if media_type.startswith("image/") else ("speech.transcription",)
        elif any(fnmatch.fnmatch(relative, pattern) for pattern in self.config.content_analysis_paths):
            # The canonical Task 3 support registry validates whether these are
            # supported for the actual detected type.
            requested_tasks = ()
        metadata = {
            "file_name": path.name, "path": relative, "root_id": root_id,
            "content_sha256": digest, "change_kind": change_kind,
            "analysis_mode": (self.config.mode.value if self.photo and self.config.mode else "scoped"),
            "sidecar_for": path.with_suffix("").name if sidecar else None,
            "requested_tasks": list(requested_tasks),
        }
        occurred = datetime.fromtimestamp(modified, tz=timezone.utc)
        source_id = f"{root_id}:{relative}"
        signature = connector_record_signature(
            source_record_id=source_id, source_record_version=digest, payload=payload,
            data_class=data_class, occurred_at=occurred, media_type=media_type,
            source_metadata=metadata,
        )
        return ConnectorRawRecord(
            connector_instance_id=self.instance.id, source_record_id=source_id,
            source_record_version=digest, record_signature=signature,
            data_class=data_class, occurred_at=occurred, observed_at=datetime.now(timezone.utc),
            media_type=media_type, payload=payload, source_metadata=metadata,
            required_permissions=tuple(required),
        )

    def _removed_record(self, key: str, previous: dict[str, Any]):
        document = {"change_kind": "removed", "path_key": key, "previous": previous}
        payload = canonical_json(document)
        metadata = {"change_kind": "removed", "removed_path": previous.get("relative_path"), "root_id": previous.get("root_id")}
        source_id = f"removed:{key}:{previous.get('sha256')}"
        permissions = ("media.metadata",) if self.photo else ("files.read",)
        signature = connector_record_signature(
            source_record_id=source_id, source_record_version="removed-1", payload=payload,
            data_class="filesystem.observation", media_type="application/json",
            source_metadata=metadata,
        )
        return ConnectorRawRecord(
            connector_instance_id=self.instance.id, source_record_id=source_id,
            source_record_version="removed-1", record_signature=signature,
            data_class="filesystem.observation", observed_at=datetime.now(timezone.utc),
            media_type="application/json", payload=payload, source_metadata=metadata,
            required_permissions=permissions,
        )
