# Task 3 and Task 3A Acceptance Audit

> **PROVISIONAL — superseded by R0 evidence pending revalidation (2026-07-17).** Historical evidence is retained below but does not prove current integrated or authenticated runtime behaviour.

Date: 2026-07-11  
Scope: Task 3 and mandatory Task 3A only. Task 4 was not started.

## Verdict

Task 3 and the mandatory Task 3A P0 scope are implemented and verified. P1/P2 items explicitly catalogued as metadata-only or unsupported remain visible and are not represented as executable support.

A final delegated Stage 5 follow-up closed three previously under-specified edges: recurrence is now explicitly prefix-only with active/dormant/return metrics; PELT defaults to robust L1 for deterministic uni/multivariate change points; and decay/project episodes preserve evidence while rejecting isolated one-event bursts. The independent AS-OF/export audit required no changes.

## Final pipeline

1. A bounded local import path is checked against configured roots.
2. Streaming inventory, signature/MIME/extension evidence, content hashing, content-addressed storage, and structure fingerprinting run without a model.
3. The file registry selects one deterministic family adapter or records ambiguous, corrupt, encrypted, password-required, metadata-only, or unsupported status.
4. Adapters emit generic extraction units, embedded-child descriptors, metadata, and typed evidence locators. They never write graph truth.
5. Known approved schemas execute immutable declarative parsers. Unknown fingerprints create one bounded proposed interpretation request per fingerprint/version.
6. Canonical logical ActivityEvents are deduplicated into partitioned Parquet; observation occurrences and partition metadata are append-only catalogues in PostgreSQL.
7. Deterministic feature and temporal stages produce evidence-grounded candidates and the three separate histories. Only bounded ambiguous residue crosses the canonical Task 2 execution boundary.
8. Accepted, provenance-valid high-value assertions alone may enter Neo4j through `GraphProjectionService`.

## Storage and recovery

- Raw immutable blobs: configurable `GDPR_DATA_ROOT`, `/data` in Docker, content-addressed by SHA-256.
- Container durability: named `intelligence_data` volume shared by intelligence and Celery.
- Approved import roots: `/source-uploads` in Docker; path traversal and archive re-entry remain bounded.
- Event lake: atomic Parquet partitions with schema version, row count, time bounds, and file hash.
- PostgreSQL: runs, snapshots, source occurrences, locators, schema/parser registry, checkpoints, event observations, temporal states, specialist requests, and audit records.
- Restart: checkpoint identity includes stage/item/content/parser version. Completed work is skipped; failed work resumes without replaying the import.

## File support matrix

| Priority/status | Formats | Execution boundary |
|---|---|---|
| P0 deterministic | JSON, NDJSON, CSV, TSV, XML, HTML, YAML, text/log, Markdown; DOCX, XLSX, PPTX, ODT, ODS, ODP, RTF; EML, MBOX, ICS, VCF; SRT, WebVTT; GeoJSON, KML, KMZ, GPX, SQLite; ZIP, TAR, TAR.GZ/TGZ, GZIP, BZIP2, XZ | Local deterministic adapters with typed structural locators |
| P0 optional specialist | PDF; JPEG, PNG, WebP, TIFF, HEIF, BMP, GIF; WAV, MP3, M4A/AAC, FLAC, OGG/Opus; MP4, MOV, MKV, WebM | Deterministic metadata/structure first; OCR, speech, caption, landmark, and topic work only through Task 2 routes |
| P1 metadata-only | 7z, RAR, DOC, XLS, PPT, XLSB, MSG, PST, GeoPackage, Shapefile, GML, GeoTIFF, plist, HAR, LevelDB, Avro, Parquet | Catalogued/probed; no executable extraction claim until a reviewed read-only adapter and fixture exist |
| P2 unsupported | OST, descriptor-less protobuf, disk images, unknown binary, proprietary encrypted stores | Catalogued with explicit reason; never convenience-uploaded to a model |

All executable registry records carry adapter/version, extensions, MIME/signature evidence, capability flags, locator vocabulary, streaming flag, dependencies/security limitations, known limitations, and registered valid/malformed/locator fixture IDs. Family tests instantiate those fixtures and validate resolvability. The cross-family corpus covers ZIP→JSON/image/email lineage, MBOX→PDF, scanned/hybrid PDF OCR routing, XLSX formula/value and stable cells, multi-stream video and subtitles when FFmpeg is installed, EXIF/no-EXIF images, GPX, an exact million-row SQLite database, unknown/corrupt files, encrypted archives, and duplicate child bytes under distinct parents.

## Locator and specialist coverage

- Structured: JSON pointer/record, CSV row/cell, text line/byte span, XML element, HTML DOM span.
- Documents: PDF page/block/region, Office paragraph/table cell, spreadsheet cell, slide shape/notes.
- Communications: email header/MIME part/attachment, calendar component, vCard property.
- Media: image region, media time range, video frame, subtitle cue.
- Geo/database/archive: geospatial feature, table row/cell, archive member with full nested lineage.
- Routes: `document.ocr`, `image.ocr`, `image.caption`, `image.landmark_candidate`, `speech.transcription`, `speech.diarisation`, `speech.translation`, schema interpretation, semantic adjudication, and topic labelling. Result provenance records engine, model, derivation, confidence, and exact page/region or time-range locator.

## Acceptance assertions

| Assertion | Evidence/result |
|---|---|
| Extension alone never decides type | Probe/classification mismatch tests; adapters reject uncorroborated extensions |
| Unknown schema sampled once | Registry/database tests prove idempotence by fingerprint and interpretation version |
| Approved schema bypasses model work | Bulk pipeline replay/approval integration test |
| Duplicate bytes preserve occurrences | content blob deduplication plus distinct SourceArtifact/observation/parent tests |
| Raw events go to Parquet, not Neo4j | event writer tests; graph allowlist explicitly excludes `ActivityEvent` |
| Strict local never invokes external execution | Task 2 route/privacy tests and measured provider/network call count of zero |
| No silent Google fallback | unsupported provider fails closed; controlled cloud requires an explicit approved engine |
| Controller profile does not alter Subject behaviour | three-history temporal tests plus graph semantic-separation guard |
| Occurrence and system discovery differ | real PostgreSQL bitemporal/as-of test |
| Killed run resumes | checkpoint failure/retry and synthetic restart tests |
| Encrypted/corrupt/unsupported remain visible | archive/document/cross-family tests with explicit quarantine status |
| OCR/transcription provenance is resolvable | specialist-result persistence tests for image/page regions and media time ranges |
| Image metadata does not prove physical presence | EXIF and no-EXIF tests retain metadata-only evidence; no HOME/presence promotion |
| Archive content cannot escape limits | traversal, depth, symlink, expansion, member-count, and nested-lineage tests |

## Model policy and measured reduction

Deterministic stages process raw files and events. Models see only bounded samples or selected specialist media, through the existing Task 2 task/engine/provider/privacy/audit registry. Proposal is not approval. Measured benchmark: 3 files, 254,674 bytes, 3,000 records, 2,000 events, one semantic call, zero provider/network calls, a 0.000333 call/record ratio, and a 99.9667% reduction from per-record model invocation. Peak traced memory was 75,127,597 bytes.

## Verification

- Python compile: passed.
- Full repository tests: 246 passed, 2 skipped (optional FFmpeg/platform-symlink availability), 4 benign fixture warnings.
- Task 3-only tests: 208 passed, 2 optional skips.
- Frontend lint: passed.
- Frontend TypeScript check and optimized production build: passed (57 static pages generated).
- Docker Compose validation: passed. Migrations 011–015 applied. Intelligence and Celery healthy after recreation with durable storage.

## Dependencies and limitations

New Python dependencies are recorded in `intelligence/requirements.txt`; specialist ASR dependencies remain isolated in `requirements-asr.txt`. FFmpeg/ffprobe and HEIF codecs are optional and surfaced as limitations when absent. P1 metadata-only and P2 unsupported formats above are intentionally incomplete executable support. Specialist quality depends on the user-selected Task 2 engine. No destructive migration was introduced; legacy AI summaries are retained and marked `unverified_legacy`, so they cannot silently become accepted evidence.

## Incomplete requirements

There are no incomplete mandatory Task 3/P0 Task 3A requirements found by the final audit. Optional P1/P2 execution remains incomplete by design and is explicitly catalogued above. Task 4 remains untouched.
