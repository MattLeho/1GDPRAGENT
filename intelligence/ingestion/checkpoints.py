"""Deterministic stage keys and resumability primitives."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping
from uuid import UUID

from .models import CheckpointStatus, PipelineCheckpoint, PipelineStage


def _checkpoint(row) -> PipelineCheckpoint:
    values = dict(row)
    for key in ("progress", "error"):
        if isinstance(values.get(key), str):
            values[key] = json.loads(values[key])
    return PipelineCheckpoint(**values)


def checkpoint_key(*, stage: PipelineStage, item_key: str, content_hash: str | None = None, parser_version: str | None = None) -> str:
    if not item_key:
        raise ValueError("item_key is required")
    if content_hash is not None and (len(content_hash) != 64 or any(char not in "0123456789abcdef" for char in content_hash)):
        raise ValueError("content_hash must be lower-case SHA-256")
    payload = json.dumps({"stage": stage.value, "item_key": item_key, "content_hash": content_hash, "parser_version": parser_version}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


class CheckpointStore:
    def __init__(self, connection) -> None:
        self.connection = connection

    async def begin(self, *, analysis_run_id: UUID, stage: PipelineStage, item_key: str, content_hash: str | None = None, parser_version: str | None = None) -> PipelineCheckpoint:
        key = checkpoint_key(stage=stage, item_key=item_key, content_hash=content_hash, parser_version=parser_version)
        row = await self.connection.fetchrow(
            """INSERT INTO pipeline_checkpoints(analysis_run_id,stage,item_key,idempotency_key,content_hash,parser_version,status,started_at)
            VALUES($1,$2,$3,$4,$5,$6,'running',NOW())
            ON CONFLICT(analysis_run_id,stage,item_key,idempotency_key) DO UPDATE SET
              status=CASE WHEN pipeline_checkpoints.status='completed' THEN pipeline_checkpoints.status ELSE 'running' END,
              attempt=CASE WHEN pipeline_checkpoints.status='completed' THEN pipeline_checkpoints.attempt ELSE pipeline_checkpoints.attempt+1 END,
              started_at=CASE WHEN pipeline_checkpoints.status='completed' THEN pipeline_checkpoints.started_at ELSE NOW() END,
              updated_at=NOW()
            RETURNING analysis_run_id,stage,item_key,idempotency_key,content_hash,parser_version,status,attempt,progress,error""",
            analysis_run_id, stage.value, item_key, key, content_hash, parser_version,
        )
        return _checkpoint(row)

    async def finish(self, checkpoint: PipelineCheckpoint, *, status: CheckpointStatus = CheckpointStatus.COMPLETED, progress: Mapping[str, Any] | None = None, error: Mapping[str, Any] | None = None) -> PipelineCheckpoint:
        if status in {CheckpointStatus.PENDING, CheckpointStatus.RUNNING}:
            raise ValueError("finish status must be terminal")
        row = await self.connection.fetchrow(
            """UPDATE pipeline_checkpoints SET status=$5::pipeline_checkpoint_status,progress=$6::jsonb,error=$7::jsonb,
              completed_at=CASE WHEN $5::text IN ('completed','skipped') THEN NOW() ELSE completed_at END,updated_at=NOW()
            WHERE analysis_run_id=$1 AND stage=$2 AND item_key=$3 AND idempotency_key=$4
            RETURNING analysis_run_id,stage,item_key,idempotency_key,content_hash,parser_version,status,attempt,progress,error""",
            checkpoint.analysis_run_id, checkpoint.stage.value, checkpoint.item_key,
            checkpoint.idempotency_key, status.value, json.dumps(dict(progress or {})),
            json.dumps(dict(error)) if error else None,
        )
        if row is None:
            raise KeyError("checkpoint no longer exists")
        return _checkpoint(row)

    async def progress(self, analysis_run_id: UUID) -> tuple[PipelineCheckpoint, ...]:
        rows = await self.connection.fetch(
            """SELECT analysis_run_id,stage,item_key,idempotency_key,content_hash,parser_version,status,attempt,progress,error
            FROM pipeline_checkpoints WHERE analysis_run_id=$1 ORDER BY stage,item_key,updated_at""", analysis_run_id,
        )
        return tuple(_checkpoint(row) for row in rows)
