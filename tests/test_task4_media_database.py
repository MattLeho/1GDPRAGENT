from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from uuid import uuid4

import asyncpg
import pytest
from PIL import Image

from db.postgres import PostgresClient
from evidence.ledger import EvidenceLedger
from evidence.models import EvidenceLocatorCreate, LocatorType
from insights.models import InsightPeriod, LocationEvidenceClass, MediaOrigin, PeriodGranularity, TemporalMode
from insights.service import InsightService
from test_task1_database_integration import migrated_database


@pytest.mark.asyncio
async def test_metadata_pipeline_preserves_camera_screenshot_and_landmark_evidence(migrated_database, tmp_path):
    url, request_id, _ = migrated_database
    client = PostgresClient(url)
    connection = await asyncpg.connect(url)
    try:
        ledger = EvidenceLedger(client)
        profile_id=await connection.fetchval("INSERT INTO profiles(identity_name) VALUES('Media fixture') RETURNING id")
        run_id = await ledger.create_analysis_run("task4-media", "task4-v1", request_id=request_id,profile_id=profile_id)
        snapshot_id = await ledger.create_export_snapshot(run_id, "manual_import", request_id=request_id,profile_id=profile_id)
        occurred = datetime(2025, 6, 1, 12, tzinfo=timezone.utc)

        async def image_unit(name: str, metadata: dict):
            path = tmp_path / name
            Image.new("RGB", (100, 80), "white").save(path)
            content = path.read_bytes()
            _, artifact_id = await ledger.record_source_artifact(
                snapshot_id,content,storage_uri=path.resolve().as_uri(),original_path=name,
                file_name=name,detected_mime="image/png",extension=".png",file_type_status="matched",
            )
            locator_id = await ledger.create_locator(EvidenceLocatorCreate(
                artifact_id=artifact_id,locator_type=LocatorType.IMAGE_REGION,
                locator={"x":0,"y":0,"width":100,"height":80},
            ),content)
            await connection.execute(
                """INSERT INTO extraction_units
                (analysis_run_id,artifact_id,unit_key,unit_type,ordinal,structured_payload,metadata,
                 evidence_locator_id,adapter_id,adapter_version)
                VALUES($1,$2,'image:0','image_metadata',0,$3::jsonb,'{}',$4,'media','1.0.0')""",
                run_id,artifact_id,json.dumps(metadata),locator_id,
            )
            return artifact_id,locator_id

        camera_metadata={
            "capture_timestamp":"2025:06:01 12:00:00","timezone":"+00:00",
            "device":{"make":"Fixture","model":"Camera"},
            "gps":{"latitude":51.5246,"longitude":-0.1340},
        }
        camera_id,camera_locator=await image_unit("camera.png",camera_metadata)
        sidecar_content=json.dumps({"geoData":{"latitude":51.5247,"longitude":-0.1341},"photoTakenTime":{"timestamp":"1748779200"}}).encode()
        (tmp_path/"camera.png.json").write_bytes(sidecar_content)
        _,sidecar_artifact=await ledger.record_source_artifact(
            snapshot_id,sidecar_content,storage_uri=(tmp_path/"camera.png.json").resolve().as_uri(),
            original_path="camera.png.json",file_name="camera.png.json",detected_mime="application/json",
            extension=".json",file_type_status="matched",
        )
        sidecar_locator=await ledger.create_locator(EvidenceLocatorCreate(
            artifact_id=sidecar_artifact,locator_type=LocatorType.JSON_POINTER,locator={"pointer":"/geoData"},
        ),sidecar_content)
        await connection.execute(
            """INSERT INTO extraction_units
            (analysis_run_id,artifact_id,unit_key,unit_type,ordinal,structured_payload,metadata,
             evidence_locator_id,adapter_id,adapter_version)
            VALUES($1,$2,'json:0','structured_record',0,$3::jsonb,'{}',$4,'json','1.0.0')""",
            run_id,sidecar_artifact,sidecar_content.decode(),sidecar_locator,
        )
        screenshot_id,screenshot_locator=await image_unit("Screenshot UCL.png",camera_metadata)
        downloaded_metadata={**camera_metadata,"device":{},"capture_timestamp":None,"downloaded_from":"https://example.invalid/paris"}
        downloaded_id,_=await image_unit("Downloads Paris.png",downloaded_metadata)
        await connection.execute(
            """INSERT INTO specialist_task_requests
            (analysis_run_id,artifact_id,task_key,input_manifest,status,output_manifest,completed_at)
            VALUES($1,$2,'image.landmark_candidate','{}','completed',$3::jsonb,NOW())""",
            run_id,screenshot_id,json.dumps({"candidate":{"place_label":"UCL","confidence":0.9}}),
        )
        for task_key,output in (
            ("image.origin_classification",{"origin":"screenshot","confidence":0.99,"features":{"name_hint":True}}),
            ("image.ocr",{"text":"GitHub browser dashboard ucl.ac.uk","words":[{"text":"GitHub"}]}),
            ("image.caption",{"text":"A browser interface","topics":["software"],"entities":["UCL"]}),
        ):
            await connection.execute(
                """INSERT INTO specialist_task_requests
                (analysis_run_id,artifact_id,task_key,input_manifest,status,output_manifest,completed_at)
                VALUES($1,$2,$3,$4::jsonb,'completed',$5::jsonb,NOW())""",
                run_id,screenshot_id,task_key,json.dumps({"evidence_locator_id":str(screenshot_locator)}),json.dumps(output),
            )

        period=InsightPeriod(
            mode=TemporalMode.PERIOD,granularity=PeriodGranularity.MONTH,
            from_at=occurred-timedelta(days=1),to_at=occurred+timedelta(days=2),
        )
        places=await InsightService(client).get_place_insights(subject_id=str(profile_id),period=period)
        camera=next(item for item in places.candidates if item.artifact_id==camera_id and item.basis.value=="exif_gps")
        assert camera.media_origin is MediaOrigin.CAMERA_ORIGIN
        assert camera.evidence_class is LocationEvidenceClass.STRONG_OBSERVATION
        sidecar=next(item for item in places.candidates if item.artifact_id==camera_id and item.basis.value=="takeout_sidecar")
        assert sidecar.evidence_class is LocationEvidenceClass.STRONG_OBSERVATION
        assert sidecar.evidence[1].artifact_id==sidecar_artifact
        confirmed=await InsightService(client).confirm_media_location(
            artifact_id=camera_id,evidence_locator_id=camera_locator,reviewed_by="fixture-user",
            occurred_at=occurred,place_label="Confirmed UCL",analysis_run_id=run_id,
            profile_id=profile_id,
        )
        assert confirmed.evidence_class is LocationEvidenceClass.USER_CONFIRMED
        refreshed=await InsightService(client).get_place_insights(subject_id=str(profile_id),period=period)
        assert any(item.insight_id==confirmed.insight_id for item in refreshed.candidates)
        screenshot_rows=[item for item in places.candidates if item.artifact_id==screenshot_id]
        assert {item.basis.value for item in screenshot_rows}=={"exif_gps","visual_landmark"}
        assert all(item.media_origin is MediaOrigin.SCREENSHOT for item in screenshot_rows)
        assert all(item.evidence_class is LocationEvidenceClass.CANDIDATE for item in screenshot_rows)
        downloaded=next(item for item in places.candidates if item.artifact_id==downloaded_id)
        assert downloaded.media_origin is MediaOrigin.DOWNLOADED_MEDIA
        assert downloaded.evidence_class is LocationEvidenceClass.CANDIDATE
        landmark=next(item for item in screenshot_rows if item.basis.value=="visual_landmark")
        assert landmark.place_label=="UCL"
        assert landmark.evidence[1].locator_id==screenshot_locator
        content=next(item for item in places.media_content_candidates if item.artifact_id==screenshot_id)
        assert content.media_origin is MediaOrigin.SCREENSHOT
        assert content.application_candidates==("github",)
        assert content.webpage_candidates==("ucl.ac.uk",)
        assert content.visible_topic_candidates==("software",)
        content_trace=await InsightService(client).trace_insight(
            content.insight_id,profile_id=profile_id,
        )
        assert content_trace.detector_id==content.detector_id
        assert content_trace.evidence_locators[0]["resolvable"] is True
    finally:
        await client.close()
        await connection.close()


@pytest.mark.asyncio
async def test_media_reads_are_isolated_by_artifact_snapshot_profile_ownership(migrated_database,tmp_path):
    url,request_id,_=migrated_database
    client=PostgresClient(url)
    connection=await asyncpg.connect(url)
    try:
        ledger=EvidenceLedger(client)
        occurred=datetime(2025,7,1,12,tzinfo=timezone.utc)

        async def subject_image(label: str,latitude: float):
            profile_id=await connection.fetchval(
                "INSERT INTO profiles(identity_name) VALUES($1) RETURNING id",label,
            )
            run_id=await ledger.create_analysis_run(
                "task4-media-isolation","task4-v1",request_id=request_id,profile_id=profile_id,
            )
            snapshot_id=await ledger.create_export_snapshot(
                run_id,"manual_import",request_id=request_id,profile_id=profile_id,
            )
            path=tmp_path/f"{label}.png"
            Image.new("RGB",(100,80),"white").save(path)
            content=path.read_bytes()
            _,artifact_id=await ledger.record_source_artifact(
                snapshot_id,content,storage_uri=path.resolve().as_uri(),original_path=path.name,
                file_name=path.name,detected_mime="image/png",extension=".png",file_type_status="matched",
            )
            locator_id=await ledger.create_locator(EvidenceLocatorCreate(
                artifact_id=artifact_id,locator_type=LocatorType.IMAGE_REGION,
                locator={"x":0,"y":0,"width":100,"height":80},
            ),content)
            metadata={
                "capture_timestamp":"2025:07:01 12:00:00","timezone":"+00:00",
                "device":{"make":"Fixture","model":"Camera"},
                "gps":{"latitude":latitude,"longitude":-0.1},
            }
            await connection.execute(
                """INSERT INTO extraction_units
                (analysis_run_id,artifact_id,unit_key,unit_type,ordinal,structured_payload,metadata,
                 evidence_locator_id,adapter_id,adapter_version)
                VALUES($1,$2,'image:0','image_metadata',0,$3::jsonb,'{}',$4,'media','1.0.0')""",
                run_id,artifact_id,json.dumps(metadata),locator_id,
            )
            await connection.execute(
                """INSERT INTO specialist_task_requests
                (analysis_run_id,artifact_id,task_key,input_manifest,status,output_manifest,completed_at)
                VALUES($1,$2,'image.ocr',$3::jsonb,'completed',$4::jsonb,NOW())""",
                run_id,artifact_id,json.dumps({"evidence_locator_id":str(locator_id)}),
                json.dumps({"text":f"{label} dashboard","topics":[label]}),
            )
            return profile_id,artifact_id,locator_id,run_id

        first_profile,first_artifact,first_locator,first_run=await subject_image("alpha-subject",51.5)
        second_profile,second_artifact,second_locator,second_run=await subject_image("beta-subject",48.8)
        period=InsightPeriod(
            mode=TemporalMode.PERIOD,granularity=PeriodGranularity.MONTH,
            from_at=occurred-timedelta(days=1),to_at=occurred+timedelta(days=2),
        )
        service=InsightService(client)
        first=await service.get_place_insights(subject_id=str(first_profile),period=period)
        second=await service.get_place_insights(subject_id=str(second_profile),period=period)
        assert {item.artifact_id for item in first.candidates}=={first_artifact}
        assert {item.artifact_id for item in second.candidates}=={second_artifact}
        assert {item.artifact_id for item in first.media_content_candidates}=={first_artifact}
        assert {item.artifact_id for item in second.media_content_candidates}=={second_artifact}
        with pytest.raises(LookupError,match="artifact evidence locator not found"):
            await service.confirm_media_location(
                artifact_id=second_artifact,evidence_locator_id=second_locator,
                reviewed_by="alpha",place_label="must not cross profiles",
                analysis_run_id=second_run,profile_id=first_profile,
            )
        with pytest.raises(LookupError,match="insight catalogue entry not found"):
            await service.trace_insight(
                second.candidates[0].insight_id,profile_id=first_profile,
            )
    finally:
        await client.close()
        await connection.close()


@pytest.mark.asyncio
async def test_temporal_aggregate_change_invalidates_snapshot_cache(migrated_database):
    url,request_id,_=migrated_database
    client=PostgresClient(url)
    connection=await asyncpg.connect(url)
    try:
        profile_id=await connection.fetchval(
            "INSERT INTO profiles(identity_name) VALUES('Aggregate fixture') RETURNING id",
        )
        run_id=await connection.fetchval(
            """INSERT INTO analysis_runs(run_type,profile_id,request_id,status,pipeline_version)
               VALUES('task4-aggregate-cache',$1,$2,'running','task4-v1') RETURNING id""",
            profile_id,request_id,
        )
        start=datetime(2025,8,1,tzinfo=timezone.utc)
        period=InsightPeriod(
            mode=TemporalMode.PERIOD,granularity=PeriodGranularity.MONTH,
            from_at=start,to_at=start+timedelta(days=31),
        )
        service=InsightService(client)
        first=await service.get_snapshot(subject_id=str(profile_id),period=period)
        await connection.execute(
            """INSERT INTO temporal_aggregates
            (analysis_run_id,subject_id,history_type,aggregate_type,aggregate_key,window_start,window_end,
             values,source_event_count,detector_id,detector_version)
            VALUES($1,$2,'personal_behavioural','engagement_profile','all-actions',$3,$4,
                   '{"investigation":4}'::jsonb,4,'fixture','1')""",
            run_id,str(profile_id),period.from_at,period.to_at,
        )
        second=await service.get_snapshot(subject_id=str(profile_id),period=period)
        assert first.canonical_source_counts["temporal_aggregates"]==0
        assert second.canonical_source_counts["temporal_aggregates"]==1
        assert second.overview.engagement.calculated_features["canonical_temporal_aggregate_count"]==1
        assert await connection.fetchval(
            "SELECT count(*) FROM insight_materialisations WHERE subject_id=$1",str(profile_id),
        )==2
    finally:
        await client.close()
        await connection.close()
