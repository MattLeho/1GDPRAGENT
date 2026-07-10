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