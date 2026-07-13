# Task 2 Implementation Ledger

Updated: 2026-07-10

## Persistence

- Migration 010 adds `task_routes`, `processing_settings`, `workflow_preferences`, `execution_records`, `connector_credentials`, `transcript_artifacts`, `outbound_messages`, and `inbox_checkpoints`.
- `ExecutionRecord.analysis_run_id` and transcript provenance extend Task 1 `AnalysisRun`/`SourceArtifact`; no parallel provenance store was introduced.
- Legacy global workflow mode seeds per-workflow preferences. Legacy email base64 is quarantined for re-entry.

## Runtime

- Canonical task/engine registry and privacy-aware router.
- Explicit deterministic, local intelligence, Ollama, and remote provider adapters.
- Provider/model, source artefacts, sizes, result, and structured errors audited per attempt.
- Local Parakeet/Whisper ASR path with FFmpeg normalization and timestamp persistence; text-only semantic follow-up.
- Canonical 18-workflow registry, mixed per-workflow execution, and one N8N webhook registry.
- Built-in SMTP send, IMAP connection test/monitor, checkpointing, response matching/classification, and message transport audit.
- Policy drafting/analysis, graph explanation, and vendor OCR no longer silently default to Google.

## User interface

- Seven-section settings navigation.
- Task categories, engine location/model/fallback/health, and advanced route limits.
- Per-workflow execution selection with contextual N8N disclosure.
- Connector status/permissions/sync/rotation/disconnect controls.
- Processing privacy policy and external model audit.

## Verification ledger

- Migration 010: live and disposable databases passed.
- Full pytest suite: 38 passed.
- TypeScript: passed.
- Focused Task 2 lint: passed with zero errors/warnings.
- Production build: passed; 54 pages and all Task 2 routes emitted.
- Runtime policy probes: strict-local 403, unsupported pair 400, deterministic local success.
- Compose: Next.js, intelligence, Celery, PostgreSQL, Neo4j, Redis, Qdrant, and optional N8N healthy.
- Local deterministic media tools: FFmpeg installed; Tesseract and ExifTool health checks passed.

## Deferred by specification

- Personal Insights and temporal product UI (Task 4).
- Connector-wide acquisition and retention/deletion policies (Task 5).
- Optional Parakeet/Whisper model weights remain operator-installed; absence is visible and never triggers hidden cloud execution.
