# Task 3A — File type support and extraction workflow catalogue

This is a required companion to Task 3 in `MattLeho/1GDPRAGENT`.

It exists because **file format extraction and source/schema interpretation are different layers**.

Do not create one giant “AI file extraction” workflow.

Target:

```text
FILE BYTES
   ↓
FILE-TYPE TRUTH
   ↓
FILE-FAMILY ADAPTER
   ↓
GENERIC EXTRACTION UNITS + EXACT LOCATORS
   ↓
STRUCTURE FINGERPRINT / SOURCE HINTS
   ↓
APPROVED SOURCE-SCHEMA PARSER
   ↓
ACTIVITY EVENTS / ASSERTION CANDIDATES
```

A PDF adapter extracts pages, text blocks, tables, images and locators. It does not decide that a sentence proves a controller inferred a sensitive interest.

A JSON adapter exposes structure and records. It does not decide that the file is search history until a known schema/parser or reviewed parser spec establishes that meaning.

## Delegation protocol for this task

The primary agent is the **orchestrator and integrator**. Keep GPT-5.6 Sol on work that requires cross-cutting architectural judgement, security/privacy decisions, migration ownership, shared contracts, integration, or final acceptance.

Use **Terra-Medium** for bounded delegated subtasks where the input, output contract, file ownership, and tests can be stated precisely. If Terra-Medium is unavailable in the current environment, use the cheapest competent sub-agent available for the same bounded work. Do not silently push every leaf task back to the orchestrator unless delegation has failed.

### Work that stays with the orchestrator

The orchestrator owns:

- reading the full task and all predecessor plans;
- auditing the actual merged repository before edits;
- freezing shared interfaces and invariants;
- PostgreSQL migration ownership and migration ordering;
- canonical Pydantic/TypeScript contracts that multiple modules consume;
- provenance and epistemic rules;
- processing-mode and external-data-transfer rules;
- concurrency/resumability architecture;
- any destructive operation or deletion semantics;
- merge/integration decisions;
- end-to-end tests;
- final line-by-line acceptance audit.

### Work suitable for Terra-Medium sub-agents

Prefer delegation for:

- repository inventories and implementation maps;
- isolated adapters behind a frozen interface;
- deterministic extractors or classifiers with explicit fixtures;
- source/file-family parser implementations;
- test fixture generation;
- unit-test expansion;
- leaf React components consuming already-defined API contracts;
- documentation updates after implementation is stable;
- performance micro-benchmarks;
- compatibility shims and narrow migrations prepared for orchestrator review.

### Delegation rules

1. **Freeze the contract before parallel work.** Do not delegate five agents to invent five versions of the same interface.
2. **One owner per shared file.** The orchestrator should pre-assign file/directory ownership. Avoid parallel edits to migrations, canonical models, registries, or central routers.
3. **Use isolated worktrees/branches where supported.** Each sub-agent should make a coherent, reviewable change set.
4. **No semantic scope expansion.** A sub-agent may not redesign the ontology, weaken provenance, add an external fallback, or introduce a new source of truth because it makes its leaf task easier.
5. **No unreviewed merge.** The orchestrator reviews diffs, runs focused tests, then integrates.
6. **Failed sub-agent work is not a blocker to reasoning.** Re-scope, re-delegate, or implement the critical part centrally.
7. **Do not count generated files as implementation.** A delegated task is complete only when the contract is satisfied and tests pass.

### Required sub-agent handoff

Every delegated task must return:

```text
SUBTASK
Scope completed:

FILES CHANGED
- ...

CONTRACT USED
- ...

TESTS RUN
- command
- result

ASSUMPTIONS
- ...

KNOWN LIMITATIONS
- ...

INTEGRATION NOTES
- ...

BLOCKERS
- none / ...
```

The orchestrator maintains one implementation ledger for the whole task:

```text
requirement
owner
dependency
implementation location
status
tests
integration status
migration/backfill note
blocker
```

### Wave gates

Do not begin a later wave merely because one sub-agent finished early.

At the end of every wave the orchestrator must:

1. inspect every delegated diff;
2. reconcile duplicate concepts;
3. run the wave's focused tests;
4. run type checking/compile checks for touched services;
5. update the implementation ledger;
6. explicitly mark the shared contracts that are now frozen for the next wave.

# 1. Freeze FileFamilyAdapter before parallel work

**Owner: Task 3 orchestrator**

Define a canonical adapter interface.

Suggested contract:

```text
FileFamilyAdapter
- adapter_id
- adapter_version
- family
- supported_mime_types
- supported_extensions
- probe(file) -> ProbeResult
- extract(file, context) -> ExtractionResult
- supports_streaming
- supports_nested_members
- locator_types
- capability_flags
```

`ExtractionResult` must contain:

```text
artifact_id
adapter_id
adapter_version
family
detected_format
metadata
units[]
embedded_members[]
warnings[]
quarantine_status
```

Each `ExtractionUnit` contains:

```text
unit_id
unit_type
ordinal
text/value/structured payload
metadata
evidence_locator
parent_unit_id
```

Capability flags may include:

```text
text
tables
structured_records
attachments
embedded_media
metadata
timestamps
coordinates
frames
audio_stream
speaker_timing
slides
sheets
pages
database_tables
archive_members
```

Adapters never write graph truth.

# 2. File support status model

Maintain a machine-readable support registry.

Statuses:

```text
SUPPORTED_DETERMINISTIC
SUPPORTED_WITH_OPTIONAL_SPECIALIST
METADATA_ONLY
QUARANTINED
UNSUPPORTED
```

For every format record:

- format/family;
- extensions;
- MIME/signatures;
- adapter;
- extraction capabilities;
- locator coverage;
- streaming support;
- maximum tested fixture size;
- optional system dependency;
- security limitations;
- known unsupported features.

The Settings/ingestion UI may later display this registry.

# 3. Priority matrix

Implement practical support in priority order.

## P0 — required for Task 3 completion

### Archives/containers

- ZIP;
- TAR;
- TAR.GZ/TGZ;
- GZIP single-stream;
- BZIP2;
- XZ.

7z may be P1 if a safe tested dependency is available.

Encrypted archives must be detected and surfaced as `QUARANTINED` or explicit password-required state. Do not brute-force passwords.

RAR is P1/optional and must not block Task 3.

### Structured and semi-structured data

- JSON;
- JSONL/NDJSON;
- CSV;
- TSV;
- generic delimited text;
- XML;
- HTML;
- YAML where safely parsed;
- plain text;
- Markdown;
- log/text line streams.

### Documents

- PDF;
- DOCX;
- XLSX;
- PPTX;
- ODT;
- ODS;
- ODP;
- RTF.

Legacy binary DOC/XLS/PPT may be P1 through a constrained converter or specialist library.

### Email, calendar and contacts

- EML;
- MBOX;
- ICS/iCalendar;
- VCF/vCard.

### Images

Metadata-first support for:

- JPEG/JPG;
- PNG;
- WebP;
- TIFF;
- HEIC/HEIF where platform/library support exists;
- BMP;
- GIF.

### Audio

- WAV;
- MP3;
- M4A/AAC;
- FLAC;
- OGG/Opus.

### Video

- MP4;
- MOV;
- MKV;
- WebM.

### Subtitles/captions

- SRT;
- WebVTT.

### Geospatial/location

- GeoJSON;
- KML/KMZ;
- GPX.

### Local databases

- SQLite.

## P1 — implement where dependencies are safe and tests are practical

- 7z;
- RAR;
- DOC/XLS/PPT legacy binaries;
- XLSB;
- EML nested-message edge cases;
- MSG;
- PST;
- GeoPackage;
- Shapefile;
- GML;
- GeoTIFF metadata;
- Apple plist and binary plist;
- browser Netscape bookmark HTML;
- HAR;
- LevelDB/IndexedDB snapshot inspection where a robust read-only adapter is available;
- Avro/Parquet as imported source formats.

## P2 — catalogue, probe and surface explicitly

- OST;
- proprietary encrypted database formats;
- arbitrary protobuf without a descriptor/schema;
- unknown binary blobs;
- disk images;
- application-specific stores requiring unsafe reverse engineering.

P2 does not mean “pretend the file does not exist”.

The inventory must show:

```text
detected
unsupported or schema-required
size
hash
source path
reason
next action
```

# 4. Delegated file-family work packages

The Task 3 orchestrator freezes the adapter contract, then delegates these packages.

## Sub-agent F1 — Structured data and text

**Recommended: Terra-Medium**

Own:

- JSON;
- JSONL/NDJSON;
- CSV/TSV/delimited;
- XML;
- HTML;
- YAML;
- TXT;
- Markdown;
- logs.

Implement:

- streaming where appropriate;
- encoding/BOM detection;
- delimiter detection with bounded sampling;
- record boundaries;
- exact JSON Pointer/record locator support;
- CSV row/cell locators;
- XML element/attribute locators;
- HTML DOM/CSS-path-like stable locators plus raw span where practical;
- line/byte locators for text/logs;
- generic metadata only.

Do not semantically classify a source from field names beyond candidate hints.

Tests include huge JSON array simulation, NDJSON malformed line, mixed encoding, quoted CSV newlines and malformed HTML.

## Sub-agent F2 — PDF, Office and OpenDocument

**Recommended: Terra-Medium**

Own:

- PDF;
- DOCX/XLSX/PPTX;
- ODT/ODS/ODP;
- RTF;
- approved legacy-conversion path if selected.

### PDF workflow

Classify pages:

```text
native_text
scanned_image
hybrid
```

Extract:

- page count;
- page text with page/block locators;
- text coordinates where library permits;
- tables as table candidates;
- embedded images as child artefacts;
- document metadata.

Only scanned/hybrid residue goes to `document.ocr`.

OCR is a TaskRoute from Task 2, not hardcoded Gemini.

Never replace the raw PDF with OCR text.

### DOCX/ODT/RTF

Extract:

- paragraphs;
- headings;
- tables;
- hyperlinks;
- comments/notes where supported;
- document metadata;
- embedded media references.

Locators identify paragraph/table/cell/run or equivalent stable structural position.

### XLSX/ODS

Extract workbook metadata, sheet names, used ranges, cells, formula/value distinction, comments/notes and table regions.

Preserve:

```text
sheet
row
column
cell address
formula
displayed/cached value where present
```

Do not send a whole workbook to an LLM for “analysis”.

### PPTX/ODP

Extract:

- slide order;
- titles;
- text shapes;
- speaker notes;
- tables;
- charts as chart metadata/data where accessible;
- embedded media.

Locator must include slide and shape/note identity.

Tests include native/scanned/hybrid PDFs, merged spreadsheet cells, formulas, hidden sheets, speaker notes and embedded media.

## Sub-agent F3 — Email, calendar and contacts

**Recommended: Terra-Medium**

Own:

- EML;
- MBOX;
- ICS;
- VCF;
- P1 MSG/PST only if dependencies pass review.

### EML/MBOX

Extract source-level records:

- message ID;
- thread/reference headers;
- sender;
- recipients;
- dates;
- subject;
- relevant standard headers;
- multipart bodies;
- attachment metadata;
- attachments as child SourceArtifacts.

Preserve HTML and plain-text alternatives separately.

Do not infer open/click events from mere receipt.

Locators identify message, header, MIME part and attachment.

### ICS

Extract:

- event UID;
- DTSTART/DTEND with timezone semantics;
- recurrence rules;
- organisers/attendees;
- location;
- summary/description;
- alarms where present.

Do not expand infinite recurrence blindly. Use bounded recurrence policy and preserve RRULE source evidence.

### VCF

Extract:

- contact record;
- names;
- emails;
- phones;
- organisation;
- addresses;
- birthday/date fields;
- custom fields as unknown properties.

Do not assert relationship semantics.

Tests cover MIME nesting, duplicate Message-ID, malformed headers, timezone ICS and recurring events.

## Sub-agent F4 — Media and subtitles

**Recommended: Terra-Medium**

Own image/audio/video/subtitle family adapters.

This package performs deterministic metadata and stream extraction. Task 4 later adds Personal Insights media interpretation.

### Images

Metadata-first:

- format;
- dimensions;
- EXIF/raw metadata;
- capture timestamp;
- timezone metadata;
- GPS;
- camera/device;
- editing software;
- animation/frame count;
- perceptual hash where approved.

Classify origin only through a separate task/detector. The adapter does not decide physical presence.

`image.ocr`, `image.caption`, and `image.landmark_candidate` are TaskRoutes and run only under configured policy.

### Audio

Extract:

- codec/container;
- duration;
- channels;
- sample rate;
- embedded tags;
- creation metadata where available.

Normalise through ffmpeg only where required for the selected speech engine.

Route to:

```text
speech.transcription
speech.diarisation optional
speech.translation optional
```

Persist timestamped segments/words where the engine supports them.

Do not ask a general LLM to transcribe by default.

### Video

Extract:

- container/codec;
- duration;
- dimensions;
- frame rate;
- creation metadata;
- GPS/location metadata where present;
- audio streams;
- subtitle streams.

Audio transcription uses the speech route.

Visual frame analysis is selective. Implement deterministic sampling strategies, scene-change candidates and explicit frame/time-range locators. Do not analyse every frame by default.

### SRT/VTT

Extract timed cue records with exact cue/time locators.

Tests cover EXIF GPS, screenshots with no EXIF, edited images, VFR video metadata, multiple audio tracks and subtitles.

## Sub-agent F5 — Geospatial, databases and browser/storage artefacts

**Recommended: Terra-Medium**

Own P0 GeoJSON/KML/KMZ/GPX and SQLite.

P1 adapters are implemented only after P0 passes.

### Geospatial

Extract:

- CRS where applicable;
- feature count;
- geometry type;
- bounding box;
- feature properties;
- timestamp/elevation tracks where present.

Locators identify feature/member and coordinate/segment where practical.

Do not call a location HOME.

### SQLite

Read-only only.

Inventory:

- SQLite version/header;
- table/view names;
- columns/types;
- row counts using bounded strategy;
- indexes;
- foreign-key metadata.

Create structure fingerprints by table schema.

Representative samples feed schema interpretation.

Do not execute triggers, extensions or user-defined code.

Never modify the source database.

For large tables use streaming/batched reads.

### Browser/storage P1

Bookmarks HTML, HAR, plist and selected LevelDB/IndexedDB snapshots must each have an explicit read-only adapter and fixture before status becomes supported.

Do not ship brittle ad-hoc binary regex extraction as “support”.

## Sub-agent F6 — Archive/container format adapters

**Recommended: Terra-Medium**

Own format-specific container readers.

Security policy remains owned by Task 3.1B.

Implement safe streaming readers for P0 formats and optional P1 formats approved by orchestrator.

Every member becomes a source occurrence with an archive-member EvidenceLocator containing:

```text
outer artefact
nested member chain
member path
member ordinal
compressed/uncompressed metadata
```

Nested archives re-enter inventory subject to global limits.

Do not blindly materialise all members to disk.

# 5. Specialist task routes and fallback order

File-family adapters must call Task 2's Task Execution Router for specialist work.

Recommended task boundaries:

```text
document.ocr
image.ocr
image.origin_classification
image.caption
image.landmark_candidate
speech.transcription
speech.translation
speech.diarisation
schema.interpretation
semantic.adjudication
```

Default route principle:

```text
deterministic parser/probe
 ↓
local specialist engine
 ↓
explicitly configured external specialist fallback
 ↓
review/unsupported
```

A general LLM is not the fallback for every unreadable file.

Examples:

```text
scanned PDF
  → page rasterisation
  → document.ocr
  → grounded text blocks
```

```text
audio file
  → stream metadata
  → audio normalisation
  → speech.transcription
  → transcript units
```

```text
unknown JSON schema
  → structure fingerprint
  → representative records
  → schema.interpretation
  → proposed parser spec
```

```text
corrupt unknown binary
  → quarantine
  → no LLM upload
```

# 6. EvidenceLocator requirements by family

Required locator families:

```text
archive_member
json_pointer
json_record
csv_row
csv_cell
text_line
text_byte_span
xml_element
html_dom_span
pdf_page_block
pdf_region
office_paragraph
office_table_cell
spreadsheet_cell
slide_shape
slide_notes
email_header
email_mime_part
email_attachment
calendar_component
vcard_property
image_region
media_time_range
video_frame
subtitle_cue
geospatial_feature
database_table_row
database_cell
```

A specialist/model-derived claim without a resolvable locator remains candidate/review, not accepted evidence.

For OCR/model output, preserve:

- source page/frame/image;
- region/time range;
- engine/model;
- derivation version;
- confidence;
- exact extracted text where applicable.

# 7. Embedded and nested content

Use a child-artefact model.

Examples:

```text
ZIP
 └── XLSX
      └── embedded PNG
```

```text
MBOX
 └── EML
      └── PDF attachment
           └── embedded image
```

Each child retains lineage to the parent and its own content hash where bytes exist.

Embedded content may be deduplicated across parents without losing occurrences.

Prevent infinite loops with lineage/depth checks.

# 8. File workflow registry

Create a machine-readable registry rather than switch statements spread across upload routes.

Suggested record:

```text
format_key
family
probe_priority
adapter_id
adapter_version
status
supported_extensions
supported_mime_types
magic_signatures
task_routes
capability_flags
system_dependencies
security_notes
fixture_ids
```

The central dispatcher:

1. receives FileTypeTruth;
2. ranks compatible adapters;
3. probes;
4. selects one adapter or explicit ambiguous state;
5. executes extraction;
6. records adapter/version;
7. emits units and child artefacts;
8. hands structured units to fingerprint/schema layer.

No Next.js upload route should contain format-specific AI prompt logic.

# 9. Migration of the current upload paths

Audit existing:

- upload process routes;
- upload scan routes;
- grounded extraction;
- data-artifact generation;
- any Gemini base64 media/document paths.

Replace direct “send whole file to Gemini” behaviour with the registry/adapter/task-route pipeline.

Preserve existing useful records through migration/backfill.

Do not silently reclassify old AI summaries as grounded source evidence.

Mark legacy derived content with its actual basis and provenance status.

# 10. Test matrix

Every supported format needs at minimum:

```text
valid fixture
malformed fixture
extension/MIME/signature mismatch fixture
locator-resolution test
deduplication test where applicable
large/streamed fixture where applicable
```

Family-specific tests from delegated packages are mandatory.

Cross-family end-to-end fixtures:

1. ZIP containing JSON, JPEG and MBOX;
2. MBOX with PDF attachment;
3. scanned PDF inside Takeout archive;
4. XLSX with dates, URLs and opaque IDs;
5. MP4 with audio and subtitles;
6. image with EXIF GPS;
7. screenshot of a location website with no GPS;
8. GPX track;
9. SQLite database with a million-row synthetic table;
10. unknown binary blob;
11. encrypted archive;
12. duplicate embedded image in two parent files.

Required assertions:

- extension alone never decides type;
- unsupported files remain catalogued;
- corrupt binary is not uploaded to an LLM as a convenience fallback;
- OCR output resolves to page/region evidence;
- transcription resolves to media time ranges;
- spreadsheet extraction preserves formula/value distinction;
- email attachments become child artefacts;
- screenshot content cannot establish physical presence;
- downloaded image cannot establish physical presence;
- archive lineage remains resolvable;
- nested content cannot escape archive safety limits;
- every SUPPORTED format has a registered fixture and locator test.

# 11. Acceptance and completion report

The Task 3 orchestrator audits this companion plan line by line.

Report:

1. support registry;
2. P0/P1/P2 support matrix;
3. adapter modules and versions;
4. delegated sub-agent ownership;
5. exact file fixtures;
6. locator coverage;
7. specialist task routes used;
8. current direct-AI file paths removed or migrated;
9. unsupported formats;
10. optional system dependencies;
11. performance limitations;
12. every incomplete requirement.

Do not expand Task 3A into source-specific semantic profiling.

File-family extraction ends at generic units, metadata, structure and exact evidence locators. Source/schema parsers and the Task 3 temporal pipeline determine meaning.
