from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest
from PIL import Image

from execution.adapters import invoke_engine
from ingestion.materialization import OperationalTemporalMaterializer
from ingestion.models import ActionClass, ActivityEvent, TemporalPrecision
from ingestion.registry import FORMATS_BY_KEY
from test_task1_database_integration import migrated_database


ROOT = Path(__file__).resolve().parents[1]


def _event(subject_id: str, occurred_at: datetime, action: ActionClass) -> ActivityEvent:
    event_id = uuid4()
    return ActivityEvent(
        event_id=event_id,
        record_signature=(event_id.hex * 2),
        subject_id=subject_id,
        export_snapshot_id=uuid4(),
        artifact_id=uuid4(),
        service="fixture",
        data_domain="behaviour",
        event_type=action.value.lower(),
        action_class=action,
        occurred_at=occurred_at,
        temporal_precision=TemporalPrecision.SECOND,
        parser_id="fixture",
        parser_version="1",
        source_locator_id=uuid4(),
    )


def test_image_origin_route_is_honest_and_executable(tmp_path):
    registry = (ROOT / "frontend/lib/execution/registry.ts").read_text(encoding="utf-8")
    assert "'image.origin_classification'" in registry
    assert "'deterministic_image_origin'" in registry
    assert "image.origin_classification','document.ocr" not in registry
    assert "'local_visual'" in registry

    screenshot = tmp_path / "Screenshot 2026-01-01.png"
    Image.new("RGB", (1280, 720), "white").save(screenshot)
    result = invoke_engine("deterministic_image_origin", "image.origin_classification", {"file_path": str(screenshot)}, None, {})
    assert result["origin"] == "screenshot"
    assert result["status"] == "candidate"
    assert result["physical_presence_supported"] is False

    camera = tmp_path / "camera.jpg"
    exif = Image.Exif()
    exif[271] = "Fixture Camera"
    exif[272] = "Model One"
    exif[36867] = "2025:03:04 10:11:12"
    Image.new("RGB", (640, 480), "blue").save(camera, exif=exif)
    camera_result = invoke_engine("deterministic_image_origin", "image.origin_classification", {"file_path": str(camera)}, None, {})
    assert camera_result["origin"] == "camera_origin"
    assert camera_result["features"]["capture_time_present"] is True
    assert camera_result["physical_presence_supported"] is False

    for format_key in ("jpeg", "png", "webp", "tiff", "heif", "bmp", "gif"):
        assert "image.origin_classification" in FORMATS_BY_KEY[format_key].task_routes


@pytest.mark.asyncio
async def test_ingestion_materializes_features_and_temporal_outputs_idempotently(migrated_database):
    url, request_id, _file_id = migrated_database
    connection = await asyncpg.connect(url)
    try:
        run_id = await connection.fetchval(
            "INSERT INTO analysis_runs(run_type,request_id,status,pipeline_version) VALUES('task3-materialisation',$1,'running','task3-v1') RETURNING id",
            request_id,
        )
        start = datetime(2025, 1, 1, tzinfo=timezone.utc)
        events = (
            _event("subject-1", start, ActionClass.SEARCHED),
            _event("subject-1", start + timedelta(days=1), ActionClass.CREATED),
            _event("subject-1", start + timedelta(days=2), ActionClass.CODED),
            _event("subject-1", start + timedelta(days=3), ActionClass.COMMUNICATED),
        )
        materializer = OperationalTemporalMaterializer(connection)
        first = await materializer.materialize(
            analysis_run_id=run_id,
            partition_file_hash="a" * 64,
            events=events,
            artifact_paths={event.artifact_id: f"fixture/{event.event_type}.json" for event in events},
        )
        second = await materializer.materialize(
            analysis_run_id=run_id,
            partition_file_hash="a" * 64,
            events=events,
        )
        assert first == second
        assert first["feature_count"] > 0
        assert first["aggregate_count"] > 0
        assert first["state_count"] == 1
        assert await connection.fetchval("SELECT count(*) FROM temporal_materialisation_runs WHERE analysis_run_id=$1", run_id) == 1
        assert await connection.fetchval("SELECT count(*) FROM deterministic_feature_candidates WHERE analysis_run_id=$1", run_id) == first["feature_count"]
        assert await connection.fetchval("SELECT count(*) FROM temporal_aggregates WHERE analysis_run_id=$1", run_id) == first["aggregate_count"]
        assert await connection.fetchval("SELECT count(*) FROM temporal_states WHERE analysis_run_id=$1 AND state_type='engagement_profile'", run_id) == 1
    finally:
        await connection.close()
