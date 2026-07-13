# Workflow Architecture and Inventory

`frontend/lib/workflows/registry.ts` is the canonical `WorkflowDefinition` registry. `workflow_preferences` stores execution mode per workflow (`built_in`, `n8n`, `hybrid`, or `disabled`), configuration, fallback order, and schedule. The old global backend is used only once by migration 010 to initialise per-workflow rows.

N8N is an optional adapter. Its webhook settings derive from the same canonical mapping used by the runtime and API; the Next.js service no longer depends on N8N starting.

| Workflow | Exported N8N implementation | Built-in handler | Current callers | Parity |
|---|---|---|---|---|
| Policy acquisition | 01, 13 | policy acquisition route | new-request flow | Built in |
| Policy analysis | 01, 13 | policy task route | new-request flow | Built in |
| Request drafting | 02 | request.drafting task | request submission | Built in |
| Email sending | 03a | authenticated SMTP transport | request submission | Built in |
| IMAP test | runtime webhook | TLS IMAP connector | settings | Built in |
| Inbox monitoring | 03b | incremental unseen search/match | monitor endpoint, post-send prime | Built in |
| Response classification | 03b | email.classification task | inbox monitor | Built in |
| Attachment/download detection | 03b/04 | response classification/detector | inbox monitor | Built in |
| Response parsing | 04 | upload processor | upload APIs | Built in |
| File ingestion | 04/05 | Python `/ingest` + evidence ledger | upload scan | Built in |
| Identity ingestion | 08 | graph identity API → evidence assertions | graph identity API | Built in |
| Grounded extraction | 04/05 | Python `/extract` | upload processing | Built in |
| Graph projection | 05 | `GraphProjectionService` | evidence APIs/worker | Built in |
| Graph query/hybrid retrieval | 09/10/14 | Python `/query` and frontend grounded query | graph chat/RLM | Built in |
| Transcription | 11 | Python local ASR adapters | upload processor | Built in |
| Vendor OCR | 12 | local OCR + semantic adjudication routes | ONSIT extraction | Built in |
| Privacy-policy scanning | 13 | policy acquisition/analysis routes | policy API | Built in |
| MAKGED validation | 07 | Python `/validate` | evidence/graph flows | Built in |

The built-in inbox monitor stores its checkpoint, matches controller addresses against active requests, records response events, invokes the configured classification task, and marks processed mail seen. Full connector ingestion and retention policy semantics remain reserved for Task 5.
