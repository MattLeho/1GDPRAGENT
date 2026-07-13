"""Evidence tracing for Personal Insights.

Model explanations are returned as annotations only. Evidence comes from the
indexed ActivityEvents, accepted Assertions, source artefacts and mechanically
resolvable EvidenceLocators.
"""
from __future__ import annotations

from pathlib import Path
import json
from urllib.parse import unquote, urlparse
from uuid import UUID

from evidence.locators import resolve_locator
from features.pipeline import load_activity_event_partitions
from insights.models import InsightTrace


def _value(row, key, default=None):
    value = row.get(key, default) if isinstance(row, dict) else row[key]
    if isinstance(value, str) and value[:1] in {"{", "["}:
        try: return json.loads(value)
        except json.JSONDecodeError: return value
    return value


def _local_path(storage_uri: str) -> Path:
    parsed = urlparse(storage_uri)
    if parsed.scheme not in {"", "file"}:
        raise ValueError("only local evidence storage can be mechanically resolved")
    if parsed.scheme == "file":
        raw = unquote(parsed.path)
        if parsed.netloc:
            raw = f"//{parsed.netloc}{raw}"
        if len(raw) >= 3 and raw[0] == "/" and raw[2] == ":":
            raw = raw[1:]
        return Path(raw)
    return Path(storage_uri)


def _find_derived(payload, insight_id: UUID) -> dict:
    """Find the exact derived DTO inside a cached snapshot payload."""
    if isinstance(payload, dict):
        if str(payload.get("insight_id", "")) == str(insight_id):
            return payload
        for value in payload.values():
            found = _find_derived(value, insight_id)
            if found:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _find_derived(value, insight_id)
            if found:
                return found
    return {}


class InsightEvidenceTracer:
    def __init__(self, connection) -> None:
        self.connection = connection

    async def trace(self, insight_id: UUID) -> InsightTrace:
        materialisation = await self.connection.fetchrow(
            """SELECT im.* FROM insight_materialisations im
            JOIN insight_catalogue ic ON ic.materialisation_id=im.id
            WHERE ic.insight_id=$1 ORDER BY im.created_at DESC,im.id DESC LIMIT 1""",
            insight_id,
        )
        if materialisation is None:
            raise LookupError("insight catalogue entry not found")
        indexed = await self.connection.fetch(
            """SELECT * FROM insight_evidence_index
               WHERE insight_id=$1 AND materialisation_id=$2
               ORDER BY evidence_kind,evidence_ref_id""",
            insight_id,materialisation["id"],
        )
        payload = _value(materialisation, "payload", {})
        selected = _find_derived(payload, insight_id)
        event_ids = {row["evidence_ref_id"] for row in indexed if row["evidence_kind"] == "activity_event"}
        assertion_ids = {row["evidence_ref_id"] for row in indexed if row["evidence_kind"] == "assertion"}
        temporal_state_ids = {row["evidence_ref_id"] for row in indexed if row["evidence_kind"] == "temporal_state"}
        temporal_aggregate_ids = {row["evidence_ref_id"] for row in indexed if row["evidence_kind"] == "temporal_aggregate"}
        external_context_ids = {row["evidence_ref_id"] for row in indexed if row["evidence_kind"] == "external_context_event"}
        locator_ids = {row["evidence_ref_id"] for row in indexed if row["evidence_kind"] == "evidence_locator"}
        artifact_ids = {row["evidence_ref_id"] for row in indexed if row["evidence_kind"] == "source_artifact"}
        artifact_ids.update(row["artifact_id"] for row in indexed if row["artifact_id"] is not None)
        locator_ids.update(row["locator_id"] for row in indexed if row["locator_id"] is not None)

        activity_events = []
        if event_ids:
            partition_rows = await self.connection.fetch(
                "SELECT storage_uri FROM event_partitions WHERE schema_version='activity-event-v1' ORDER BY created_at"
            )
            paths = [row["storage_uri"] for row in partition_rows if Path(row["storage_uri"]).exists()]
            if paths:
                for event in load_activity_event_partitions(paths):
                    if event.event_id in event_ids:
                        activity_events.append(event.model_dump(mode="json"))
                        artifact_ids.add(event.artifact_id)
                        locator_ids.add(event.source_locator_id)

        assertions = []
        if assertion_ids:
            rows = await self.connection.fetch(
                """SELECT * FROM assertions WHERE id=ANY($1::uuid[]) AND status IN ('accepted','superseded')
                ORDER BY system_asserted_at,id""", list(assertion_ids),
            )
            assertions = [dict(row) for row in rows]
            linked = await self.connection.fetch(
                "SELECT evidence_locator_id FROM assertion_evidence WHERE assertion_id=ANY($1::uuid[])",
                list(assertion_ids),
            )
            locator_ids.update(row["evidence_locator_id"] for row in linked)

        temporal_states = []
        if temporal_state_ids:
            rows = await self.connection.fetch(
                "SELECT * FROM temporal_states WHERE id=ANY($1::uuid[]) ORDER BY system_asserted_at,id",
                list(temporal_state_ids),
            )
            temporal_states = [dict(row) for row in rows]

        temporal_aggregates = []
        if temporal_aggregate_ids:
            rows = await self.connection.fetch(
                "SELECT * FROM temporal_aggregates WHERE id=ANY($1::uuid[]) ORDER BY window_start,id",
                list(temporal_aggregate_ids),
            )
            temporal_aggregates = [dict(row) for row in rows]

        external_context_events = []
        if external_context_ids:
            rows = await self.connection.fetch(
                "SELECT * FROM external_context_events WHERE id=ANY($1::uuid[]) ORDER BY occurred_at,id",
                list(external_context_ids),
            )
            external_context_events = [dict(row) for row in rows]

        locators = []
        if locator_ids:
            rows = await self.connection.fetch(
                """SELECT el.*,cb.storage_uri,sa.original_path FROM evidence_locators el
                JOIN source_artifacts sa ON sa.id=el.artifact_id
                JOIN content_blobs cb ON cb.id=sa.content_blob_id
                WHERE el.id=ANY($1::uuid[]) ORDER BY el.id""",
                list(locator_ids),
            )
            for row in rows:
                item = dict(row)
                item["locator"] = _value(item, "locator", {})
                try:
                    content = _local_path(item["storage_uri"]).read_bytes()
                    resolved = resolve_locator(content, item["locator_type"], item["locator"])
                    item["resolvable"] = True
                    item["resolved_byte_count"] = len(resolved)
                except Exception as exc:
                    item["resolvable"] = False
                    item["resolution_error"] = str(exc)
                locators.append(item)
                artifact_ids.add(item["artifact_id"])

        artifacts = []
        if artifact_ids:
            rows = await self.connection.fetch(
                """SELECT id,export_snapshot_id,parent_artifact_id,content_blob_id,original_path,
                archive_member_path,file_name,declared_mime,detected_mime,extension,file_type_status,
                canonical_hash,source_organisation,source_product,source_service,created_at
                FROM source_artifacts WHERE id=ANY($1::uuid[]) ORDER BY created_at,id""",
                list(artifact_ids),
            )
            artifacts = [dict(row) for row in rows]

        detector_id = str(selected.get("detector_id") or materialisation["derivation_method"])
        detector_version = str(selected.get("detector_version") or materialisation["derivation_version"])
        selected_window = None
        if selected.get("window_start") and selected.get("window_end"):
            selected_window = (selected["window_start"], selected["window_end"])
        elif selected.get("start_at") and selected.get("end_at"):
            selected_window = (selected["start_at"], selected["end_at"])
        return InsightTrace(
            insight_id=insight_id, detector_id=detector_id, detector_version=detector_version,
            analysis_run_id=selected.get("analysis_run_id") or materialisation["analysis_run_id"],
            time_window=selected_window or ((materialisation["from_at"], materialisation["to_at"]) if materialisation["from_at"] and materialisation["to_at"] else None),
            calculated_features=selected.get("calculated_features", {}),
            source_counts={"activity_events":len(activity_events),"assertions":len(assertions),
                           "temporal_states":len(temporal_states),"temporal_aggregates":len(temporal_aggregates),
                           "external_context_events":len(external_context_events),
                           "source_artifacts":len(artifacts),"evidence_locators":len(locators)},
            activity_events=tuple(activity_events), assertions=tuple(assertions),
            temporal_states=tuple(temporal_states),temporal_aggregates=tuple(temporal_aggregates),
            external_context_events=tuple(external_context_events),
            source_artifacts=tuple(artifacts), evidence_locators=tuple(locators),
            model_explanation=selected.get("model_explanation"),
        )
