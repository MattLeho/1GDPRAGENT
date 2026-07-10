You are continuing architectural work in:

`MattLeho/1GDPRAGENT`

Inspect the current repository recursively before editing.

This task assumes the provenance/assertion/ontology foundation from the previous architecture brief is complete or is being used as the target architecture.

Use CURRENT CODE as the strongest evidence.

Read at minimum:

- `frontend/app/dashboard/settings/page.tsx`
    
- `frontend/components/settings/AICredentialsSection.tsx`
    
- `frontend/components/settings/APICredentialsSection.tsx`
    
- `frontend/components/settings/N8NWebhooksSection.tsx`
    
- `frontend/lib/model-preferences.ts`
    
- `frontend/lib/model-intents.ts`
    
- `frontend/lib/ai-credentials.ts`
    
- `frontend/lib/n8n-client.ts`
    
- all `frontend/app/api/settings/**`
    
- `frontend/lib/actions/email-settings.ts`
    
- `frontend/lib/actions/requests/submit.ts`
    
- all current N8N workflow JSON
    
- `intelligence/api/**`
    
- `intelligence/agents/**`
    
- `intelligence/tasks.py`
    
- `IMPLEMENTATION_TRACKER.md`
    

# Primary problem

The settings architecture currently treats broad workflow categories as model-selection tasks.

For example, one model purpose called `extraction` covers OCR, transcription, document parsing and summaries.

This is the wrong abstraction.

The application also has one global:

```text
built_in
n8n
hybrid
```

workflow-backend setting.

The target architecture requires:

1. task-specific execution routing;
    
2. per-workflow backend selection;
    
3. built-in implementations for all shipped core workflows;
    
4. N8N as an optional adapter;
    
5. a substantially redesigned settings UI.
    

# Product rule

Users should configure what engine performs a task.

They should not need to understand internal prompt architecture.

Example:

```text
Speech transcription
    Local Parakeet

Speech translation
    Local Whisper

Document OCR
    Local OCR

Unknown-schema interpretation
    Gemma local

Graph explanation
    GPT / Gemini / local model

Request drafting
    selected general model
```

The execution layer decides how to invoke the engine.

# 1. Introduce TaskDefinition and TaskRoute

Create a canonical task registry.

Suggested task keys:

```text
speech.transcription
speech.translation
speech.diarisation

image.metadata
image.origin_classification
image.ocr
image.caption
image.landmark_candidate

document.text_extraction
document.ocr
document.structure

schema.fingerprinting
schema.interpretation

semantic.adjudication
semantic.topic_labelling
semantic.context_correlation

temporal.change_detection
temporal.episode_labelling

graph.projection
graph.explanation

policy.extraction
policy.interpretation

request.drafting

email.classification
email.retention_adjudication

media.summary
```

Do not make every task use AI.

Every TaskDefinition should describe:

- `task_key`
    
- `display_name`
    
- `description`
    
- `task_category`
    
- `privacy_class`
    
- `input_modality`
    
- `output_schema`
    
- `deterministic`
    
- `default_engine_id`
    
- `supported_engine_types`
    
- `supports_local`
    
- `supports_external`
    
- `allows_external_in_strict_local`
    
- `configuration_schema`
    

Create TaskRoute persistence.

Minimum route configuration:

- `task_key`
    
- `engine_id`
    
- `provider`
    
- `model`
    
- `execution_location`
    
- `fallback_chain`
    
- `enabled`
    
- `max_concurrency`
    
- `batch_size`
    
- `timeout_ms`
    
- `configuration`
    
- `updated_at`
    

Execution location:

- `local`
    
- `external`
    
- `automatic`
    

# 2. Build an Engine Registry

Engine types should include:

- `deterministic`
    
- `local_model`
    
- `remote_model`
    
- `local_service`
    
- `remote_service`
    

Implement explicit engine adapters.

Initial engines should include where dependencies are available:

```text
deterministic_json
deterministic_tabular
deterministic_exif
deterministic_temporal

parakeet_local
whisper_local

local_ocr

ollama_generation

google_generation
openai_generation
openrouter_generation
huggingface_generation
nvidia_generation
```

Do not claim an engine is operational merely because a provider API key can be stored.

Each engine requires:

- health check;
    
- capability declaration;
    
- model discovery where applicable;
    
- invocation adapter;
    
- structured error result.
    

A selected non-Google engine must not silently send personal data to Google.

# 3. Split transcription from semantic analysis

The current upload processing uses Gemini for audio/video transcription.

Refactor it.

Target:

```text
audio/video
 ↓
ffmpeg normalisation where required
 ↓
speech.transcription TaskRoute
 ↓
timestamped transcript
 ↓
optional speech.diarisation
 ↓
deterministic transcript artefacts
 ↓
semantic analysis of selected transcript residue
```

Implement local ASR adapters.

Support at minimum:

```text
Parakeet
Whisper
```

Do not hardcode either as an architectural dependency.

Default selection may prefer Parakeet where the locally detected hardware and language requirements are supported.

Whisper remains available.

Separate:

```text
TRANSCRIPTION
```

from:

```text
TRANSCRIPT SUMMARY
TOPIC EXTRACTION
ENTITY EXTRACTION
```

The speech recogniser should not be asked to perform GDPR interpretation.

Persist:

- engine;
    
- model;
    
- transcript language;
    
- segment timestamps;
    
- word timestamps where available;
    
- confidence metadata where available;
    
- analysis run;
    
- derivation version.
    

# 4. Add execution privacy policy

Create processing modes:

```text
strict_local
local_first
controlled_cloud
```

Rules:

## strict_local

No personal-data content may be sent to an external engine.

External model routes are disabled for protected task inputs.

## local_first

Use local route first.

External fallback occurs only if:

- the task permits external execution;
    
- the route explicitly contains the external fallback;
    
- the user has enabled external fallback.
    

Record every external processing event.

## controlled_cloud

Approved external engines may run configured tasks.

Still record:

- task;
    
- engine;
    
- provider;
    
- model;
    
- timestamp;
    
- source artefact IDs;
    
- analysis run ID.
    

Do not display unsupported claims such as `zero retention guaranteed`.

Provider policy metadata is documentation metadata, not a technical guarantee.

# 5. Replace global workflow backend with WorkflowDefinition

Create a canonical workflow registry.

Every current N8N workflow JSON and every built-in workflow path must be inventoried.

Do not rely on the current hand-maintained N8N arrays.

Create WorkflowDefinition.

Minimum fields:

- `workflow_key`
    
- `display_name`
    
- `description`
    
- `category`
    
- `built_in_handler`
    
- `n8n_webhook_key`
    
- `supports_schedule`
    
- `configuration_schema`
    
- `required_task_keys`
    
- `required_connector_capabilities`
    

Create WorkflowPreference.

Fields:

- `workflow_key`
    
- `execution_mode`
    
- `enabled`
    
- `configuration`
    
- `fallback_order`
    
- `schedule`
    
- `updated_at`
    

Execution modes:

```text
built_in
n8n
hybrid
disabled
```

Selection is PER WORKFLOW.

Example:

```text
Request drafting      built_in
Email sending         built_in
Inbox monitoring      built_in
Response parsing      built_in
Graph projection      built_in
Transcription         built_in
Vendor OCR            built_in
Custom automation     n8n
```

# 6. Inventory and reconcile current workflows

Inspect all N8N workflow files and runtime webhook references.

The repository currently contains divergent workflow registries.

Produce a migration map containing:

```text
workflow
current N8N implementation
current built-in implementation
current callers
parity status
required work
```

Core application workflows must have built-in paths.

At minimum review:

- privacy-policy acquisition/analysis;
    
- request drafting;
    
- email sending;
    
- IMAP/Gmail connection testing;
    
- inbox monitoring;
    
- response classification;
    
- attachment/download detection;
    
- response parsing;
    
- file ingestion;
    
- identity ingestion;
    
- grounded extraction;
    
- graph projection;
    
- graph query/hybrid retrieval;
    
- transcription;
    
- vendor OCR;
    
- privacy-policy scanning;
    
- MAKGED validation.
    

Do not create duplicate built-in implementations where a Python intelligence service already performs the work.

Expose the existing Python implementation as the built-in handler.

# 7. Remove N8N as a requirement for email operation

The current request path may draft using the built-in workflow but relies on N8N for email transport.

Implement a built-in email transport.

Use the configured email connector/credential layer.

Support:

- SMTP where configured;
    
- provider-specific email connector where implemented.
    

Built-in request workflow:

```text
draft
 ↓
human review where configured
 ↓
send
 ↓
record message ID / transport metadata
 ↓
monitor response
```

N8N may replace or wrap the transport when selected for that workflow.

# 8. Fix email credential storage

The current email settings path base64-encodes the password and stores it as `password_encrypted`.

Base64 is not encryption.

Migrate email credentials to the canonical server-side encrypted credential system.

Requirements:

- never ask the browser to `btoa()` a secret and call it encrypted;
    
- encrypt server-side before persistence;
    
- do not return decrypted credentials to the browser;
    
- support credential rotation;
    
- support credential deletion;
    
- migrate legacy base64 records where safely identifiable;
    
- otherwise mark legacy credentials for re-entry;
    
- test decryption only inside the server-side connector/transport layer.
    

# 9. Rebuild Settings information architecture

Replace the single long settings card grid with settings navigation.

Suggested sections:

```text
Profile & Identity
Connectors
Processing & Models
Workflows
Data Retention
Privacy & Security
Advanced
```

## Profile & Identity

Existing profile and ID-document management.

## Connectors

Email and future data connectors.

Display:

- status;
    
- permissions;
    
- last sync;
    
- next sync;
    
- data classes;
    
- pause;
    
- resync;
    
- disconnect.
    

## Processing & Models

Task Execution Router.

Group by category:

```text
Speech
Images
Documents
Semantic Analysis
Graph
Policy & Requests
```

For every task show:

```text
Task name
Current engine
Local / External badge
Model where applicable
Fallback chain
Health
Configure
```

Use sensible defaults.

Allow an Advanced view for concurrency, batch size and timeout.

Do not force a user to select one global preferred model.

## Workflows

List WorkflowDefinitions.

Example row:

```text
Inbox monitoring

Execution:
[Built in]

Status:
Healthy

Uses:
Email connector

Schedule:
Continuous / incremental

Configure
```

N8N is one execution option.

When `n8n` is selected, expose webhook configuration for that workflow.

Do not show seven webhook password-style inputs to users who selected built-in workflows.

## Data Retention

Placeholder architecture for retention policies from the later connector/retention task.

## Privacy & Security

Display:

- processing mode;
    
- external processing audit;
    
- credential state;
    
- encryption state;
    
- local data paths;
    
- purge controls.
    

## Advanced

N8N dashboard/webhooks, raw provider configuration and development settings.

# 10. Add execution audit

Create an ExecutionRecord.

Fields:

- `id`
    
- `analysis_run_id`
    
- `task_key`
    
- `workflow_key`
    
- `engine_id`
    
- `provider`
    
- `model`
    
- `execution_location`
    
- `source_artifact_ids`
    
- `started_at`
    
- `completed_at`
    
- `status`
    
- `input_size`
    
- `output_size`
    
- `error`
    

The UI should be able to answer:

```text
Which external models processed my personal data?
```

# 11. Tests

Required tests:

- each TaskDefinition has a valid engine;
    
- unsupported engine/task combinations are rejected;
    
- strict-local mode blocks external invocation;
    
- local-first mode does not call external fallback when local succeeds;
    
- external fallback is audited;
    
- selected non-Google engine does not silently invoke Google;
    
- speech transcription does not invoke a general LLM by default;
    
- summary task receives transcript text, not original audio;
    
- every registered core workflow has a built-in implementation;
    
- N8N-disabled installation can draft, send and monitor a GDPR request using built-in workflows;
    
- workflow execution mode is per workflow;
    
- one workflow may use N8N while another uses built-in;
    
- legacy global workflow setting migrates safely;
    
- legacy email password storage is not treated as encrypted credential storage;
    
- browser never receives decrypted connector secrets.
    

# 12. Documentation

Update:

- README
    
- implementation tracker
    
- processing architecture
    
- workflow architecture
    
- settings architecture
    

At completion report:

1. current workflow inventory;
    
2. workflow parity table;
    
3. TaskDefinition registry;
    
4. engine adapters;
    
5. default task routes;
    
6. privacy execution modes;
    
7. settings redesign;
    
8. credential migration;
    
9. tests and exact results;
    
10. incomplete built-in workflow parity.
    

Do not build the Personal Insights page in this task.