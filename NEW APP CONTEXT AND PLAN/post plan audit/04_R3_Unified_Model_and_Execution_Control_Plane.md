# R3 — Unified Model and Execution Control Plane

## Goal

Make the canonical Task Router the only execution path from a product feature to a deterministic engine, local model or remote provider. Remove the active legacy model-routing architecture, expose model discovery, support complete fallback routes and audit every invocation.


## Programme rules

- Current code and runtime behaviour outrank previous completion reports.
- Preserve user data, provenance and migration history.
- PostgreSQL remains canonical; Neo4j remains a rebuildable projection.
- Model output cannot silently become graph truth.
- Every model call must use the canonical Task Router and create an execution record.
- Every protected operation must be scoped to the authenticated canonical profile.
- Distinguish unknown, unconfigured, unavailable, blocked and failed.
- Do not introduce hardcoded Google execution, synthetic graph data or invented compliance metrics.
- Implementation agents cannot be the sole final auditors of their own work.


## Dependencies

- R0–R2 accepted.
- Authentication, ownership and request schema are stable.

## Lead-agent ownership

The lead agent owns TaskDefinition/TaskRoute contracts, migration from legacy preferences, privacy and fallback semantics, credential integration, recommendation policy and the final repository-wide call-site audit.

## Subagent delegation

### A — Legacy routing removal

Inventory and remove runtime use of:

- `model_preferences`;
- `getWorkflowModelPreference`;
- direct provider calls;
- direct Gemini/Google model defaults;
- environment-only feature routing.

Create a safe migration to TaskRoutes.

### B — Provider/model discovery

Normalise discovery for:

- Ollama;
- OpenAI;
- OpenRouter;
- Google;
- NVIDIA NIM;
- Hugging Face;
- Parakeet;
- Whisper;
- OCR/deterministic services.

### C — Recommendation engine

Build deterministic task suitability scoring. Prefer the smallest healthy model that satisfies task, modality, privacy, structured-output and tool-use requirements.

### D — Hardware probe/setup jobs

Implement bounded, allowlisted setup jobs for local runtimes and weights. No arbitrary user-provided shell commands.

### E — Processing settings UI

Implement primary engine/model, ordered fallback engine/model, health, discovery, recommendations, setup state, validation and save feedback.

### F — Product call-site migration

Move request assistant, policy analysis, graph selection/explanation, uploads, schema interpretation, media, drafting, classification and adjudication to TaskRoute.

### G — Privacy/network audit tests

Prove provider isolation, fallback order, strict-local behaviour and execution auditing.

## Task inventory

Audit existing tasks and add explicit tasks where needed:

```text
request.assistant
request.tool_selection
policy.structured_analysis
graph.tool_selection
graph.result_explanation
semantic.entity_extraction
semantic.topic_labelling
semantic.context_correlation
```

Avoid one generic “AI” route.

## Model catalogue

Return a common contract containing:

```text
provider
engine_id
model_id
display_name
execution_location
installed
available
modalities
task_tags
parameter_class
context_length
structured_output
tool_calling
minimum_ram_gb
minimum_vram_gb
estimated_download_gb
cost_class
privacy_notes
catalogue_source
```

Unavailable metadata may be `unknown`; it must not be fabricated.

## Recommendation rules

Inputs:

- task capability;
- modality;
- privacy mode;
- local hardware;
- installed state;
- structured output;
- tool calling;
- expected context;
- latency;
- cost;
- explicit cloud approvals.

Example:

```text
semantic.topic_labelling
→ small healthy local instruction model
→ small approved remote model only when explicit fallback is enabled
```

Recommendation does not change a route without user action unless an explicit automatic mode is designed.

## Complete fallback chain

Each entry stores:

```text
engine_id
provider
model
execution_location
failure_conditions
```

Failure conditions may include unavailable, timeout, rate limit, not installed, out of memory and provider error. Privacy blocks never silently trigger unapproved external execution.

## Model setup jobs

Persist:

```text
requested engine/model
hardware assessment
required runtime
download estimate
explicit approval
progress
logs
verification
rollback/cleanup state
```

Initial allowlisted actions may include Ollama pulls and verified ASR dependency/model installation.

## Clear labels

Use:

```text
Ollama — Local Text Generation
Ollama — Local Vision-Language Model
NVIDIA NIM API — Cloud
NVIDIA Local Runtime — not implemented until a separate adapter exists
Parakeet — Local ASR
Whisper — Local ASR
Tesseract — Local OCR
```

## Request assistant migration

The assistant must:

- invoke a canonical task;
- use the configured route and fallbacks;
- create execution records;
- surface configuration failures as errors;
- not store provider errors as assistant responses;
- preserve grounded tool results and citations.

## Credential migration

Move active AI provider secrets to the canonical authenticated, versioned AES-GCM service. The old AES-CBC path becomes migration-only and then inactive.

## Execution records

Record:

```text
profile
task
workflow
engine
provider
model
local/external
source artefacts
input/output size
status
error
timestamps
fallback position
privacy decision
```

## Required tests

### Invariants

- no runtime `model_preferences` read;
- no direct Google call outside the provider adapter;
- no feature chooses a provider without TaskRoute;
- every model invocation creates an execution record.

### Provider isolation

- Ollama-only chat makes zero remote calls;
- OpenRouter makes zero Google calls;
- NVIDIA NIM uses NVIDIA;
- strict-local blocks external candidates;
- controlled-cloud allows only approved engines.

### Discovery/UI

- installed Ollama models appear;
- remote catalogues populate;
- missing credential is `unconfigured`;
- outage is `unavailable`;
- `Other model…` works;
- primary/fallback models can differ.

### Fallback

- primary local unavailable → configured local fallback;
- primary local unavailable → explicit remote fallback;
- privacy block cannot bypass consent;
- every attempt is audited.

### Setup

- unsuitable hardware gives a reason;
- approved setup streams progress;
- failed setup is recoverable;
- success appears in discovery and health.

### Browser

- route controls do not overlap;
- recommendations explain suitability;
- health offers setup where supported;
- request chat works without Google when another route is selected.

## Definition of done

- Task Router is the only active execution control plane.
- Legacy preferences are migrated and inactive.
- Request chat has no hidden Google default.
- Model discovery feeds dropdowns.
- Primary and fallback models are independently configurable.
- Provider labels are explicit.
- Setup jobs are bounded and auditable.
- Every invocation is privacy-gated and recorded.
- Independent call-site and network audits pass.

## Paste-ready `/goal`

```text
Execute R3 — Unified Model and Execution Control Plane.

Audit R0–R2 first. Make TaskRoute the only execution path. Remove active runtime dependence on model_preferences, migrate all product call sites, add missing explicit tasks, expose local and remote model catalogues, implement task-aware recommendations, complete primary and ordered fallback model configuration, clarify provider names and build bounded local setup jobs.

The request assistant, policy analysis, graph explanation, uploads, media, drafting, classification and adjudication must create ExecutionRecords. A selected non-Google route must never invoke Google.

Delegate legacy removal, discovery, recommendations, setup, UI, call-site migration and network tests to bounded subagents. Keep router contracts, privacy/fallback semantics, migrations, credentials and final call-site audit under the lead agent.

Before completion, run repository invariants, provider-isolation tests, fallback/setup scenarios and authenticated browser journeys. Commission independent call-site and network auditors.
```
