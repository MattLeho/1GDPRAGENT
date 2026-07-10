Prompt:
@GitHub nice thanks. Because of all this, obviously we already have our main dashboard pages to track and make requests and stuff and the graph view page as well, but I was thinking of adding an additional page for "personal insights" like a dashboard where it shows the users interests, with a slidebar timeline at the top so they can revisit their interests from any point in time, this would be a new page. This would consist of insights into what ive been searching about, what I spoke about with my AIs during the period, where I've been, things ive visited, changes compared to previous months or years, connections to outside events for example, instagram usage dropped from 20 mins a day to 0 on the same day as the online safety act came out- possible cause/ relation between the events. Obviously thats an example, I dont yuse instagram, but you get it. also the settings page needed a revamp, like we need to be able to plug in different models for different things like the transcription should use whispr not Gemini, that would be silly it would cost so much for something whispr or even a local model like parakeet could do very cheap or even free, so the settings page needs a revamp, and all of the existing N8N workflows need optional hard coded options as well as I cant be bothered to set up N8N on this machine and a lot of people wont care about N8N, so its good to have as an option but we should also have these workflows built in and easy to configure from the settings page. tbh for the 300gb data dump from google, a lot of it is images which I probably wont include but if they are ever included, it would be cool to extract time/location, if its a screenshot, what is the screenshot of etc so for example, if i took a picture of my uni in 2022 on a wednesday in november, we can assume i was there when the photo was taken and that can be added to my location map. then data connectors as well, sometimes we dont need a gdpr request to get information, like we can create a connector between the app and the users browser so all the search history is automatically sent to the GDPR app in real time, emails are processed and sorted and added to the graph in real time through connections etc and the data can be wiped on a schedule as normal through GDPR or the dashboards, say, every 6 months (but thats another problem I dont want to delete important emails, so we need to figure out which ones are important enough to stay and not get deleted, then also we have spam, if the user is receiving messages about ai newsletters cause they signed up years ago, the system might think that the user still has the interest even if they havent opened this newsletter for months)

Response form ChatGPT:

Yes. This is the missing **second half of the product**.

The current main dashboard is operational: requests, deadlines, retrieved data, review queues and data holders. The current home page is explicitly organised around those operational privacy metrics and links primarily to requests and the graph.

The graph answers:

> **How is my data structurally connected?**

The new **Personal Insights** page answers:

> **What does my digitally observable life look like through time?**

I would keep them completely separate.

```text
HOME
Operational privacy control

REQUESTS
Acquire / delete / challenge data

PERSONAL INSIGHTS
Understand behavioural and longitudinal patterns

DATA GRAPH
Understand structural links, profiles and capabilities

ONSIT
Discover external/public data exposure
```

The sidebar currently has Home, Requests, Data Graph, ONSIT, New Request and Settings; there is a clean conceptual gap for `/dashboard/insights`.

## The really important distinction: signal, exposure and engagement

Your newsletter example identifies a major flaw that would otherwise ruin the Personal Insights system.

Imagine:

```text
2021
Matt subscribes to AI newsletter

2022
newsletter arrives weekly

2023
newsletter arrives weekly

2024
newsletter arrives weekly

2025
newsletter arrives weekly

2026
newsletter arrives weekly
```

A naive topic counter says:

```text
AI interest:
2021 ███
2022 ████
2023 █████
2024 █████
2025 █████
2026 █████
```

Wrong.

The newsletter is evidence that **AI-related content entered Matt's information environment**.

It is not necessarily evidence that Matt engaged with it.

The ontology needs this distinction:

```text
AMBIENT EXPOSURE
Content was presented, sent or made available.

PASSIVE CONSUMPTION
Content appears to have been viewed.

ACTIVE INVESTIGATION
The user searched, queried, followed links or repeatedly returned.

CREATION
The user produced something about the topic.

IMPLEMENTATION
The user applied the topic to a project or workflow.

COMMUNICATION
The user actively discussed the topic.
```

Therefore:

```text
Newsletter received
    ↓
AI TOPIC EXPOSURE

Newsletter opened
    ↓
WEAK AI ENGAGEMENT SIGNAL

Newsletter link clicked
    ↓
ACTIVE AI ENGAGEMENT SIGNAL

Searches "SAM3 planning map extraction"
    ↓
AI + PLANNING INVESTIGATION SIGNAL

Asks ChatGPT 14 follow-up questions
    ↓
SUSTAINED INVESTIGATION EPISODE

Commits GeoPlanAgent integration
    ↓
AI IMPLEMENTATION SIGNAL
```

**A received email should contribute `0` to observed interest by default.**

It can contribute to:

```text
TopicExposureState
```

but not:

```text
ObservedInterestState
```

The same logic applies to AI conversations.

Your own message to an AI is behavioural evidence.

The AI's answer is mostly exposure.

For example:

```text
USER:
How could temporal satellite imagery identify abandonment?

    ↓

strong user-originated investigation signal
```

Then:

```text
ASSISTANT:
Here are 12 remote sensing techniques...

    ↓

content exposure
```

If you ask:

```text
How would UniverSat fit before SAM3?
```

that follow-up is more interesting. It shows continued engagement and conceptual integration.

The system should model:

```text
USER QUERY
      ↓
ASSISTANT OUTPUT
      ↓
USER FOLLOW-UP
      ↓
USER FOLLOW-UP
      ↓
CROSS-SOURCE SEARCH
      ↓
PROJECT ACTIVITY

= sustained investigation episode
```

That gives you something much closer to what profiling systems may care about.

Not:

```text
word "AI" appeared 900 times
```

## The external-events idea is extremely good, but it must not pretend to discover causes

Your Instagram example should produce:

```text
OBSERVED CHANGE

Instagram activity
20 min/day median
        ↓
0 min/day

Change point:
14 March
```

Then:

```text
CONTEXTUAL EVENT

Relevant regulatory event
14 March
```

The system may create:

```text
TemporalCorrelationCandidate
```

Not:

```text
Online Safety Act caused Matt to leave Instagram
```

I would calculate a correlation evidence vector:

```text
temporal_proximity
topic_relevance
user_exposure_evidence
direct_user_statement
preceding_search_activity
competing_changes
behavioural_persistence
```

This is the critical dimension:

```text
USER EXPOSURE EVIDENCE
```

Suppose usage collapses on the same date as a political event.

But you have:

```text
0 searches about it
0 AI conversations about it
0 emails opened about it
0 articles visited about it
0 messages mentioning it
```

Then the system says:

> **Possible temporal coincidence. No evidence currently shows that you encountered the event before the behavioural change.**

Much stronger example:

```text
10:42 search: "online safety act age verification"
10:51 BBC article visited
11:06 ChatGPT discussion about privacy impact
11:34 Instagram last activity
11:35 account settings visited
following 6 months: zero Instagram use
```

Now you have a much stronger **possible relation**.

Still not causal truth.

The system might say:

> **Instagram activity ceased during a short period of unusually concentrated Online Safety Act research. The available data shows direct exposure to the issue before the behavioural change. This supports a possible relationship, but does not establish cause.**

That is precisely the kind of insight your philosophy permits.

## Images: one correction to your university example

This:

> took a picture of my uni in November 2022

can potentially support a location observation.

This:

> has an image showing UCL

does **not**.

The media pipeline needs an evidence hierarchy.

```text
ORIGINAL CAMERA PHOTO
EXIF GPS
EXIF capture timestamp
        ↓
STRONG LOCATION OBSERVATION
```

EXIF defines an original capture time and time-zone metadata, and GPS EXIF tags can store camera latitude and longitude. ([exiftool.org](https://exiftool.org/TagNames/EXIF.html "https://exiftool.org/TagNames/EXIF.html"))

Then:

```text
ORIGINAL CAMERA PHOTO
capture timestamp
no GPS
recognisable UCL building
high-confidence landmark match
        ↓
LOCATION CANDIDATE
```

Then:

```text
SCREENSHOT
Google Maps open at UCL
        ↓
NO LOCATION PRESENCE INFERENCE
```

Instead:

```text
CONTENT EXPOSURE:
UCL / mapping / location content
```

Likewise:

```text
downloaded Instagram image of Paris
```

does not mean:

```text
Matt was in Paris
```

The first stage must therefore classify:

```text
CAMERA_ORIGIN
SCREENSHOT
DOWNLOADED_MEDIA
EDITED_MEDIA
GENERATED_MEDIA
UNKNOWN
```

Then apply different analysis rules.

I would make media ingestion **metadata-only by default**.

```text
METADATA ONLY
hash
capture date
GPS
device/camera
dimensions
file lineage

SELECTIVE VISUAL ANALYSIS
screenshots
location candidates
unclassified media
user-selected folders

FULL MEDIA ANALYSIS
explicit opt-in
```

That means your `300 GB` Takeout does not suddenly turn into `200 GB` of VLM calls.

The current upload system does the opposite: it base64-encodes image files and sends them to the configured Google extraction path for OCR/visual description. The other upload path similarly sends image bytes to Gemini.

That should become a last-stage fallback.

## The settings redesign is now necessary

The current model selector has only:

```text
Default / RLM
Request Drafting
File Extraction
Knowledge Graph
Policy Analysis
```

and `File Extraction` explicitly includes **“OCR, transcription, document parsing, and summaries”**.

That abstraction is wrong.

A model is not selected because something is vaguely called “extraction”.

The app needs a **Task Execution Router**.

For example:

|Task|Default engine|
|---|---|
|Speech transcription|Local Parakeet|
|Speech translation|Whisper|
|Speaker diarisation|NeMo/diarisation engine|
|Image metadata|ExifTool/deterministic|
|Screenshot detection|Deterministic classifier|
|Screenshot OCR|Local OCR|
|Image caption|Local VLM|
|Landmark candidate|Vision model|
|JSON parsing|Deterministic|
|Unknown-schema interpretation|Semantic model|
|Topic labelling|Small semantic model|
|Temporal change detection|Deterministic|
|Context-event interpretation|Semantic model|
|Graph explanation|General LLM|
|Policy analysis|Grounded semantic model|
|DSAR drafting|General LLM|

Your transcription example is exactly right.

OpenAI's Whisper is a dedicated speech-recognition model with local model weights and several model sizes; its official repository describes multilingual recognition, speech translation and local Python use. ([GitHub](https://github.com/openai/whisper "https://github.com/openai/whisper")) NVIDIA's current Parakeet TDT `0.6B v3` is a **“600-million-parameter”** high-throughput ASR model supporting **“25” European languages**, including English, French and Spanish, and exposes word- and segment-level timestamps. ([Hugging Face](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3 "https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3"))

Using Gemini as the normal transcription engine when Parakeet or Whisper is locally available is architecturally backwards.

Gemini could still be used afterwards:

```text
AUDIO
 ↓
Parakeet
 ↓
TIMESTAMPED TRANSCRIPT
 ↓
deterministic entities / topics
 ↓
small semantic residue
 ↓
LLM interpretation
```

Not:

```text
AUDIO
 ↓
Gemini please do everything
```

## N8N should become an adapter, not a mode for the entire application

The current setting is:

```text
built_in
n8n
hybrid
```

globally.

That is too crude.

You might want:

```text
Policy analysis        BUILT IN
Request drafting       BUILT IN
Email sending          BUILT IN
Inbox monitoring       BUILT IN
Response parser        BUILT IN
Graph projection       BUILT IN
Transcription          BUILT IN
Vendor OCR             BUILT IN

Custom enterprise flow N8N
Special automation     N8N
```

Or:

```text
Request drafting       BUILT IN
Email sending          N8N
Inbox monitoring       BUILT IN
```

Each workflow therefore needs:

```text
execution_mode:
  BUILT_IN
  N8N
  HYBRID
  DISABLED
```

individually.

The repo already demonstrates why a shared registry is necessary. The settings UI lists **“7”** N8N webhook types, while `n8n-client.ts` has a different **“6”**-entry webhook registry.

The implementation tracker also explicitly says that inbox monitoring/response parsing and some KG/identity/hybrid RAG paths remain to be translated into built-in services.

And the current built-in request flow still says that built-in mode drafts the request but does not send it; delivery depends on N8N in hybrid mode.

So yes: **every shipped workflow needs a built-in implementation**.

N8N can remain for people who actively want it.

A person cloning your repo should be able to:

```text
docker compose up
 ↓
open settings
 ↓
connect email
 ↓
select local/cloud processing
 ↓
use the app
```

without opening an N8N canvas.

## The connector idea is also the correct direction

GDPR should not be the only acquisition mechanism.

It should be:

```text
DATA ACQUISITION LAYER

GDPR / DSAR
Browser connector
Email connector
AI conversation import
Photo library
Filesystem
Device exports
Manual import
Future integrations
        ↓
SAME EVIDENCE PIPELINE
```

A Chrome extension can receive visit events through the Chrome History API's `onVisited` event; visit records expose visit time, referrer linkage, transition type and whether a visit originated locally or from synced history. ([Chrome for Developers](https://developer.chrome.com/docs/extensions/reference/api/history "https://developer.chrome.com/docs/extensions/reference/api/history")) A browser extension can also use Chrome native messaging to exchange JSON messages with a local native host rather than treating a remote cloud API as the default data sink. ([Chrome for Developers](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging "https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging"))

That gives you:

```text
Chrome
  ↓
GDPR Agent browser extension
  ↓
local native bridge
  ↓
SourceConnector
  ↓
ActivityEvent
  ↓
event lake
```

The browser connector should never write:

```text
Matt interested in AI
```

It writes:

```text
2026-07-10 13:42
VISITED
openai.com/...
transition=link
source=browser_connector
```

The analysis system does the rest.

Email works the same way.

For Gmail, Google's official push system uses a mailbox `watch`, Cloud Pub/Sub and change-history IDs, and the watch must be renewed at least once every **“7” days**. ([Google for Developers](https://developers.google.com/gmail/api/guides/push "https://developers.google.com/gmail/api/guides/push")) That makes Gmail push a valid optional connector, but not the simplest local-first default.

I would support:

```text
BUILT-IN IMAP INCREMENTAL SYNC
default

GMAIL API
optional specialist connector

N8N EMAIL WORKFLOW
optional adapter
```

## And deletion must be separate from interest analysis

This is important.

Do **not** build:

```text
Interest model says newsletter irrelevant
 ↓
delete email
```

The deletion system needs an independent **Retention Decision Engine**.

For email:

```text
KEEP_LEGAL_OR_REGULATORY
KEEP_FINANCIAL
KEEP_IDENTITY_OR_SECURITY
KEEP_PROJECT_RECORD
KEEP_ACTIVE_CONVERSATION
KEEP_PERSONAL_SIGNIFICANCE
LOW_VALUE_BULK
SPAM
UNSURE
```

Evidence might include:

```text
user sent/replied
thread depth
starred
explicit user label
attachment
invoice/receipt
contract
education context
employment context
bank/payment context
travel booking
account security
calendar/event relationship
named human correspondent
bulk-mail headers
List-Unsubscribe
repeated template structure
no-reply sender
historical engagement
```

Your AI newsletter example becomes:

```text
received every week
List-Unsubscribe present
bulk sender
no replies
no clicked links observed
no related browsing from email
no active interaction for 11 months

        ↓

LOW_VALUE_BULK candidate
```

Separately:

```text
Matt independently searched AI 400 times
built 3 AI projects
discussed AI with assistants

        ↓

strong observed AI signal
```

The newsletter does not create that interest.

I would also separate three deletion operations:

```text
LOCAL_PURGE
Delete the copy held by GDPR Agent.

SOURCE_DELETE
Delete data through a connected source where supported.

CONTROLLER_ERASURE_REQUEST
Exercise GDPR deletion rights against the organisation.
```

They are not the same action.

For scheduled deletion:

```text
POLICY
delete eligible low-value email after 6 months

 ↓

DRY RUN

 ↓

1,842 deletion candidates
37 uncertain
18 protected

 ↓

REVIEW

 ↓

QUARANTINE / LABEL

 ↓

GRACE PERIOD

 ↓

DELETE

 ↓

VERIFY
```

Never auto-delete `UNSURE`.

# Revised implementation order

I would slightly change the sequence I gave you before:

```text
OLD PLAN 1
Evidence ledger + provenance + ontology foundation

        ↓

NEW PLAN A
Task execution router + settings + workflow registry

        ↓

OLD PLAN 2
300 GB ingestion + event lake + temporal engine

        ↓

NEW PLAN B
Personal Insights + contextual correlations + media intelligence

        ↓

NEW PLAN C
Live connectors + retention policies

        ↓

OLD PLAN 3
Capability + purpose drift + active DSAR testing
```

The new settings architecture should come **before** the `300 GB` pipeline because otherwise Codex will hardwire processing engines while building the ingestion system.

# Codex brief A — Task Execution Router, built-in workflow parity and settings rebuild

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

# Codex brief B — Personal Insights, temporal exploration, contextual correlations and media intelligence

Continue work in:

`MattLeho/1GDPRAGENT`

This task assumes:

- immutable evidence and Assertion architecture exists;
    
- the event lake and temporal analysis engine exist;
    
- Task Execution Router exists;
    
- high-volume ActivityEvents are not stored individually in Neo4j.
    

Inspect the actual merged repository before editing.

# Primary task

Create a new user-facing page:

```text
/dashboard/insights
```

Display name:

```text
Personal Insights
```

This page is a longitudinal, evidence-backed projection of the person's own data.

It is not the Data Graph page.

The distinction is:

```text
Data Graph
How are my data, identifiers, controller profiles and capabilities connected?

Personal Insights
How did my observed activity, interests, routines, projects, places and engagement change through time?
```

The page must never present model-generated psychological interpretation as fact.

# 1. Add Personal Insights to dashboard navigation

Add:

```text
Personal Insights
/dashboard/insights
```

to the primary dashboard navigation.

Position it between operational request management and the structural Data Graph.

Suggested conceptual navigation:

```text
Home
View Requests
Personal Insights
Data Graph
ONSIT Discovery
New Request
Settings
```

Use a suitable existing Lucide icon.

Do not overload the Home dashboard with the full insights experience.

A small Personal Insights preview may later be added to Home.

# 2. Build the page around one global temporal control

At the top of the page create a persistent time control.

Modes:

```text
POINT IN TIME
PERIOD
COMPARE
```

Granularity:

```text
month
quarter
year
custom
```

Example:

```text
JAN 2019 ─────── JUN 2021 ─────── MAY 2024 ─────── NOW
                            ▲
                         selected
```

Render a low-profile activity-density histogram behind or beneath the time slider.

This helps the user see sparse and dense periods.

The selected period is global page state.

All insight modules must use the same temporal selection unless a module explicitly enters local drill-down mode.

Support shareable query parameters:

```text
?from=
?to=
?compareFrom=
?compareTo=
```

# 3. Do not create a second source of truth

The Personal Insights page must query:

- ActivityEvent partitions;
    
- accepted Assertions;
    
- TemporalStates;
    
- ProjectEpisodeCandidates;
    
- PersonalEraCandidates;
    
- ControllerProfile states where explicitly compared.
    

Do not create generic editable fields such as:

```text
current_interest = AI
```

Materialised insight tables may exist for performance.

They are derived views linked to:

- analysis run;
    
- derivation method;
    
- derivation version.
    

# 4. Create InsightSnapshot API

Implement a typed PersonalInsightsService.

Suggested methods:

```text
get_period_overview
get_interest_states
get_search_insights
get_ai_conversation_insights
get_place_insights
get_engagement_profile
get_project_episodes
get_routine_changes
get_personal_drift
get_contextual_correlations
trace_insight
```

Build APIs such as:

```text
GET /api/insights/overview
GET /api/insights/interests
GET /api/insights/search
GET /api/insights/ai-conversations
GET /api/insights/places
GET /api/insights/changes
GET /api/insights/context
GET /api/insights/evidence/:id
```

Endpoints must accept temporal parameters.

Return machine-readable evidence references.

# 5. Model exposure separately from engagement

Create or formalise:

```text
TopicExposureState
ObservedInterestState
EngagementProfile
```

Do not derive interest from topic occurrence count alone.

Evidence classes must distinguish:

```text
AMBIENT_EXPOSURE
PASSIVE_CONSUMPTION
ACTIVE_INVESTIGATION
CREATION
IMPLEMENTATION
COMMUNICATION
```

Examples:

```text
newsletter received
    AMBIENT_EXPOSURE

newsletter opened
    PASSIVE_CONSUMPTION candidate

newsletter link followed
    ACTIVE_INVESTIGATION

search query
    ACTIVE_INVESTIGATION

user-authored AI prompt
    ACTIVE_INVESTIGATION or COMMUNICATION

assistant output
    AMBIENT_EXPOSURE

repeated AI follow-up
    sustained ACTIVE_INVESTIGATION

project file created
    CREATION

code / workflow implementation
    IMPLEMENTATION

email reply about topic
    COMMUNICATION
```

A received email must not increase ObservedInterestState by default.

A recommendation shown to the user must not increase ObservedInterestState by default.

# 6. Add source-specific signal semantics

## Browser/search

Model:

- query;
    
- visit;
    
- transition;
    
- revisitation;
    
- active duration where reliable;
    
- bookmark/save;
    
- referrer path;
    
- domain diversity.
    

A single search is weak evidence.

Repeated related searches, cross-source investigation and subsequent creation are stronger.

Do not infer enduring interest from one curiosity search.

## AI conversations

Separate:

```text
USER_AUTHORED_TURN
ASSISTANT_GENERATED_TURN
```

User-authored turns are behavioural evidence.

Assistant-generated turns are primarily exposure.

Calculate:

- topic;
    
- follow-up depth;
    
- session duration;
    
- repeated session count;
    
- topic recurrence;
    
- question refinement;
    
- cross-session return.
    

Detect investigation chains.

Example:

```text
initial question
 ↓
technical follow-up
 ↓
architecture follow-up
 ↓
implementation follow-up
 ↓
related project activity
```

Create:

```text
InvestigationEpisodeCandidate
```

Do not classify the user psychologically.

## Email

Separate:

- received;
    
- opened where reliably known;
    
- clicked where evidence exists;
    
- replied;
    
- forwarded;
    
- archived;
    
- deleted;
    
- unsubscribed.
    

Bulk/newsletter arrival is exposure.

User replies are strong communication evidence.

Do not treat recurring newsletters as continuing interest merely because they continue arriving.

## Creation/project activity

Where connectors provide evidence, support:

- documents created;
    
- files modified;
    
- repositories changed;
    
- project episodes;
    
- repeated tool use.
    

Creation and implementation signals should remain separate from consumption.

# 7. Build Personal Insights page modules

## A. Period overview

Example:

```text
APRIL 2026

Most active topics
Planning
AI
Transport

3 emerging topic clusters
2 returning interests
1 major project episode

Observed activity:
Investigation 38%
Creation 27%
Implementation 19%
Communication 11%
Passive consumption 5%
```

Every percentage must be calculated.

## B. Interest Atlas

Display hierarchical topics.

Example:

```text
Artificial Intelligence

Intensity      ████████
Persistence    ██████
Recurrence     ███████
Breadth        █████████
Novelty        ██
Context spread ████████
```

The six-dimensional state is authoritative.

An optional composite display is secondary.

Allow topic expansion:

```text
AI
 ├── LLMs
 │    ├── Agents
 │    ├── RAG
 │    └── Local inference
 ├── Computer Vision
 └── AI Governance
```

Show:

- selected-period state;
    
- previous-period state;
    
- peak period;
    
- first observed;
    
- latest observed;
    
- active source domains.
    

## C. Search and investigation

Show:

- recurring searches;
    
- emerging question clusters;
    
- investigation episodes;
    
- query refinement chains;
    
- abandoned one-off searches;
    
- searches that later appear in project activity.
    

Do not display sensitive raw queries on the overview without appropriate user control.

Allow evidence drill-down.

## D. AI conversations

Show:

- user-originated topics;
    
- sustained conversation clusters;
    
- recurrent questions;
    
- assistants/services used;
    
- project-linked conversations;
    
- follow-up depth.
    

Do not use assistant-generated text as equal-strength evidence of the user's interests.

## E. Places and movement

Render an interactive map.

Support location evidence classes:

```text
DEVICE_LOCATION
EXIF_GPS
ADDRESS_EVENT
POSTCODE_EVENT
PLACE_EVENT
VISUAL_LOCATION_CANDIDATE
```

Display confidence and evidence type.

The user must be able to filter:

```text
Confirmed/strong observations
Candidates
All
```

Show:

- recurrent places;
    
- new places;
    
- changes in activity centres;
    
- travel periods;
    
- place-linked project episodes.
    

Do not automatically name a dominant overnight cluster `HOME`.

## F. Engagement profile

Display:

```text
CONSUMPTION
INVESTIGATION
CREATION
IMPLEMENTATION
COMMUNICATION
```

Compare with previous period.

Example:

```text
Implementation +41%
Passive consumption -18%
```

## G. Changes

Show:

```text
EMERGING
DECLINING
RETURNING
TEMPORARY BURST
REGIME SHIFT
ROUTINE CHANGE
```

Each card must explain the detector output.

Example:

```text
Urban transport returned after 11 months of low activity.

Evidence:
4 active periods
3 prior dormant periods
mean dormancy: 8.2 months
```

## H. Project episodes

Show burst-derived episodes.

Example:

```text
HEALTHY STREETS WORKFLOW EPISODE
6–19 June 2026

Observed signals:
transport planning
Healthy Streets
workflow automation
data sources
presentation activity

Peak investigation:
11 June

Shift towards implementation:
6 July
```

Do not invent a project name unless:

- source evidence names it;
    
- the user confirms it;
    
- or the label is visibly marked machine-generated.
    

## I. Personal eras

Display contiguous behavioural-regime candidates.

Machine label and human label are separate.

Example:

```text
Machine candidate:
"Planning + transport implementation period"

Your label:
"PJA placement"
```

# 8. Build Contextual Correlation Engine

Purpose:

Surface possible relationships between detected behavioural changes and external events.

The engine must detect the behavioural change FIRST.

Do not scan world events and search the user's history for arbitrary coincidences.

Pipeline:

```text
behavioural time series
 ↓
change point / burst / regime shift
 ↓
detected local event
 ↓
retrieve relevant external-context events around window
 ↓
calculate contextual relation vector
 ↓
TemporalCorrelationCandidate
```

Create:

```text
TemporalCorrelationCandidate
```

Fields:

- `id`
    
- `local_change_id`
    
- `external_event_id`
    
- `temporal_proximity`
    
- `semantic_relevance`
    
- `user_exposure_evidence`
    
- `direct_user_statement`
    
- `preceding_related_activity`
    
- `behavioural_persistence`
    
- `competing_explanations_count`
    
- `status`
    
- `analysis_run_id`
    

Statuses:

```text
coincidence_candidate
possible_relation
evidence_supported_relation
user_confirmed
rejected
```

Never use `caused_by` as a machine-generated relationship.

A direct user statement may create a human-confirmed causal claim.

## Exposure evidence

Before strengthening an external-event relationship, search for evidence that the user encountered the subject.

Examples:

- relevant search;
    
- article visit;
    
- user-authored AI discussion;
    
- email engagement;
    
- message authored by user;
    
- user confirmation.
    

Example output:

```text
Instagram use fell from a 20-minute daily median to zero on 14 March.

A relevant regulatory event occurred on the same date.

No evidence currently shows you encountered the event before the behavioural change.

Classification:
Temporal coincidence candidate.
```

Stronger example:

```text
Instagram use ceased after a concentrated 52-minute period of searches and AI discussion about the same regulatory issue.

Related activity occurred before the final Instagram session.

Classification:
Possible relation.

This does not establish cause.
```

# 9. Build external context event storage

Create ExternalContextEvent.

Fields:

- `id`
    
- `title`
    
- `event_type`
    
- `occurred_at`
    
- `ended_at`
    
- `topics`
    
- `jurisdiction`
    
- `source_uri`
    
- `source_artifact_id`
    
- `ingested_at`
    

Sources may later include:

- legislation/regulation feeds;
    
- public policy events;
    
- major platform changes;
    
- software/product releases;
    
- cultural events;
    
- user-added events.
    

External event ingestion must remain separate from personal-data ingestion.

Do not send personal behavioural data to public event sources.

# 10. Add optional Media Intelligence pipeline

Media processing is opt-in and tiered.

Modes:

```text
metadata_only
selective_visual
full_visual
```

Default:

```text
metadata_only
```

## Stage 1: deterministic metadata

For every image:

- content hash;
    
- perceptual hash where appropriate;
    
- format;
    
- dimensions;
    
- EXIF;
    
- capture timestamp;
    
- timezone metadata;
    
- GPS;
    
- camera/device metadata;
    
- editing software metadata where available.
    

Preserve raw metadata as evidence.

## Stage 2: media-origin classification

Classify:

```text
camera_origin
screenshot
downloaded_media
edited_media
generated_media
unknown
```

Use deterministic metadata/path/dimension heuristics first.

Semantic model only receives ambiguous candidates.

## Stage 3: route by origin class

### camera_origin

Potentially extract:

- scene category;
    
- objects;
    
- landmark candidate;
    
- visual location candidate.
    

GPS + original capture timestamp may create a strong location observation.

No GPS + visual landmark produces a location candidate.

Require evidence and confidence.

### screenshot

Extract:

- OCR;
    
- application/interface candidate;
    
- webpage/service candidate;
    
- visible topics;
    
- visible entities.
    

A screenshot showing a place must not establish physical presence.

### downloaded_media

May contribute content exposure.

It does not establish physical presence.

### unknown

Review or selected visual analysis.

## Stage 4: location evidence

Create MediaLocationCandidate.

Minimum fields:

- `artifact_id`
    
- `occurred_at`
    
- `temporal_precision`
    
- `location_type`
    
- `lat`
    
- `lon`
    
- `place_label`
    
- `basis`
    
- `confidence`
    
- `evidence_locator_id`
    

Basis:

```text
exif_gps
takeout_sidecar
visual_landmark
user_confirmed
```

Do not merge visual landmark candidates into confirmed location observations automatically.

# 11. Evidence inspector

Every insight card requires:

```text
Why am I seeing this?
```

The evidence drawer should display:

- detector;
    
- detector version;
    
- analysis run;
    
- time window;
    
- calculated features;
    
- source counts;
    
- supporting ActivityEvents;
    
- supporting Assertions;
    
- source artefacts;
    
- evidence locators;
    
- model explanation where used.
    

The model explanation is not the evidence.

# 12. Performance

Do not query millions of Parquet records separately for every React card.

Create period-level materialised aggregates.

Suggested levels:

```text
day
week
month
quarter
year
```

Invalidate/recompute aggregates by analysis run and affected partition.

Use DuckDB/Polars for bulk calculations.

The frontend consumes compact insight payloads.

# 13. Tests

Required synthetic scenarios:

1. newsletter received weekly for 3 years but never engaged with;
    
2. newsletter received and clicked repeatedly;
    
3. AI answer mentions robotics but user never follows up;
    
4. user asks repeated robotics questions across 6 sessions;
    
5. search burst followed by project creation;
    
6. one curiosity search does not become enduring interest;
    
7. topic disappears and returns after 9 months;
    
8. camera photo with GPS and capture time;
    
9. UCL landmark photo without GPS;
    
10. screenshot of UCL website;
    
11. downloaded photo of Paris;
    
12. behavioural usage collapse aligned with unrelated external event;
    
13. behavioural change aligned with event but no user exposure evidence;
    
14. behavioural change preceded by relevant searches and user-authored AI discussion;
    
15. contextual candidate never becomes causal fact automatically;
    
16. user confirms a relationship;
    
17. historical data imported in 2026 appears at historical occurred_at time while system discovery remains 2026;
    
18. all insight evidence links resolve to source evidence.
    

Required assertions:

- ambient email exposure does not increase ObservedInterestState by default;
    
- assistant output is not weighted as a user-authored interest signal;
    
- screenshots cannot establish physical presence;
    
- downloaded images cannot establish physical presence;
    
- visual landmark result is a candidate until reviewed;
    
- external-event search begins from detected personal change points;
    
- temporal proximity alone cannot produce evidence-supported relation;
    
- insight materialisation is reproducible from source events.
    

# 14. Documentation

Document:

- Personal Insights philosophy;
    
- signal versus exposure;
    
- time-slider architecture;
    
- AI conversation semantics;
    
- contextual correlation guardrails;
    
- media evidence hierarchy;
    
- location inference guardrails.
    

At completion report:

1. page architecture;
    
2. APIs;
    
3. insight modules;
    
4. interest evidence semantics;
    
5. AI conversation semantics;
    
6. Contextual Correlation Engine;
    
7. Media Intelligence pipeline;
    
8. map/location evidence hierarchy;
    
9. performance strategy;
    
10. tests and exact results.
    

Do not implement automatic data deletion in this task.

# Codex brief C — live data connectors and conservative retention/deletion policies

Continue work in:

`MattLeho/1GDPRAGENT`

This task assumes:

- provenance/assertion architecture exists;
    
- ActivityEvent event lake exists;
    
- Task Execution Router exists;
    
- Personal Insights evidence semantics distinguish exposure from engagement.
    

# Primary task

Create a general Data Connector architecture and a conservative retention/deletion policy system.

GDPR/DSAR is one acquisition mechanism.

The application must also support user-authorised direct data sources where appropriate.

Target:

```text
DSAR / export
Browser
Email
AI conversation import
Photo library
Filesystem
Future providers
        ↓
SourceConnector
        ↓
SourceArtifact / ActivityEvent
        ↓
same provenance and analysis pipeline
```

No connector may directly write semantic truth to Neo4j.

# 1. Create SourceConnector architecture

Create a canonical SourceConnector interface.

Connector modes:

```text
snapshot_import
incremental_poll
event_stream
webhook_push
folder_watch
```

A connector must declare:

- `connector_key`
    
- `display_name`
    
- `provider`
    
- `connector_type`
    
- `supported_modes`
    
- `data_classes`
    
- `permissions`
    
- `supports_backfill`
    
- `supports_incremental`
    
- `supports_source_delete`
    
- `supports_remote_delete_request`
    
- `configuration_schema`
    

Create ConnectorInstance.

Fields:

- `id`
    
- `profile_id`
    
- `connector_key`
    
- `status`
    
- `configuration_encrypted`
    
- `permissions`
    
- `sync_mode`
    
- `last_cursor`
    
- `last_sync_at`
    
- `next_sync_at`
    
- `last_error`
    
- `created_at`
    
- `updated_at`
    

Status:

```text
connected
paused
degraded
authentication_required
error
disconnected
```

Create ConnectorSyncRun.

Track:

- connector;
    
- cursor before;
    
- cursor after;
    
- artefacts discovered;
    
- events produced;
    
- duplicates skipped;
    
- errors;
    
- start/end time.
    

# 2. Connector ingestion invariant

Every connector uses the same acquisition pipeline.

Example:

```text
browser visit
 ↓
connector raw record
 ↓
SourceArtifact or typed source record
 ↓
EvidenceLocator
 ↓
ActivityEvent
 ↓
temporal analysis
```

Do not let the browser connector create:

```text
INTERESTED_IN AI
```

Do not let the email connector create:

```text
IMPORTANT EMAIL
```

These are later analytical decisions.

Preserve raw source semantics.

# 3. Build Browser Connector MVP

Create a separate browser-extension package or clearly isolated directory.

Target Chromium first.

Use the browser history API with explicit permission.

Capture relevant visit events.

Where available preserve:

- URL;
    
- visit timestamp;
    
- transition type;
    
- referring visit ID;
    
- local/synchronised origin indicator;
    
- browser profile connector ID.
    

Do not capture page body content by default.

Create a local bridge.

Preferred architecture:

```text
browser extension
 ↓
native messaging host
 ↓
local GDPR Agent connector service
```

The extension should not require a cloud relay.

Implement:

- initial backfill;
    
- incremental event handling;
    
- reconnect;
    
- local queue;
    
- acknowledgement;
    
- deduplication;
    
- connector health.
    

Use deterministic visit event signatures.

URL decomposition occurs in the personal-data processing pipeline.

## Optional content capture

Page-content capture is OFF by default.

If later enabled:

- scope by explicit domain/rule;
    
- display permissions clearly;
    
- capture only approved page metadata/text;
    
- preserve source URL and timestamp;
    
- never capture password fields;
    
- never capture payment forms;
    
- never capture private content merely because the extension technically can.
    

# 4. Build Email Connector architecture

The existing email configuration is centred on sending GDPR requests and N8N IMAP testing.

Refactor email into a SourceConnector plus EmailTransport capability.

Separate:

```text
EMAIL SOURCE CONNECTOR
read/synchronise authorised mailbox data

EMAIL TRANSPORT
send GDPR requests and replies
```

Support built-in IMAP as the initial generic connector.

Support provider-specific connectors later.

Optional Gmail API adapter may be implemented where credentials/configuration exist.

Email sync must be incremental.

Persist provider/message stable IDs where available.

Preserve:

- mailbox/folder;
    
- message ID;
    
- thread ID;
    
- sender;
    
- recipients;
    
- timestamp;
    
- subject;
    
- headers relevant to classification;
    
- attachment metadata;
    
- body according to user-selected ingestion scope.
    

User-selectable ingestion scopes:

```text
metadata_only
headers_and_subject
text_body
full_message
```

Attachments may use separate ingestion policies.

# 5. Build EmailEvent semantics

Create source-level events:

```text
EMAIL_RECEIVED
EMAIL_SENT
EMAIL_REPLIED
EMAIL_FORWARDED
EMAIL_ARCHIVED
EMAIL_DELETED
EMAIL_OPENED_CANDIDATE
EMAIL_LINK_CLICKED
EMAIL_UNSUBSCRIBED
```

Only create events supported by connector evidence.

Do not invent `EMAIL_OPENED` if the connector does not expose reliable evidence.

Model newsletter/bulk exposure separately from engagement.

# 6. Build bulk/newsletter candidate detector

Use deterministic evidence first.

Candidate signals may include:

- `List-Unsubscribe`;
    
- `List-Id`;
    
- bulk precedence headers;
    
- no-reply sender;
    
- repeated sender;
    
- repeated template signature;
    
- repeated subject pattern;
    
- high send frequency;
    
- many recipients where observable;
    
- low user reply rate.
    

Produce:

```text
BulkMailCandidate
NewsletterCandidate
```

Do not treat these as spam automatically.

# 7. Interest semantics for email

Enforce:

```text
EMAIL_RECEIVED
    topic exposure only

EMAIL_OPENED_CANDIDATE
    weak passive-engagement evidence

EMAIL_LINK_CLICKED
    active-engagement evidence

EMAIL_REPLIED
    strong communication evidence

EMAIL_UNSUBSCRIBED
    disengagement action
```

Repeated delivery without engagement must not sustain an ObservedInterestState.

Implement engagement decay.

Do not call decay `disinterest`.

Use:

```text
current observed engagement weakened
```

# 8. AI conversation connectors

Create connector architecture for AI conversation sources.

Initial priority:

```text
snapshot import/export parser
```

Support known export formats through StructureFingerprint and approved parser specs.

Preserve:

```text
conversation
turn
speaker role
timestamp
service
model where known
conversation title
source locator
```

Speaker role must distinguish:

```text
user
assistant
system
tool
unknown
```

Only user-authored turns contribute direct behavioural-query signals by default.

Provider APIs may be added where officially supported and explicitly authorised.

Do not implement brittle authenticated page scraping as the default connector strategy.

Browser-assisted capture must be separately opt-in.

# 9. Photo/media library connector

Create a folder-watch/snapshot connector.

User selects directories.

Modes:

```text
metadata_only
selected_visual_analysis
full_visual_analysis
```

Default:

```text
metadata_only
```

Folder watcher should detect:

- new file;
    
- modified file;
    
- removed file.
    

Content hashing prevents duplicate analysis.

Removal from the folder does not delete historical evidence automatically.

Create a new source observation indicating removal from the connected source view.

# 10. Filesystem connector framework

Implement an explicit directory connector.

Scope only user-selected paths.

Do not recursively index the entire machine by default.

Configuration:

- roots;
    
- include patterns;
    
- exclude patterns;
    
- maximum file size;
    
- supported file types;
    
- metadata-only paths;
    
- content-analysis paths.
    

Preserve:

- file path relative to connector root;
    
- create time where available;
    
- modify time;
    
- content hash;
    
- MIME/type;
    
- source connector.
    

Filesystem modification events may support project-episode analysis.

They do not establish semantic project meaning without further evidence.

# 11. Retention policy architecture

Create RetentionPolicy.

Minimum fields:

- `id`
    
- `profile_id`
    
- `name`
    
- `scope`
    
- `connector_id`
    
- `data_class`
    
- `minimum_age`
    
- `decision_threshold`
    
- `action`
    
- `schedule`
    
- `enabled`
    
- `grace_period`
    
- `configuration`
    

Actions:

```text
local_purge
source_delete
controller_erasure_candidate
review_only
```

Do not combine these actions.

# 12. Create RetentionDecision

Retention decisions are independent of personal-interest inference.

Classification:

```text
KEEP_LEGAL_OR_REGULATORY
KEEP_FINANCIAL
KEEP_IDENTITY_OR_SECURITY
KEEP_PROJECT_RECORD
KEEP_ACTIVE_CONVERSATION
KEEP_PERSONAL_SIGNIFICANCE
LOW_VALUE_BULK
SPAM
UNSURE
```

Every decision stores:

- source item;
    
- classification;
    
- deterministic evidence;
    
- semantic adjudication where used;
    
- confidence;
    
- policy;
    
- analysis run;
    
- review status.
    

`UNSURE` is a valid output.

Default action for `UNSURE` is keep/review.

# 13. Build conservative email-retention detector

Deterministic keep signals should include where supported:

- user starred/flagged;
    
- explicit keep label;
    
- user sent or replied;
    
- active multi-message thread;
    
- attachment;
    
- invoice/receipt candidate;
    
- contract/legal candidate;
    
- education candidate;
    
- employment candidate;
    
- banking/payment candidate;
    
- identity/security candidate;
    
- travel-booking candidate;
    
- calendar/event linkage;
    
- known human correspondent;
    
- currently active project linkage.
    

Low-value candidate evidence may include:

- bulk/newsletter candidate;
    
- repeated template;
    
- no user reply;
    
- no observed link engagement;
    
- long inactivity period;
    
- no attachment;
    
- no project/legal/financial/security relationship.
    

The semantic model receives only unresolved candidates.

Do not feed the entire mailbox to a general model for classification.

# 14. Add deletion planning and dry run

A scheduled retention policy first creates:

```text
DeletionPlan
```

Example:

```text
Policy:
Low-value bulk mail older than 6 months

Eligible:
1,842

Protected:
61

Uncertain:
37

Estimated source deletion:
1,744
```

The plan must show why items were protected or uncertain.

Initial default:

```text
dry_run = true
```

# 15. Add staged deletion

Where source capabilities support it:

```text
candidate
 ↓
review
 ↓
quarantine / temporary label where available
 ↓
grace period
 ↓
source delete
 ↓
verification
```

Do not immediately permanently destroy uncertain email.

Where a provider offers Trash semantics, prefer moving to Trash over irreversible deletion for the first supported implementation.

Record source response IDs/status.

# 16. Local purge

Local deletion is separate.

Before local purge determine:

- whether source evidence is referenced by accepted Assertions;
    
- whether source evidence is required to explain a historical insight;
    
- whether a redacted/minimised evidence representation can preserve provenance.
    

Do not silently break EvidenceLocators.

If full content is purged but a permitted evidence excerpt/hash is retained, record:

```text
content_purged_at
retained_evidence_basis
```

The UI must show that full source content is no longer available.

# 17. Controller erasure candidate

Retention policies may create:

```text
ControllerErasureCandidate
```

They must not send a GDPR deletion request automatically unless the user has explicitly enabled that workflow and the relevant request is reviewed according to configuration.

This integrates with the existing request system.

Do not create a separate GDPR request product.

# 18. Connector controls in Settings

Under:

```text
Settings → Connectors
```

display cards:

```text
Chrome History
Connected
Live
Last event: 14 seconds ago

Email
Connected
Incremental IMAP
Last sync: 2 minutes ago

Photo Library
Paused
Metadata only
12,481 files catalogued
```

Actions:

```text
Configure
Pause
Sync now
Backfill
View data classes
Disconnect
```

Under:

```text
Settings → Data Retention
```

display policies.

Example:

```text
Low-value bulk email

Scope:
Email connector

Age:
6 months

Action:
Move to Trash

Mode:
Dry run

Next review:
1 August
```

# 19. Connector privacy controls

Every connector must show its permissions.

Example:

```text
Chrome History

READ:
visited URL
visit time
transition type

NOT READ:
page body
form content
passwords
downloads
```

The user must be able to understand the acquisition boundary.

Connector configuration changes are audited.

# 20. Tests

Required synthetic scenarios:

1. browser initial backfill;
    
2. browser `onVisited` incremental event;
    
3. duplicate browser visit ingestion;
    
4. connector reconnect with unsent local queue;
    
5. email received newsletter;
    
6. recurring newsletter with no engagement;
    
7. newsletter with repeated clicked links;
    
8. user-replied human email;
    
9. invoice attachment;
    
10. active university correspondence;
    
11. low-value bulk email older than 6 months;
    
12. uncertain email;
    
13. retention dry run;
    
14. protected email excluded from deletion plan;
    
15. uncertain email excluded from automatic deletion;
    
16. staged move-to-Trash flow;
    
17. local purge cannot break accepted evidence silently;
    
18. AI export distinguishes user and assistant turns;
    
19. assistant-generated AI text does not create direct user-interest evidence;
    
20. photo connector metadata-only mode makes no visual model calls;
    
21. connector pause stops acquisition without deleting historical data;
    
22. disconnect does not silently erase source evidence;
    
23. controller erasure candidate routes into existing request workflow.
    

At completion report:

1. SourceConnector architecture;
    
2. connector implementations;
    
3. browser bridge;
    
4. email source/transport split;
    
5. AI conversation ingestion;
    
6. photo/filesystem connectors;
    
7. retention model;
    
8. email-importance logic;
    
9. deletion staging;
    
10. connector Settings UI;
    
11. tests and exact results;
    
12. unsupported provider/source-deletion capabilities.
    

Do not weaken evidence provenance to simplify source deletion.

The core conceptual rule I would now write at the top of the project is:

```text
THE SYSTEM MUST DISTINGUISH:

what reached me
what I looked at
what I actively investigated
what I created
what I implemented
what I said about myself
what my behaviour evidenced
what a controller assigned to me
what the system hypothesised
```

Because honestly, **that distinction is the thing that stops Personal Insights becoming the exact kind of crude profiling system the project is criticising**.

A compressed token-saving Codex version of these three briefs is possible without changing the architecture.