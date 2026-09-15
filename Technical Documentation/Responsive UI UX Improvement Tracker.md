# Responsive UI/UX Improvement Tracker

Updated: 2026-09-14

## Purpose

This is the living implementation tracker for the responsive product pass. It links each visible component to the user task it supports, the behavior it must provide, known defects, responsive acceptance, and verification evidence. Update the relevant row whenever behavior or acceptance evidence changes.

Physical screen size is not available to a web application. Acceptance therefore uses CSS viewport width, browser zoom, input method, and available container width as the reliable proxies for a 13-inch laptop, split-screen use, tablets, phones, and large desktop displays.

## Primary user journeys

1. **Find and act on a controller or broker:** search existing requests, scan for broker exposure, review truthful findings, select a company, and create a request with explicit confirmation.
2. **Create and track a request:** create a guided or manual request, see it immediately in the list, inspect its evidence and deadline, record communication, and import the response.
3. **Understand personal data:** import data, inspect graph and Personal Insights views, change the time period, and trace every derived claim to evidence.
4. **Configure automation safely:** connect an inbox/provider, configure an agent schedule, run it deliberately, and see persisted run status and errors.
5. **Operate on any supported viewport:** complete the same task without horizontal page overflow, clipped controls, inaccessible dialogs, or hidden primary actions.

## Responsive acceptance matrix

| Viewport / mode | Required behavior |
|---|---|
| 320–375px phone | Single-column flow; no page-level horizontal overflow; controls have visible labels and approximately 44px touch targets; dialogs use available width. |
| 768px tablet | Mobile navigation remains available; page actions and filters reflow before content becomes cramped. |
| 1024px or 200% zoom | No fixed desktop sidebar consuming the working area; primary tasks remain keyboard accessible and vertically reflow. |
| 1280–1366px laptop | Sidebar and content coexist without clipping; headings and controls use compact typography/spacing; all request actions remain visible. |
| 1920px+ desktop | Content has readable maximum widths; body text and controls do not become unnecessarily oversized; dense workflows can use multiple columns. |
| 400% zoom | Core navigation and task completion remain possible through vertical reflow without two-dimensional scrolling. |

## Component and flow tracker

Status values: `verified`, `implemented-needs-browser`, `in-progress`, `backlog`, `blocked`, `truthfulness-defect`.

| ID | Component / route | User task and intended behavior | Responsive / UX contract | Status | Evidence / next action |
|---|---|---|---|---|---|
| SHELL-001 | `components/layout/DashboardLayout.tsx` | Navigate between core workflows and access profile/theme/notifications. | Mobile menu below `lg`; fixed sidebar only when adequate width exists; main content always `min-w-0`; compact padding before `xl`. | implemented-needs-browser | Breakpoint moved from `md` to `lg`; validate 375/768/1024/1366. |
| SHELL-002 | Global typography in `app/globals.css` | Read and operate comfortably across compact laptop and large desktop layouts. | Fluid root scale from 14–16px; display headings still use component breakpoints; never reduce accessibility below 14px. | implemented-needs-browser | Validate zoom and browser font settings. |
| REQ-001 | Access Requests header/actions | Search, scan, manually add, or start a guided request without losing an action off-screen. | Stack on compact widths, three equal actions at `sm`, inline actions at `xl`. | implemented-needs-browser | Source updated; live breakpoint matrix pending. |
| REQ-002 | `SearchToolbar.tsx` | Search companies/brokers, filter state, and sort results. | Search gets a full row below `xl`; filters get equal columns; no fixed-width overflow; clear button accessible. | implemented-needs-browser | Reflow, URL Back/Forward sync, `replace`-based typing, search-focus handoff, and clear-button label implemented. |
| REQ-003 | `AddManualRequestDialog.tsx` + `RequestsGrid.tsx` | After successful creation, see and focus the new request immediately. | Dialog fits viewport; list updates without manual reload. | implemented-needs-browser | Dialog now refreshes the route after success; verify the new card appears and receives focus. |
| REQ-004 | Request detail modal/direct route | Inspect evidence, messages, events, and actions on any viewport. | Full-width stacked panels below `lg`; tabs scroll or condense; no `100vw - 256px` mobile sizing. | implemented-needs-browser | Request cards now expose the owned deep-link page as the canonical record and retain a labelled quick workspace for chat/policy/files. The modal links back to the full record; the unsafe unused sheet remains deleted. Full client-body reuse and live owned/foreign request checks remain. |
| REQ-006 | Request detail policy scan | Scan a controller policy from an existing request and render a real analysis or explicit error. | Action remains usable in stacked modal; request body matches the server contract. | implemented-needs-browser | Corrected payload to `{url, company}` and added non-2xx handling; live request with a valid policy URL still required. |
| REQ-007 | Request chat | Send a message without displaying a failed submission as persisted. | Composer remains reachable; failed optimistic messages are rolled back and input restored. | implemented-needs-browser | Non-2xx and protected-request failures now roll back the optimistic message and restore the draft; the API no longer returns raw exception details. Live success/error proof remains. |
| REQ-005 | New Request wizard | Analyze deliberately, carry the selected identity and scope into a request, and distinguish creation/drafting/delivery. | Header/actions wrap; progress labels abbreviate; state survives Back/Next; sensitive details are encrypted server-side. | implemented-needs-browser | Policy analysis now runs only on explicit Analyze and passes public-URL validation. Real name/email/details reach submission and are encrypted server-side; graph linking is optional; scope/date choices persist across step navigation; UI says Create rather than promising delivery. Step 1 is live-verified at 467px; full step 2/3 submission with real data remains. |
| BROKER-001 | Access Requests “Scan for Brokers” → ONSIT Discovery | Reach the real discovery workflow directly from the request workflow instead of the simulated legacy scanner. | Button remains visible at every breakpoint and opens the authenticated discovery flow. | verified | Link rendered and remained visible at 1024px with no horizontal overflow. |
| BROKER-002 | `DatabrokerScanner.tsx` | Run a real profile-scoped broker scan and review persisted evidence before creating removal requests. | Clear queued/running/completed/failed state; no fabricated findings; usable cards/actions on mobile. | truthfulness-defect | Current implementation uses random simulated results and local-only state; replace with real job API before representing it as operational. |
| HOME-001 | Home summary and Quick Actions | Start common tasks and understand current workload. | Compact hero/KPI spacing on laptop; cards reflow; navigation handoff focuses intended control. | in-progress | QuickActions hydration classes normalized; responsive hero and `focus=search` behavior pending. |
| HOME-002 | `AgentManager.tsx` | Reach the contextual workflow needed for policy analysis, inbox configuration, graph review, broker discovery, or import. | Rows stack on phones; every action has a visible label and touch-sized target; no synthetic runtime status. | verified | Replaced five incompatible POST controls and local-only schedules/status with truthful workflow links. Live 467px check shows all five labels, no “All Idle” claim, and no horizontal overflow; 3/3 focused contracts pass. |
| INS-001 | Personal Insights selection/hydration | Open Insights without hydration warnings or route loss and see stable time controls. | Server and first client render share one time snapshot; local-time formatting occurs after mount; controls stack below `sm`. | implemented-needs-browser | Stable `initialNow`, mounted date localization, and responsive controls implemented; live no-warning proof pending. |
| INS-002 | Personal Insights module loading | See useful modules as they arrive and retry only failures. | Progressive per-module loading/error state; slow module cannot pin the visibility of completed modules. | implemented-needs-browser | Each module now commits independently; global refresh completes after all settle. Add per-module retry and bounded concurrency next. |
| GRAPH-001 | Graph workspace and inspector | Explore nodes and evidence without the inspector crushing the graph. | Inspector becomes a sheet/drawer below `xl`; controls reflow; compact viewport math matches shell padding. | implemented-needs-browser | Graph had no page overflow at 1024px; drawer node-selection behavior and canvas resize remain to verify. |
| SETTINGS-001 | Settings navigation/forms | Find a setting, understand state, edit it, and see validation/health. | Horizontal scrollable section navigation below wide desktop; vertical rail only with adequate width; labels/fields never clip. | in-progress | Navigation, card padding, retention grids/confirmation, ID upload/document rows, AI credential writes, and Source Connector forms are repaired. Privacy and the complete split-screen browser matrix remain. |
| ONSIT-001 | ONSIT discovery | Start a bounded discovery, monitor progress, and reuse service-bound findings. | Forms and progress stack; active task is encoded in the URL; durability boundary is visible. | implemented-needs-browser | A task URL now resumes polling/findings while Intelligence remains running, findings-load failure is visible, and raw backend errors are not returned. The page explicitly says scan history is not durable across service restart; database persistence remains backlog. |
| OVERLAY-001 | Dialog/sheet/popover primitives | Complete modal tasks by touch and keyboard without content leaving the viewport. | Safe viewport max width/height; internal scrolling; focus return; 44px close/actions. | backlog | Audit shared sheet/select/tabs and caller overrides. |
| A11Y-001 | Keyboard, focus, labels, status | Complete primary journeys without a pointer and understand async status. | Visible focus, named icon buttons, live regions, logical tab order, no color-only state. | in-progress | Search clear and identity-document icon actions named; notification and settings webhook keyboard/target audit remains. |
| IMPORT-001 | `ZipImporter.tsx` evidence ingestion | Upload an export once, record each persisted file through the canonical evidence pipeline, and understand what still requires review. | Progress and per-file errors remain readable; completion never claims unreviewed graph projection. | implemented-needs-browser | Removed duplicate PUT/stale-state path and nonexistent `result.content`; completion uses the local processed accumulator and returned run/artifact metadata. Two focused tests pass. |
| SETTINGS-002 | Task routes, processing policy, execution audit, and N8N configuration | Configure only the current profile's routes/secrets and never read or overwrite another profile's settings. | Responsive controls are secondary to server-enforced profile isolation. | implemented-needs-browser | Migration 034 adds fail-closed ownership and composite uniqueness; routes/router/N8N resolution use session profile authority; two-profile route contract is covered. Live signed-in cross-profile acceptance remains. |
| SETTINGS-003 | ONSIT API keys and legacy email credential | Store secrets without overstating provider availability; test only capabilities the configured card can actually perform. | Fields and actions stack on phones, have programmatic labels, visible status, and recover from thrown operations. | implemented-needs-browser | New ONSIT keys use authenticated AES-256-GCM in an atomic transaction and authoritative post-save presence; UI says stored-only because active workers do not consume them yet. Email card now promises only SMTP storage/IMAP testing, clears busy in `finally`, and directs monitoring to Source Connectors. Live 467px wording/layout verified; provider consumption remains backlog. |
| SETTINGS-004 | AI credentials and Source Connectors | Save provider secrets atomically and configure evidence sources with truthful validation, task identity, and health. | Inputs are labelled; actions are touch-sized; server-visible path requirements and async status are disclosed without clipping. | implemented-needs-browser | AI credential writes now use canonical AES-GCM in one transaction while retaining read-only legacy compatibility. Connectors reject incomplete/relative configuration, retain queued task IDs, display profile-scoped health, accept pairing from the live 3002 UI, and return stable proxy errors. The form and rejection state are live-verified at 363px; real create/sync/health remains. |
| ONSIT-002 | ONSIT API/UI contract | Show real progress and normalized findings from active providers, with bounded visible failure handling. | Progress is 0–100, findings have stable IDs/sources, and polling cannot fail silently forever. | implemented-needs-browser | Progress normalization, real service labels, Python finding-envelope normalization, required seed validation, and bounded visible poll failure are implemented. Persistence/resume remains under ONSIT-001. |
| REQ-008 | Policy analysis authority and acquisition | Acquire a public privacy policy safely and persist its analysis for the owning request/profile. | Scan remains usable in canonical detail UI; server blocks internal/private URL targets. | implemented-needs-browser | Public URL validation and redirect controls are implemented. Migration 035 is applied; all reads/writes are profile/request scoped, pre-request wizard analysis remains explicitly transient, and two-scope contracts pass. A signed-in scan against an existing request remains unverified because this profile currently has no requests. |

## Complete route and component inventory

Every active `frontend/app` page/layout and every TypeScript component under `frontend/components` is represented below. “Review” means the component has not yet passed the full breakpoint, keyboard, loading/error, and truthful-function acceptance matrix.

### Routes and layouts

| Surface | What it does | Current need / status |
|---|---|---|
| `app/layout.tsx` | Root providers, metadata, theme and notifications. | Review provider loading, font delivery, error boundary and hydration at all themes. |
| `app/page.tsx` | Authenticated root redirect. | Verify deterministic session-aware destination. |
| `app/login/page.tsx` | Username/password authentication and error reasons. | Review phone layout, password-manager/autofill, validation, loading and keyboard submission. |
| `app/dashboard/layout.tsx` | Applies the shared authenticated shell. | Covered by SHELL-001; verify mobile menu focus return. |
| `app/dashboard/home/page.tsx` | Workload summary and common task entry points. | Responsive hero implemented; remaining cards and truthful automation states under HOME-001/002. |
| `app/dashboard/requests/page.tsx` | Request search/list/create entry point. | 1024px reflow verified; phone/tablet and creation refresh still required. |
| `app/dashboard/requests/[id]/page.tsx` | Direct request detail route. | Invalid IDs now fail as 404 before UUID queries; review route consistency with modal/sheet and live owned/foreign request states. |
| `app/requests/new/page.tsx` | Guided three-step request creation. | Compact progress/header implemented; validate all wizard steps and persistence. |
| `app/dashboard/import/page.tsx` | ZIP evidence import and broker-discovery entry point. | Simulated scanner removed from the active page; live responsive verification remains. |
| `app/dashboard/graph/page.tsx` | Graph exploration workspace. | Responsive inspector/control implementation needs live node-selection proof. |
| `app/dashboard/insights/page.tsx` | Personal Insights server boundary and stable time seed. | Authority, rendering and 1024px overflow verified; partial/error behavior remains. |
| `app/dashboard/onsit/page.tsx` | Real asynchronous footprint discovery workflow. | Persist task/findings history, qualify provider claims, and test narrow forms. |
| `app/dashboard/settings/page.tsx` | Settings sections and navigation. | Responsive horizontal/vertical navigation implemented; every section needs field-level review. |

### Dashboard components

| Component | What it does | Current need / status |
|---|---|---|
| `dashboard/ActivityFeed.tsx` | Displays recent activity. | Review empty/error states, timestamp hydration and narrow row wrapping. |
| `dashboard/AgentManager.tsx` | Provides contextual workflow shortcuts. | Verified at 467px: all five labelled actions render without overflow; recurring automation remains configured only in its real workflow/settings surfaces. |
| `dashboard/ComplianceGauge.tsx` | Shows deadline/response evidence. | Review terminology, chart scaling and no-data semantics. |
| `dashboard/DatabrokerScanner.tsx` | Legacy simulated scanner, no longer mounted by an active page. | Delete after confirming no downstream import; do not restore without a persisted profile-scoped implementation. |
| `dashboard/DataVolumeChart.tsx` | Charts received data volume. | Fix zero/hidden-container chart dimension warning and test resize behavior. |
| `dashboard/FileProcessingCard.tsx` | Shows file processing state. | Review progress/error/retry and long filenames. |
| `dashboard/PrivacyScoreCard.tsx` | Shows request state counts. | Review no-data labels, click behavior and card wrapping. |
| `dashboard/QuickActions.tsx` | Links to four frequent tasks. | Hydration classes fixed; search-focus handoff implemented and needs browser proof. |
| `dashboard/RequestsTimeline.tsx` | Charts request activity over time. | Review responsive chart axes/tooltips and no-data dimensions. |
| `dashboard/ReviewDetailModal.tsx` | Shows a review item and actions. | Review viewport sizing, focus, destructive confirmation and action result refresh. |
| `dashboard/ReviewQueue.tsx` | Lists items requiring user review. | Review mobile card/table behavior and ownership of state updates. |
| `dashboard/StatsOverview.tsx` | Displays dashboard KPI cards. | Review compact grid, label wrapping and evidence definitions. |
| `dashboard/TaskWidget.tsx` | Lists ongoing request tasks. | Review empty state, deadline language and narrow table/card adaptation. |
| `dashboard/TopDataHolders.tsx` | Shows received artefacts grouped by company. | Review long company names, evidence links and zero state. |
| `dashboard/ZipImporter.tsx` | Uploads GDPR export archives into canonical reviewable evidence. | Duplicate processing and false graph claims repaired; review large-file cancellation, privacy disclosure, and mobile dropzone. |

### Request components

| Component | What it does | Current need / status |
|---|---|---|
| `requests/AddManualRequestDialog.tsx` | Creates externally initiated requests and optionally scans a policy. | Responsive fields and server refresh implemented; test immediate new-card appearance and sanitize policy rendering. |
| `requests/DataViewer.tsx` | Presents received/request data. | Review large payload virtualization, long values, download actions and mobile navigation. |
| `requests/RequestCard.tsx` | Summarizes one request with direct-record and quick-workspace actions. | Canonical link, labelled 40px quick-view/cancel controls and compact sizing implemented; live 320px card data remains. |
| `requests/RequestDetailModal.tsx` | Quick activity/evidence/request workspace. | Responsive stacked layout and evidence-backed deadline display implemented. Uploads now process sequentially using recorded server state; fake deletion, progress, graph claims and completion-triggered duplicate ingestion are removed. Extract its viable client body into the canonical route after live owned-request coverage. |
| `requests/RequestDetailSheet.tsx` | Retired alternate request detail. | Deleted: it called a nonexistent logs route and contained toast-only Complete/Export/Save actions plus broken chat submission. The responsive contract asserts it remains absent. |
| `requests/RequestsGrid.tsx` | Filters/sorts cards and opens details. | Confirm router refresh after manual creation; add broker-backed search only when data model supports it. |
| `requests/SearchToolbar.tsx` | Search, state filter and sort controls. | Reflow/focus/a11y implemented; test Back/Forward synchronization and debounce history. |

### Wizard components

| Component | What it does | Current need / status |
|---|---|---|
| `wizard/UrlAnalyzer.tsx` | Analyzes a controller/privacy-policy URL. | Review URL validation, provider failure, evidence disclosure and narrow action layout. |
| `wizard/IdentityBuilder.tsx` | Builds/selects request identity evidence. | Review sensitive-field clarity, document selection, validation and mobile grouping. |
| `wizard/IdentityMiniMap.tsx` | Visualizes selected identity/graph context. | Review small-container dimensions and non-visual equivalent. |
| `wizard/IdentitySelector.tsx` | Chooses identity attributes/documents. | Review keyboard selection, overflow and required/optional semantics. |
| `wizard/ScopeSelector.tsx` | Selects request scope and submits. | Review long scope labels, confirmation summary, double-submit prevention and success navigation. |

### Graph components

| Component | What it does | Current need / status |
|---|---|---|
| `graph/GraphCanvas.tsx` | Renders and interacts with the graph. | Test resize, touch/pinch, keyboard alternative, loading/error/empty states and performance limits. |
| `graph/GraphLegend.tsx` | Explains graph node/edge encodings. | Review responsive placement, scrolling and consistency with active modes. |
| `graph/GraphToolbar.tsx` | Search/filter/view controls for the graph. | Review narrow collapse, accessible names and state persistence. |
| `graph/InspectorPanel.tsx` | Shows evidence/details/actions for a selected node. | Drawer integration implemented below `lg`; verify all actions and long evidence. |
| `graph/PrivacyGraphControls.tsx` | Switches privacy modes and temporal/profile filters. | Responsive control grid implemented; add discoverable overflow affordance and timezone stability. |
| `graph/PrivacyModePanel.tsx` | Explains/currently summarizes graph mode. | Review drawer sizing, empty state and terminology. |
| `graph/ShadowProfileChat.tsx` | Conversational graph exploration. | Review provider/error/privacy states, mobile sheet behavior and citation grounding. |

### Personal Insights components

| Component | What it does | Current need / status |
|---|---|---|
| `insights/PersonalInsightsDashboard.tsx` | Composes all insight modules. | Stable hydration and heading scale implemented; add per-module retry/loading boundaries. |
| `insights/useInsightDashboard.ts` | Loads temporal module data and manages query state. | Progressive publishing implemented; add bounded concurrency and avoid redundant reloads. |
| `insights/TemporalControl.tsx` | Changes mode, granularity and date windows. | SSR-stable/localized inputs and responsive grid implemented; verify Compare at 320/1024. |
| `insights/ActivityDensityTimeline.tsx` | Charts event density. | Review chart resize, zero data, keyboard/text alternative and labels at narrow widths. |
| `insights/OverviewEngagement.tsx` | Shows period KPIs and engagement evidence. | Review card reflow and evidence inspection actions. |
| `insights/InterestAtlas.tsx` | Groups calculated interests. | Review long taxonomy labels, empty states and trace actions. |
| `insights/SearchAIInsights.tsx` | Separates search and AI conversation patterns. | Review dense grids on mobile and privacy/explanation text. |
| `insights/PlacesMovement.tsx` | Shows location evidence and movement candidates. | Review map/container sizing, evidence-strength controls and non-map alternative. |
| `insights/ChangesProjectsEras.tsx` | Shows detected changes, projects and eras. | Review timeline reflow and uncertainty language. |
| `insights/ContextCorrelations.tsx` | Shows bounded external-context correlations. | Review evidence/caution hierarchy and mobile cards. |
| `insights/EvidenceInspector.tsx` | Displays evidence trace for an insight. | Review dialog sizing, focus, source locators and error/retry. |

### ONSIT components

| Component | What it does | Current need / status |
|---|---|---|
| `onsit/DiscoveryForm.tsx` | Collects identity seeds and starts discovery. | Review validation/privacy guidance, responsive fields and submit state. |
| `onsit/ProgressTracker.tsx` | Polls and displays discovery progress. | Persist/recover job ID, bound polling, expose failure/retry and support reduced motion. |
| `onsit/FindingsList.tsx` | Filters/sorts discovery findings. | Load persisted history, test compact filters and truthful empty state. |
| `onsit/FindingCard.tsx` | Displays one finding with evidence/risk. | Review long URLs, action safety, touch targets and provenance. |
| `onsit/RiskBadge.tsx` | Encodes finding risk. | Ensure text/icon semantics beyond color and consistent vocabulary. |
| `onsit/VendorDiscoverySection.tsx` | Discovers vendor/DPO relationships and bulk actions. | Review provider authority, confirmation, persistence and narrow tables/forms. |
| `onsit/VendorListInput.tsx` | Extracts/imports vendor names. | Review large-list performance, parsing feedback, duplicate handling and mobile input. |
| `onsit/index.ts` | Public exports for ONSIT components. | Keep exports aligned with canonical components; no direct UI acceptance. |

### Settings components

| Component | What it does | Current need / status |
|---|---|---|
| `settings/UserProfileSection.tsx` | Edits username/email/avatar/password. | Review saved-state feedback, image sizing, validation and narrow forms. |
| `settings/IDDocumentsSection.tsx` | Manages identity documents. | Review upload progress, sensitive-data warning, file actions and mobile rows. |
| `settings/SourceConnectorsSection.tsx` | Configures source connectors. | Labelled/touch-sized forms, Intelligence-visible path disclosure, preflight validation, queued task identity, and profile-scoped health are implemented. Verify creation/sync/error states at narrow widths with a real safe source. |
| `settings/EmailConnectorSection.tsx` | Stores SMTP/IMAP credentials and performs a real IMAP connection test. | Monitoring claims removed; fields are labelled, actions stack/touch-size, and thrown save/test/remove operations clear busy state. Canonical monitoring remains in Source Connectors. |
| `settings/TaskRoutesSection.tsx` | Configures processing/model routes. | Priority split-screen audit; long engine/model/fallback controls must reflow without clipping. |
| `settings/WorkflowSettingsSection.tsx` | Configures workflow preferences. | Review persisted state, dependency warnings and narrow rows. |
| `settings/RetentionSettingsSection.tsx` | Configures retention policy. | Review irreversible-action language, confirmation and policy/version evidence. |
| `settings/PrivacySecuritySection.tsx` | Configures processing/privacy mode. | Review fail-closed explanations, dependent controls and mobile layout. |
| `settings/AICredentialsSection.tsx` | Manages model credentials. | New writes use authenticated AES-GCM in one atomic transaction; load failures are visible and empty saves are rejected. Verify provider aliases/test feedback and mobile forms. |
| `settings/APICredentialsSection.tsx` | Stores ONSIT/provider API credentials for future integration. | UI distinguishes stored presence from runtime provider availability, blocks empty saves, names reveal controls, and reflows rows. Active Intelligence consumption is not implemented. |
| `settings/N8NWebhooksSection.tsx` | Configures workflow webhooks. | Dead Test All action removed; environment URLs are no longer disclosed; rows and named reveal controls reflow. Server now accepts only credential-free HTTP(S) endpoints, validates the whole form before one transaction, and surfaces load failures. Real per-webhook health remains. |

### Layout components

| Component | What it does | Current need / status |
|---|---|---|
| `layout/DashboardLayout.tsx` | Navigation, headers, profile and shell. | Responsive breakpoint/min-width and truthful neutral health wording implemented; aggregate service health and 400% zoom remain. |
| `layout/NotificationsBell.tsx` | Retired local-only notification affordance. | Deleted and removed from the shell because no profile-scoped feed or persistence existed. Reintroduce only with a real notification contract. |

### Shared UI primitives

| Primitive | What it does | Current need / status |
|---|---|---|
| `ui/alert.tsx` | Alert container/content. | Verify semantic roles are supplied by callers and text wraps. |
| `ui/animations.tsx` | Shared motion helpers. | Respect reduced-motion and avoid layout animation. |
| `ui/avatar.tsx` | Avatar/image/fallback. | Verify alt text and fallback sizing. |
| `ui/badge.tsx` | Compact status labels. | Prevent color-only meaning and long-label overflow. |
| `ui/button.tsx` | Shared button variants/sizes. | Establish touch-size variant and allow responsive labels without overflow. |
| `ui/card.tsx` | Card structure. | Ensure `min-w-0`, wrapping and consistent compact padding. |
| `ui/checkbox.tsx` | Checkbox control. | Verify label association, focus and target size. |
| `ui/dialog.tsx` | Modal dialog primitive. | Verify viewport max-height/internal scrolling/focus across all callers. |
| `ui/error-boundary.tsx` | Catches client component failures. | Verify useful recovery, logging and no redirect loops. |
| `ui/form.tsx` | Form field/error helpers. | Verify described-by/error IDs and consistent required state. |
| `ui/input.tsx` | Text/date/file inputs. | Verify 16px mobile text where needed to avoid unwanted zoom and long-value behavior. |
| `ui/label.tsx` | Form label. | Verify every control association. |
| `ui/loading-spinner.tsx` | Loading status. | Supply accessible status text and reduced motion. |
| `ui/popover.tsx` | Anchored overlay. | Constrain collision/viewport and restore focus. |
| `ui/progress.tsx` | Progress visualization. | Require accessible value/label and truthful determinate state. |
| `ui/scroll-area.tsx` | Styled scrolling region. | Preserve keyboard/wheel/touch scrolling and visible affordance. |
| `ui/select.tsx` | Select trigger/content/item. | Add safe `min-w-0` caller contract; verify popup collision and long values. |
| `ui/separator.tsx` | Visual/semantic separator. | Hide decorative separators from accessibility tree where appropriate. |
| `ui/sheet.tsx` | Side/bottom overlay. | Verify width overrides, focus, swipe/touch and internal scrolling. |
| `ui/skeleton.tsx` | Loading placeholder. | Match final layout and expose separate accessible status. |
| `ui/sonner.tsx` | Toast host. | Verify contrast, duration, duplicate errors and mobile placement. |
| `ui/switch.tsx` | Boolean setting control. | Verify label, focus, disabled reason and target size. |
| `ui/table.tsx` | Responsive table wrapper. | Horizontal wrapper exists; add mobile card alternative where task completion would otherwise require two-axis scroll. |
| `ui/tabs.tsx` | Tab list/trigger/content. | Require caller overflow strategy; verify arrow-key orientation matches visual orientation. |
| `ui/textarea.tsx` | Multiline input. | Verify resizing, long content and error association. |
| `ui/tooltip.tsx` | Supplemental hover/focus text. | Never make required instructions tooltip-only; verify touch alternative. |

## Defect log

| Date | Defect | Root cause | Resolution / disposition |
|---|---|---|---|
| 2026-08-15 | Access Requests controls clipped on compact laptop viewport. | Desktop sidebar activated at `md`; header, action group, and toolbar were fixed single rows with fixed select widths. | Shell moved to `lg`; actions and toolbar now reflow. Browser matrix pending. |
| 2026-08-15 | Personal Insights briefly rendered then returned to Home. | Frontend and Intelligence containers had different internal authority keys; module 401 responses triggered the global login transition, and the valid login redirected Home. | Frontend recreated with Intelligence key while preserving session signing key. Add startup/config contract coverage. |
| 2026-08-15 | Hydration mismatch reported in Home Quick Actions. | Template-generated class strings differed in whitespace during the active dev/HMR transition. | Classes normalized with `cn`; clean container restart completed. |
| 2026-08-15 | Personal Insights date controls can hydrate differently by runtime timezone. | SSR used container UTC while the browser formats `datetime-local` in the user's timezone; default selection also called `new Date()` independently. | One server timestamp is passed into the client; date localization begins only after mount. Browser verification pending. |
| 2026-08-15 | Sidebar reported literal “System Online” without checking any service. | Static green indicator had no aggregate health source. | Replaced with neutral “Health not checked”; R0 regression now passes normally. Real aggregate health remains an explicit operational backlog item. |
| 2026-09-10 | ZIP import claimed graph projection and completed from stale state. | POST already recorded evidence, then the client repeated PUT against stale React state and read nonexistent `result.content`. | Removed duplicate PUT; maintain a local processed accumulator, retain run/artifact metadata, and state that evidence awaits review. |
| 2026-09-10 | Operational Import page exposed a random simulated broker scanner. | `DatabrokerScanner` generated local random results with no persisted job/evidence. | Removed from the active Import route and replaced with a disclosed link to authenticated ONSIT discovery. |
| 2026-09-10 | Docker frontend could not bind localhost:3000. | Port 3000 is owned by an unrelated Hermes Next.js process. | Preserved Hermes; restored GDPR frontend healthy on configured localhost:3002. User must stop/move Hermes before 3000 can be used. |
| 2026-09-11 | Policy analysis accepted arbitrary server-side URLs. | The acquisition route fetched the supplied URL without scheme, credential, DNS, or private-network validation. | Added a public HTTP(S) URL guard, reject mixed/private DNS results, disable redirect following, and return validation failures as 400. |
| 2026-09-11 | Request detail invented a 30-day countdown from creation time. | The active modal ignored canonical `deadline_at` evidence and derived labels/progress from elapsed days. | Replaced with recorded deadline or “Deadline not established”; workflow progress now uses the stored request value. |
| 2026-09-11 | Request chat could retain a failed optimistic message and expose raw server errors. | Auth-suppressed failures returned before rollback; API serialized the caught exception. | Rollback now precedes suppression and the API returns a stable generic error. |
| 2026-09-11 | N8N Settings offered a nonexistent bulk test and exposed operator URLs. | UI called an unimplemented route; GET merged raw environment webhook values into its browser response. | Removed the dead action, return only environment presence, and made reveal controls named/touch-sized with narrow reflow. Profile-owned persistence remains SETTINGS-002. |
| 2026-09-11 | Execution routes, privacy policy, audit rows, and N8N overrides were global. | Legacy task/configuration tables used singleton keys without canonical profile ownership. | Added and applied migration 034; all new reads/writes/audit records are profile-scoped and ambiguous legacy ownership fails closed. |
| 2026-09-11 | Policy analyses were globally cached by URL/domain and could be attached without request ownership. | Legacy schema and N8N/pre-request paths had no canonical profile/request key. | Added and applied migration 035, scoped every query to profile/request authority, made wizard-stage analysis explicitly transient, and added ownership/migration contracts. |
| 2026-09-11 | Invalid direct request IDs caused a PostgreSQL UUID exception and a 500 page. | The dynamic detail route queried before validating its route parameter. | Added an early UUID guard; a fresh live request to `/dashboard/requests/new` now returns a normal 404 rather than a server error. |
| 2026-09-11 | Agent Manager displayed fake schedules/status and sent every Run action to an incompatible endpoint. | A generic local-state card treated unrelated contextual APIs as interchangeable background agents. | Replaced it with five labelled links to the real contextual workflows; removed synthetic runs, schedules, activity, and last-run claims. |
| 2026-09-12 | Unused request sheet retained broken and toast-only actions. | A second request-detail implementation drifted from the active modal and direct route. | Deleted `RequestDetailSheet.tsx`; the responsive contract now prevents its silent reintroduction. |
| 2026-09-12 | Header notification bell always opened an empty, local-only list. | The shell mounted the component without a backend feed or persisted read/dismiss state. | Removed the affordance and orphan component; also named mobile-menu/theme icon buttons and removed clickable styling from the inert avatar. |
| 2026-09-12 | ONSIT API-key Settings claimed encryption/configuration although values used XOR and were not consumed by active workers. | Legacy storage and runtime credential paths diverged; presence was presented as provider readiness. | New writes use authenticated AES-256-GCM and a transaction; UI says “Stored,” discloses the missing worker integration, blocks empty saves, and returns authoritative presence. |
| 2026-09-12 | Legacy email card promised incremental monitoring and a 15-minute sync that it cannot start. | The card saves/tests legacy email credentials while the real monitor is disabled in favor of Source Connectors. | Relabelled as email credential + IMAP test, removed monitoring/sync claims, added labelled fields/live busy text, and guaranteed busy cleanup on failures. |
| 2026-09-12 | Wizard identity used placeholders/client-side cosmetic encryption and could draft under a fake requester. | Active step 2 omitted contact fields from store state and encrypted with a hardcoded browser key; submission fell back to placeholder name/email. | Active builder now carries entered name/email/phone/details, server validation rejects incomplete identity, request details use server-owned AES-GCM, graph linking is optional, and the retired duplicate selector was deleted. |
| 2026-09-12 | Typing in the wizard URL field repeatedly invoked external policy analysis as a “cache check.” | Debounced input called the same N8N analysis endpoint, whose cache flags were ignored/always false. | Removed automatic/cache/re-analysis paths; exactly one call occurs on explicit Analyze, after client URL shape and server public-host validation. |
| 2026-09-12 | Wizard scope/date options reset after navigating Back, and review promised sending before transport outcome was known. | Step 3 kept choices in component-local state and used unconditional send language. | Moved access/deletion/all-data state into the wizard store, controlled date inputs, labelled checkboxes, and separated Create from later draft/send outcomes. |
| 2026-09-12 | ONSIT progress could not resume after page reload and proxy errors exposed raw service text. | Task ID existed only in React state; proxy returned Intelligence response details. | Store task ID in the URL, restore it on mount, show findings-load failure, disclose service-bound durability, and return only stable proxy errors. |
| 2026-09-12 | Request cards exposed only a modal, so the owned deep-link record was effectively hidden. | The quick workspace became the sole list entry point while the authoritative server route drifted separately. | Added explicit canonical record links to each card and modal, retained a labelled quick view, and preserved the owner-checked route as the durable record. |
| 2026-09-12 | Request workspace upload UI simulated progress, promised graph ingestion, offered impossible deletion, and could re-run completed files. | Client timers and a legacy graph toggle diverged from the canonical evidence pipeline; the DELETE API intentionally retains evidence. | Removed invented progress/graph/delete behavior, process new files sequentially once, scope retry processing to the current owned request, and render only recorded server progress/state. |
| 2026-09-14 | ONSIT export fabricated sample findings after graph/query failure and did not constrain the graph query to the active profile. | A demo fallback remained in an authenticated production route and the Cypher predicate used source only. | Removed all sample fallback data, require `profile_id` in the Cypher query, and return an explicit 503 when the export cannot be produced. |
| 2026-09-14 | N8N webhook overrides could be partially saved and accepted arbitrary URL schemes or embedded credentials. | The browser-only `.url()` check was weaker than the server contract and each row committed independently. | Added server-owned HTTP(S)/credential/fragment validation, validate all inputs before writing, save in one transaction with rollback, and report settings-load failures instead of silently showing an empty form. |
| 2026-09-14 | AI provider credentials were written with legacy unauthenticated encryption and could partially save. | The route duplicated CBC crypto and committed providers independently. | Route all new writes through canonical AES-GCM, validate before writing, save in one transaction with rollback, preserve read-only compatibility for existing CBC rows, and surface load failure. |
| 2026-09-14 | Source Connectors accepted unusable configuration, discarded queued task identity, hid health, blocked browser pairing from the actual 3002 UI, and leaked proxy exception text. | Form/backend validation and runtime feedback were incomplete; the local-origin allowlist assumed only ports 3000/3001. | Added client/server configuration validation, task ID and health rendering, accessible status/labels/touch targets, port 3002 pairing support, and a stable 503 proxy envelope. |
| 2026-09-14 | A transient database timeout left Source Connectors as a permanently empty selector, and `?section=connectors` still opened Profile. | Connector loading had toast-only failure with no retry; Settings tabs ignored URL state. | Added a visible retry state, made section selection URL-backed with popstate handling, and verified direct-link plus browser Back behavior. The one observed database timeout recovered and subsequent connector API calls returned 200; underlying recurrence remains monitored. |

## Verification log

| Date | Check | Result |
|---|---|---|
| 2026-08-15 | Frontend TypeScript and focused ESLint before responsive tranche | Passed; one pre-existing unused import removed. |
| 2026-08-15 | Docker frontend health and localhost mapping | Healthy on `localhost:3000`. |
| 2026-08-15 | Access Requests at 1024×576 | No horizontal overflow; header actions form one equal-width row; search uses a full row and filters use two equal columns. |
| 2026-08-15 | Personal Insights authority/hydration retest at 1024×576 | Route remained `/dashboard/insights`; all seven module APIs returned 200; full dashboard rendered with no page-level overflow or hydration log. |
| 2026-09-10 | ZIP importer contract test | 2/2 passed: no duplicate PUT/graph claim and no active simulated broker scanner. |
| 2026-09-10 | TypeScript and diff integrity after importer repair | `tsc --noEmit` and `git diff --check` passed. |
| 2026-09-10 | Docker health and HTTP boundary | All eight containers healthy; GDPR frontend serves on 3002 and returns the expected 307 login redirect. Port 3000 remains occupied by Hermes. |
| 2026-09-11 | ONSIT and policy acquisition contracts | ONSIT 3/3 and public URL guard 12/12 focused tests passed. |
| 2026-09-11 | Request detail truthfulness contract | 4/4 passed for recorded deadlines, selection reset, chat rollback order, and generic API errors. |
| 2026-09-11 | TypeScript after ONSIT/import/policy/request-detail repairs | `tsc --noEmit` passed. |
| 2026-09-11 | Current Docker/HTTP boundary | Eight containers healthy; GDPR is on 3002 with the expected authentication redirect. PID 25844 from the unrelated Hermes frontend still owns 3000. |
| 2026-09-11 | Combined focused frontend contracts | 29/29 passed across Import, ONSIT, public URL safety, request detail, N8N Settings, and Settings profile isolation. |
| 2026-09-11 | Settings profile-ownership migration | Applied migration 034 in local Docker; all four owned tables have zero null owners and their profile indexes are present. |
| 2026-09-11 | Post-migration frontend static gates | `tsc --noEmit` passed; focused Settings/execution/N8N ESLint completed with no diagnostics. |
| 2026-09-11 | Policy ownership migration | Migration 035 applied in local Docker; history row present, zero unowned policy rows, and both profile/request indexes present. |
| 2026-09-11 | Consolidated focused frontend contracts | 36/36 passed across Import, ONSIT, URL safety, request detail (including invalid-ID handling), N8N Settings, Settings ownership, and policy ownership/migration. |
| 2026-09-11 | Live bind-mounted frontend after restart | All eight containers healthy; Requests and New Request step 1 render at 467px without page overflow. Requests shows the requested placeholder and all three actions. Invalid detail IDs return 404. GDPR remains on localhost:3002 because unrelated Hermes owns port 3000. |
| 2026-09-11 | Agent Manager truthfulness and compact layout | 3/3 focused contracts passed; live Home at 467px rendered all five shortcut labels with no page overflow and no synthetic “All Idle” state. |
| 2026-09-12 | Duplicate-detail and shell truthfulness contracts | 11/11 focused request/responsive/Agent Manager checks passed after retiring the sheet; 9/9 shell/responsive/shortcut checks passed after removing the unwired notification control. |
| 2026-09-12 | Settings credential truthfulness | 11/11 focused credential/profile/N8N contracts passed; TypeScript passed. Live Connectors and Advanced tabs at 467px showed corrected email/provider wording and no horizontal overflow. |
| 2026-09-12 | Wizard identity/analysis/state contracts | 8/8 focused wizard contracts passed; combined wizard/public-URL/policy checks passed 23/23; protected-state reset slice passed 13/13. TypeScript passed and live step 1 at 467px showed explicit/transient analysis wording without overflow. |
| 2026-09-12 | ONSIT service-bound resume contract | 14/14 focused ONSIT/wizard/credential checks passed; TypeScript passed. |
| 2026-09-12 | Consolidated continuation regression gate | 59/59 focused tests passed across 13 files. Final edited-surface ESLint and `tsc --noEmit` passed with zero diagnostics. |
| 2026-09-12 | Canonical request-detail and upload-truthfulness slice | Request-detail contract 9/9 passed; focused route/repository slice passed 12 with the database integration case skipped by its existing gate. `tsc --noEmit` passed. Live stack remains eight healthy containers on localhost:3002; current profile has no request cards for owned-record browser acceptance. |
| 2026-09-14 | ONSIT export and N8N override hardening | ONSIT/request-detail slice passed 14/14; N8N URL/settings slice passed 10/10. TypeScript and focused N8N ESLint passed. |
| 2026-09-14 | AI credentials and Source Connectors hardening | Credential/N8N contracts passed 14/14. Source Connectors/Settings URL contracts passed 5/5; five focused validation/origin assertions passed inside the healthy Intelligence container. Project TypeScript and focused connector ESLint passed with zero diagnostics; all eight Docker services were healthy on port 3002. |
| 2026-09-14 | Live Source Connectors and Settings URL acceptance | Rebuilt only `gdpr_nextjs`; direct `?section=connectors` selected Connectors, tab selection updated the URL, browser Back restored it, and the 363px filesystem form had labelled fields, truthful container-path guidance, visible client-side rejection for a relative path, and no horizontal page overflow (`351px` document within `363px` viewport). |
