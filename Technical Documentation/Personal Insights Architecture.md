---
title: Personal Insights Architecture
date: 2026-07-13
tags:
  - gdpr-agent
  - personal-insights
  - architecture
status: delivered
---

# Personal Insights Architecture

Personal Insights is a local-first, longitudinal projection of the subject's evidence. It answers how observed activity, interests, investigations, projects, routines, places and engagement changed through time. It does not create a mutable profile of what the person “is,” and model-generated interpretation is never presented as psychological fact.

## Canonical evidence and derivation boundary

PostgreSQL remains the canonical ledger for source artefacts, locators, assertions, analysis runs and derived records. High-volume `ActivityEvent` rows remain in immutable Parquet partitions rather than being copied individually into Neo4j. The insight service combines those occurrence records with accepted assertions and versioned Task 3 temporal states, topic assignments, project episodes and eras.

Every surfaced item carries an `InsightEvidenceRef`. The evidence index connects the derived insight to supporting ActivityEvents, Assertions, SourceArtifacts and EvidenceLocators. `GET /insights/evidence/{id}` resolves that index into an `InsightTrace` with the detector and version, analysis run, calculation window, calculated features, source counts and source locators. A model explanation, when present, is a separately labelled explanation; it is not promoted into the evidence list.

Derived data is append-only. Migrations 017 through 020 define versioned materialisations, aggregate buckets, a materialisation-scoped evidence index, an immutable per-insight catalogue, contextual candidates and media-location candidates, then reject update/delete operations on immutable derived records. Recalculation creates a new derivation result. `insight_settings` is the intentional mutable configuration boundary. There is no editable `current_interest` truth table or column.

## Occurrence-time semantics

All temporal selection is based on `occurred_at`, including historical material imported years later. Ingestion or import time records when the system learned about evidence; it does not move the activity into that later period.

The page owns one `InsightPeriod` selection:

- point-in-time: a bounded view around one selected point;
- period: an inclusive start and exclusive end window;
- compare: one current period plus one explicit baseline period.

The same serialized selection drives overview, interests, search, AI conversations, places, changes and context. Granularity controls day, week, month, quarter or year aggregate buckets; it does not change the evidence clock.

## Materialisation and cache

`InsightRepository` discovers only canonical `activity-event-v1` partitions that overlap the requested occurrence-time window. `PeriodMaterializer` scans each cold selection once, builds density buckets and its evidence index together, and persists an immutable snapshot. Cards consume that shared snapshot rather than reopening Parquet independently.

The deterministic cache identity includes subject, temporal mode, current and comparison windows, granularity, derivation version, overlapping partition hashes and dependency tokens for accepted assertions, temporal states, topics, episodes, eras, media candidates and external context. A changed dependency produces a new cache identity. When only some source partitions change, unaffected aggregate buckets are copied into the new immutable materialisation and affected buckets are selectively recomputed. An unchanged warm request returns the persisted payload without another Parquet scan. An independent cold materialisation over identical immutable inputs reproduces the same cache key, insight identifier and payload.

## Exposure and behavioural evidence

Signals use an ordered hierarchy:

`AMBIENT_EXPOSURE → PASSIVE_CONSUMPTION → ACTIVE_INVESTIGATION → CREATION → IMPLEMENTATION → COMMUNICATION`

Disengagement and unknown signals remain separate. A received newsletter and assistant-generated AI turn are exposure by default and do not contribute to an observed interest. Reliable opening is weak passive evidence; a click is active investigation; a reply is communication; unsubscribe is disengagement. A user-authored AI prompt is behavioural evidence, but assistant text is not weighted as if the user authored it. A single curiosity search remains a weak one-off; recurrence, refinement, cross-source investigation, return after dormancy, creation and implementation can support stronger states.

The Interest Atlas presents intensity, persistence, recurrence, breadth, novelty and context dispersion separately. Any composite is secondary and never becomes a generic editable truth score.

## Conservative contextual correlations

Context processing begins with a detected local change, opens a bounded time window, retrieves relevant `ExternalContextEvent` records, and calculates a `TemporalCorrelationCandidate`. It never starts from world events and hunts through personal history for coincidences.

Statuses are deliberately constrained:

- `coincidence_candidate`;
- `possible_relation`;
- `evidence_supported_relation`;
- `user_confirmed`;
- `rejected`.

Temporal proximity alone cannot strengthen a relation. Relevant searches, article visits, user-authored AI discussion, email engagement or authored messages must precede the change to count as exposure evidence. Persistence and competing explanations remain visible features. The engine never emits `caused_by` automatically, including after user confirmation; a causal claim requires the normal human-confirmed Assertion path.

External-context import is separate from personal-data ingestion. Context sources receive no personal behaviour or derived profile data.

## Media origin and location safeguards

Media analysis defaults to `metadata_only`. Deterministic EXIF, filename, path, dimensions, camera/device, editing-software, screenshot and download hints classify `camera_origin`, `screenshot`, `downloaded_media`, `edited_media`, `generated_media` or `unknown`. Ambiguous visual work is optional and is expressed as Task Router requests under the active privacy mode; planning those requests makes no provider or network call.

Location evidence preserves both basis and class:

- credible camera-origin GPS plus original capture time may be a strong observation;
- a Takeout sidecar remains tied to its artefact and locator;
- a visual landmark without GPS is a candidate until review;
- a screenshot or downloaded image remains content exposure, even if it contains GPS or a recognisable place;
- user confirmation is explicit and attributable.

Candidate and strong/confirmed markers remain visually distinct. The system does not infer “home” from an overnight cluster.

## API and UI

The Python service exposes `/insights/overview`, `/interests`, `/search`, `/ai-conversations`, `/places`, `/changes`, `/context` and `/evidence/{id}`. Next.js proxies these under `/api/insights`. Period endpoints share `subject_id`, `mode`, `from`, `to`, `point`, `compareFrom`, `compareTo` and `granularity`.

`/dashboard/insights` renders the period overview and engagement profile, Interest Atlas, search and AI modules, changes/projects/eras, places and movement, contextual correlations, and an evidence inspector. The modules calculate no replacement analytics in the browser. “Why am I seeing this?” opens the evidence trace, with any model explanation kept visually separate.

The URL is the shareable selection contract. The page memoizes the URL-derived point/period/compare defaults so an absent timestamp does not generate a new selection and refetch loop on every render. Mode and granularity controls update the URL as one coherent transaction and remain available after navigation.

Temporal controls, activity-density surfaces, headers and empty/error/loading states use shared theme tokens. Authenticated dark-mode verification measured the temporal and density surfaces at background `rgb(2, 8, 23)`, border `rgb(30, 41, 59)`, and text `rgb(248, 250, 252)`.

The user's authenticated profile had no event partitions and correctly showed empty states. A separate local `task4-browser-smoke` subject supplied one synthetic temporal state for a non-destructive drawer check: the visible evidence action opened the inspector, displayed detector `task4.signal-hierarchy v2.0.0`, the temporal state and source counts, and exposed no raw user content. That focused browser fixture had zero source artefacts and zero exact locators; database-backed fixtures remain the verification authority for broader catalogue/index selection, trace construction and exact locator resolution.

## Privacy boundary

Default period analysis, aggregate materialisation, correlation calculation, evidence tracing and metadata-only media analysis run locally over already-ingested evidence. Optional OCR, caption, landmark or origin-specialist work goes only through the Task 2 execution router. `strict_local` forbids external routing; the metadata default schedules no visual task and performs zero external calls. Personal behavioural data is never sent to external context-event sources.

Related: [[Task 4 Implementation Ledger]], [[Task 4 Acceptance Audit]].
