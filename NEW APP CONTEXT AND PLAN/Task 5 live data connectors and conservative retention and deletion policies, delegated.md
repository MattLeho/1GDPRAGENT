# Task 5 — Live data connectors and conservative retention/deletion policies

Continue work in `MattLeho/1GDPRAGENT`.

This task assumes Tasks 1–4 and Task 3A are implemented.

The application already has an evidence pipeline, ActivityEvent lake, Task Execution Router and Personal Insights semantics distinguishing exposure from engagement.

# Primary objective

Create a general Data Connector architecture and a conservative retention/deletion policy system.

GDPR/DSAR is one acquisition mechanism.

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
SourceArtifact / EvidenceLocator / ActivityEvent
        ↓
same provenance and analysis pipeline
```

No connector directly writes semantic truth to Neo4j.

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

# Wave 0 — Connector and deletion-safety contract freeze

**Owner: orchestrator**

Freeze:

```text
SourceConnectorDefinition
ConnectorInstance
ConnectorSyncRun
ConnectorCursor
ConnectorRawRecord
ConnectorPermission
EmailTransport
RetentionPolicy
RetentionDecision
DeletionPlan
DeletionPlanItem
SourceDeletionExecution
LocalPurgeExecution
ControllerErasureCandidate
```

Connector modes:

```text
snapshot_import
incremental_poll
event_stream
webhook_push
folder_watch
```

Connector status:

```text
connected
paused
degraded
authentication_required
error
disconnected
```

Retention actions remain separate:

```text
local_purge
source_delete
controller_erasure_candidate
review_only
```

The orchestrator owns migrations, encrypted connector configuration, credential access boundaries and all destructive-operation semantics.

Default safety rules:

- dry run first;
- UNSURE = keep/review;
- no automatic controller erasure request unless explicitly enabled;
- no interest score decides deletion;
- local purge cannot silently break accepted evidence;
- source deletion capability must be declared by connector and verified;
- no connector may exceed displayed permissions.

# Wave 1 — General connector runtime

## Sub-agent 5.1A — Connector registry and sync-run runtime

**Recommended: Terra-Medium**

Implement registry/dispatch behind frozen contracts.

Every connector declares:

- key;
- display name;
- provider;
- type;
- modes;
- data classes;
- permissions;
- backfill support;
- incremental support;
- source-delete support;
- remote-delete-request support;
- configuration schema.

Implement ConnectorSyncRun metrics:

- cursor before/after;
- artefacts discovered;
- events produced;
- duplicates skipped;
- errors;
- start/end.

Do not implement connector-specific credentials.

## Sub-agent 5.1B — Connector raw-record ingestion bridge

**Recommended: Terra-Medium**

Implement:

```text
connector raw record
 ↓
SourceArtifact / typed source record
 ↓
EvidenceLocator
 ↓
ActivityEvent/parser pipeline
```

The bridge preserves raw source semantics and routes into Task 3.

A browser visit does not create INTERESTED_IN.

An email does not create IMPORTANT_EMAIL.

Add idempotent connector-record signatures.

## Sub-agent 5.1C — Scheduling, pause/resume and health

**Recommended: Terra-Medium**

Implement generic:

- sync now;
- backfill;
- pause;
- resume;
- retry/backoff;
- degraded status;
- authentication-required status;
- last/next sync;
- connector health.

Reuse Task 2 workflow/task scheduling architecture rather than inventing a second scheduler.

**Wave 1 gate:** a synthetic connector can backfill, resume from a cursor, pause, reconnect, deduplicate and emit source records through the normal evidence pipeline.

# Wave 2 — Browser Connector MVP

This is a separate package/isolated directory.

## Sub-agent 5.2A — Chromium extension

**Recommended: Terra-Medium**

Implement explicit history permission and:

- initial history backfill;
- incremental visit capture;
- local queue;
- acknowledgement;
- reconnect;
- deterministic visit signatures.

Preserve where available:

- URL;
- visit timestamp;
- transition type;
- referring visit ID;
- local/synchronised origin indicator;
- browser profile connector ID.

Do not capture page body by default.

## Sub-agent 5.2B — Native/local bridge

**Recommended: Terra-Medium**

Implement local bridge protocol between extension and GDPR Agent connector service.

Requirements:

- no required cloud relay;
- framed/versioned messages;
- local authentication/token pairing;
- acknowledgement;
- replay protection/idempotency;
- bounded queue;
- health/status;
- clear installation documentation.

Security/integration review remains with orchestrator.

## 2.3 Optional page-content policy

**Owner: orchestrator**

Content capture remains OFF by default.

If framework support is included, it must be rule-scoped and explicitly approved.

Never capture:

- password fields;
- payment forms;
- private content merely because technically accessible.

Any later page-content capture creates separate SourceArtifacts and permissions.

**Wave 2 gate:** browser history backfill and incremental visits arrive locally and do not directly create interests.

# Wave 3 — Email source connector and transport split

## 3.1 Credential and permission boundary

**Owner: orchestrator**

Reuse Task 2 server-side encrypted credentials.

Separate:

```text
EMAIL SOURCE CONNECTOR
read/synchronise authorised mailbox

EMAIL TRANSPORT
send GDPR requests and replies
```

No browser-accessible decrypted secrets.

## Sub-agent 5.3A — Built-in IMAP source connector

**Recommended: Terra-Medium**

Implement incremental IMAP sync.

Persist stable provider/message identifiers where available.

Preserve:

- mailbox/folder;
- message ID;
- thread/reference information;
- sender;
- recipients;
- timestamp;
- subject;
- relevant headers;
- attachment metadata;
- body according to scope.

Scopes:

```text
metadata_only
headers_and_subject
text_body
full_message
```

Attachments follow separate ingestion policy and Task 3A adapters.

Only create source events supported by evidence.

## Sub-agent 5.3B — Email transport integration

**Recommended: Terra-Medium**

Integrate built-in SMTP/provider transport with Task 2 workflow registry.

Support draft/review/send/record message metadata.

Do not couple mailbox ingestion to N8N.

N8N remains an optional per-workflow adapter.

## Sub-agent 5.3C — Email event semantics

**Recommended: Terra-Medium**

Create only evidence-supported:

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

Do not invent EMAIL_OPENED if connector evidence is unavailable.

## Sub-agent 5.3D — Bulk/newsletter candidate detector

**Recommended: Terra-Medium**

Use deterministic signals:

- List-Unsubscribe;
- List-Id;
- bulk precedence;
- no-reply;
- repeated sender/template/subject;
- frequency;
- many recipients where visible;
- low reply rate.

Produce:

```text
BulkMailCandidate
NewsletterCandidate
```

Not automatic SPAM.

## Sub-agent 5.3E — Email engagement semantics

**Recommended: Terra-Medium**

Enforce:

```text
EMAIL_RECEIVED         → topic exposure
EMAIL_OPENED_CANDIDATE → weak passive candidate
EMAIL_LINK_CLICKED     → active engagement
EMAIL_REPLIED          → communication
EMAIL_UNSUBSCRIBED     → disengagement action
```

Repeated delivery without engagement does not sustain ObservedInterestState.

Implement engagement decay as weakened current observed engagement, not “disinterest”.

**Wave 3 gate:** built-in email sync and transport operate without N8N and Personal Insights receives correct exposure/engagement semantics.

# Wave 4 — AI conversation, photo and filesystem connectors

## Sub-agent 5.4A — AI conversation snapshot/import connectors

**Recommended: Terra-Medium**

Initial priority is export/snapshot parsers through Task 3 fingerprints and approved parser specs.

Preserve:

```text
conversation
turn
speaker role
timestamp
service
model where known
title
source locator
```

Roles:

```text
user
assistant
system
tool
unknown
```

Only user-authored turns contribute direct behavioural-query signals by default.

Do not use brittle authenticated scraping as the default.

## Sub-agent 5.4B — Photo/media folder connector

**Recommended: Terra-Medium**

User-selected roots only.

Modes:

```text
metadata_only
selected_visual_analysis
full_visual_analysis
```

Default metadata_only.

Detect new/modified/removed.

Use content hashes.

Removal from folder creates a source observation; it does not erase historical evidence.

Route files through Task 3A.

## Sub-agent 5.4C — Generic filesystem connector

**Recommended: Terra-Medium**

User-selected roots only.

Configuration:

- roots;
- include/exclude;
- max size;
- supported types;
- metadata-only paths;
- content-analysis paths.

Preserve relative path, create/modify time where available, hash, MIME/type and connector.

File modification may support project episodes but does not establish semantic project meaning.

## Sub-agent 5.4D — Connector-specific parser fixtures

**Recommended: Terra-Medium**

Create representative fixtures for known AI export formats, photo sidecars and filesystem events.

Use Task 3 parser registry rather than hardcoded model prompts.

**Wave 4 gate:** connector imports produce the same canonical evidence/events as snapshot imports and do not create a parallel truth model.

# Wave 5 — Retention decision engine

## 5.1 Retention epistemic/safety rules

**Owner: orchestrator**

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

UNSURE defaults to keep/review.

## Sub-agent 5.5A — Deterministic email-retention feature extractor

**Recommended: Terra-Medium**

Keep signals where supported:

- starred/flagged;
- explicit keep label;
- user sent/replied;
- active multi-message thread;
- attachment;
- invoice/receipt;
- contract/legal;
- education;
- employment;
- banking/payment;
- identity/security;
- travel booking;
- calendar/event linkage;
- known human correspondent;
- active project linkage.

Low-value candidate evidence:

- bulk/newsletter candidate;
- repeated template;
- no reply;
- no observed link engagement;
- long inactivity;
- no attachment;
- no project/legal/financial/security relationship.

The semantic task receives only unresolved candidates.

Do not feed the entire mailbox to a general model.

## Sub-agent 5.5B — Retention adjudication bundles

**Recommended: Terra-Medium**

Build minimal, privacy-mode-aware `email.retention_adjudication` bundles for unresolved candidates.

Require structured output and abstention.

Model result is one input to RetentionDecision, not direct deletion.

## Sub-agent 5.5C — Retention policy evaluator

**Recommended: Terra-Medium**

Implement policy matching by:

- profile;
- scope;
- connector;
- data class;
- minimum age;
- threshold;
- action;
- schedule;
- grace period;
- configuration.

Generate RetentionDecisions idempotently by policy/version/run.

**Wave 5 gate:** synthetic important/low-value/uncertain mail classes behave conservatively and interest strength never controls retention.

# Wave 6 — Deletion planning, staging and verification

**Destructive semantics remain orchestrator-owned.**

## Sub-agent 5.6A — DeletionPlan builder

**Recommended: Terra-Medium**

Build dry-run plans.

Example:

```text
Policy: Low-value bulk mail older than 6 months

Eligible: 1,842
Protected: 61
Uncertain: 37
Estimated source deletion: 1,744
```

Explain protected/uncertain reasons.

Default `dry_run = true`.

No deletion execution in this module.

## Sub-agent 5.6B — Quarantine/grace-period workflow

**Recommended: Terra-Medium**

Implement provider-neutral staged state machine:

```text
candidate
 ↓
review
 ↓
quarantine / temporary label where supported
 ↓
grace period
 ↓
eligible_for_delete
```

Connector-specific action executes later.

## 6.3 Source deletion execution

**Owner: orchestrator**

Only a connector declaring tested `supports_source_delete` may execute.

Prefer Trash semantics where provider supports it for the initial implementation.

Record source response IDs/status and execution audit.

No automatic permanent destruction of UNSURE.

## 6.4 Local purge

**Owner: orchestrator**

Before local purge determine:

- accepted Assertion references;
- historical insight evidence references;
- whether minimised/redacted evidence can preserve provenance.

Never silently break EvidenceLocators.

Where full content is purged but permitted evidence remains, record:

```text
content_purged_at
retained_evidence_basis
```

UI must show full source content is unavailable.

## Sub-agent 5.6C — ControllerErasureCandidate integration

**Recommended: Terra-Medium**

Create candidates that route into the existing GDPR request system.

Do not create a second request product.

Do not send automatically unless the existing workflow configuration explicitly enables reviewed automatic execution.

**Wave 6 gate:** deletion planning, staging, source delete, local purge and controller erasure are distinct and auditable.

# Wave 7 — Settings UI and connector controls

The orchestrator freezes API DTOs before UI delegation.

## Sub-agent 5.7A — Connector Settings page

**Recommended: Terra-Medium**

Under `Settings → Connectors`, show:

- status;
- permissions;
- last sync;
- next sync;
- data classes;
- pause;
- sync now;
- backfill;
- configure;
- disconnect.

Example:

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

## Sub-agent 5.7B — Connector permission inspector

**Recommended: Terra-Medium**

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

Configuration changes are audited.

## Sub-agent 5.7C — Data Retention settings

**Recommended: Terra-Medium**

Display policy scope, age, action, dry-run state, next review and latest plan summary.

Provide review-first flows.

Never hide UNSURE items in an aggregate.

## Sub-agent 5.7D — Deletion-plan review UI

**Recommended: Terra-Medium**

Display eligible/protected/uncertain groups with reasons and evidence.

Destructive confirmation invokes orchestrator-owned APIs.

**Wave 7 gate:** Settings accurately reflects connector permissions and deletion safety states.

# Wave 8 — Acceptance tests

## Sub-agent 5.8A — Connector synthetic test suite

**Recommended: Terra-Medium**

Implement:

1. browser initial backfill;
2. browser incremental visit;
3. duplicate visit;
4. reconnect with local queue;
5. connector pause;
6. disconnect without evidence erasure;
7. email newsletter receipt;
8. recurring newsletter no engagement;
9. newsletter link engagement;
10. replied human email;
11. AI export role separation;
12. photo metadata-only makes no visual calls;
13. filesystem scoped roots.

## Sub-agent 5.8B — Retention/deletion synthetic suite

**Recommended: Terra-Medium**

Implement:

1. invoice attachment;
2. active university correspondence;
3. low-value bulk older than 6 months;
4. uncertain email;
5. dry run;
6. protected excluded;
7. uncertain excluded from auto-delete;
8. move-to-Trash staged flow;
9. local purge cannot silently break evidence;
10. controller erasure candidate routes to request workflow.

## 8.3 Orchestrator final audit

Required assertions:

- connector direct graph writes do not exist;
- browser connector does not create interests;
- email receipt is exposure only;
- assistant AI turns do not create direct user-interest evidence;
- credentials remain server-side encrypted;
- built-in email operation does not require N8N;
- UNSURE never auto-deletes;
- retention does not use interest score as importance;
- local purge does not silently break provenance;
- source delete only runs through tested connector capability;
- disconnect/pause does not erase historical evidence.

At completion report:

1. delegation map;
2. SourceConnector architecture;
3. connector implementations;
4. browser bridge;
5. email source/transport split;
6. AI conversation/photo/filesystem connectors;
7. retention model;
8. email-importance logic;
9. deletion staging;
10. connector/retention Settings UI;
11. exact tests/results;
12. unsupported source-delete/provider capabilities;
13. every incomplete requirement.

Do not begin Task 6.
