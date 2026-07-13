"""PostgreSQL catalogue integration for deterministic ingestion metadata."""

from __future__ import annotations

import json
from typing import Any

from .models import FormatSupportRecord
from .registry import FORMAT_SUPPORT_REGISTRY


async def sync_format_support_registry(postgres:Any,records:tuple[FormatSupportRecord,...]=FORMAT_SUPPORT_REGISTRY)->int:
    """Idempotently publish the code-owned support registry to PostgreSQL."""
    for record in records:
        await postgres.execute(
            """INSERT INTO format_support_registry(format_key,family,probe_priority,adapter_id,adapter_version,support_status,
               supported_extensions,supported_mime_types,magic_signatures,task_routes,capability_flags,locator_types,
               supports_streaming,maximum_tested_fixture_size,system_dependencies,security_notes,known_unsupported_features,fixture_ids,updated_at)
               VALUES($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,$9::jsonb,$10::jsonb,$11::jsonb,$12::jsonb,$13,$14,$15::jsonb,$16::jsonb,$17::jsonb,$18::jsonb,NOW())
               ON CONFLICT(format_key) DO UPDATE SET family=EXCLUDED.family,probe_priority=EXCLUDED.probe_priority,
               adapter_id=EXCLUDED.adapter_id,adapter_version=EXCLUDED.adapter_version,support_status=EXCLUDED.support_status,
               supported_extensions=EXCLUDED.supported_extensions,supported_mime_types=EXCLUDED.supported_mime_types,
               magic_signatures=EXCLUDED.magic_signatures,task_routes=EXCLUDED.task_routes,capability_flags=EXCLUDED.capability_flags,
               locator_types=EXCLUDED.locator_types,supports_streaming=EXCLUDED.supports_streaming,
               maximum_tested_fixture_size=EXCLUDED.maximum_tested_fixture_size,system_dependencies=EXCLUDED.system_dependencies,
               security_notes=EXCLUDED.security_notes,known_unsupported_features=EXCLUDED.known_unsupported_features,
               fixture_ids=EXCLUDED.fixture_ids,updated_at=NOW()""",
            record.format_key,record.family,record.probe_priority,record.adapter_id,record.adapter_version,record.status.value,
            json.dumps(record.supported_extensions),json.dumps(record.supported_mime_types),json.dumps(record.magic_signatures),
            json.dumps(record.task_routes),json.dumps(record.capability_flags),json.dumps(record.locator_types),record.streaming,
            record.maximum_tested_fixture_size,json.dumps(record.system_dependencies),json.dumps(record.security_notes),
            json.dumps(record.known_unsupported_features),json.dumps(record.fixture_ids),
        )
    return len(records)


async def record_ingestion_status(postgres:Any,*,artifact_id,analysis_run_id,status:str,support_status:str|None=None,
                                  detected_format:str|None=None,adapter_id:str|None=None,adapter_version:str|None=None,
                                  quarantine_reason:str|None=None,next_action:str|None=None,warnings:tuple[str,...]=())->None:
    await postgres.execute(
        """INSERT INTO file_ingestion_records(artifact_id,analysis_run_id,status,support_status,detected_format,adapter_id,adapter_version,quarantine_reason,next_action,warnings,updated_at)
           VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,NOW()) ON CONFLICT(artifact_id) DO UPDATE SET
           status=EXCLUDED.status,support_status=EXCLUDED.support_status,detected_format=EXCLUDED.detected_format,
           adapter_id=EXCLUDED.adapter_id,adapter_version=EXCLUDED.adapter_version,quarantine_reason=EXCLUDED.quarantine_reason,
           next_action=EXCLUDED.next_action,warnings=EXCLUDED.warnings,updated_at=NOW()""",
        artifact_id,analysis_run_id,status,support_status,detected_format,adapter_id,adapter_version,
        quarantine_reason,next_action,json.dumps(warnings),
    )

