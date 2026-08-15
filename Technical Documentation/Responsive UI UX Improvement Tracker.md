# Responsive UI/UX Improvement Tracker

Updated: 2026-08-15

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
| REQ-004 | Request detail modal/sheet | Inspect evidence, messages, events, and actions on any viewport. | Full-width stacked panels below `lg`; tabs scroll or condense; no `100vw - 256px` mobile sizing. | in-progress | Responsive sizing implemented. The active modal remains canonical; fake Export/Complete buttons removed pending server workflows. |
| REQ-006 | Request detail policy scan | Scan a controller policy from an existing request and render a real analysis or explicit error. | Action remains usable in stacked modal; request body matches the server contract. | implemented-needs-browser | Corrected payload to `{url, company}` and added non-2xx handling; live request with a valid policy URL still required. |
| REQ-007 | Request chat | Send a message without displaying a failed submission as persisted. | Composer remains reachable; failed optimistic messages are rolled back and input restored. | implemented-needs-browser | Non-2xx responses now fail visibly and restore the draft; API success/error browser test remains. |
| REQ-005 | New Request wizard | Complete all steps and navigate back safely. | Header/actions wrap; progress labels abbreviate or scroll accessibly on phones. | backlog | Audit and browser test required. |
| BROKER-001 | Access Requests “Scan for Brokers” → ONSIT Discovery | Reach the real discovery workflow directly from the request workflow instead of the simulated legacy scanner. | Button remains visible at every breakpoint and opens the authenticated discovery flow. | verified | Link rendered and remained visible at 1024px with no horizontal overflow. |
| BROKER-002 | `DatabrokerScanner.tsx` | Run a real profile-scoped broker scan and review persisted evidence before creating removal requests. | Clear queued/running/completed/failed state; no fabricated findings; usable cards/actions on mobile. | truthfulness-defect | Current implementation uses random simulated results and local-only state; replace with real job API before representing it as operational. |
| HOME-001 | Home summary and Quick Actions | Start common tasks and understand current workload. | Compact hero/KPI spacing on laptop; cards reflow; navigation handoff focuses intended control. | in-progress | QuickActions hydration classes normalized; responsive hero and `focus=search` behavior pending. |
| HOME-002 | `AgentManager.tsx` | Configure/run automation and understand status. | Schedule/action controls never overlap; touch targets remain usable. | truthfulness-defect | Layout repaired; schedules are local-only and several labelled actions target incompatible endpoints. Product wiring required. |
| INS-001 | Personal Insights selection/hydration | Open Insights without hydration warnings or route loss and see stable time controls. | Server and first client render share one time snapshot; local-time formatting occurs after mount; controls stack below `sm`. | implemented-needs-browser | Stable `initialNow`, mounted date localization, and responsive controls implemented; live no-warning proof pending. |
| INS-002 | Personal Insights module loading | See useful modules as they arrive and retry only failures. | Progressive per-module loading/error state; slow module cannot pin the visibility of completed modules. | implemented-needs-browser | Each module now commits independently; global refresh completes after all settle. Add per-module retry and bounded concurrency next. |
| GRAPH-001 | Graph workspace and inspector | Explore nodes and evidence without the inspector crushing the graph. | Inspector becomes a sheet/drawer below `xl`; controls reflow; compact viewport math matches shell padding. | implemented-needs-browser | Graph had no page overflow at 1024px; drawer node-selection behavior and canvas resize remain to verify. |
| SETTINGS-001 | Settings navigation/forms | Find a setting, understand state, edit it, and see validation/health. | Horizontal scrollable section navigation below wide desktop; vertical rail only with adequate width; labels/fields never clip. | in-progress | Navigation, card padding, retention grids/confirmation, and ID upload/document rows repaired. Task routes, N8N, credentials, connectors, privacy, and split-screen browser proof remain. |
| ONSIT-001 | ONSIT discovery | Start a bounded discovery, monitor progress, review history, and reuse findings. | Forms and progress stack; findings persist across reload; claims match active providers. | truthfulness-defect | Current findings/history are page-memory only; qualify unsupported marketing claims. |
| OVERLAY-001 | Dialog/sheet/popover primitives | Complete modal tasks by touch and keyboard without content leaving the viewport. | Safe viewport max width/height; internal scrolling; focus return; 44px close/actions. | backlog | Audit shared sheet/select/tabs and caller overrides. |
| A11Y-001 | Keyboard, focus, labels, status | Complete primary journeys without a pointer and understand async status. | Visible focus, named icon buttons, live regions, logical tab order, no color-only state. | in-progress | Search clear and identity-document icon actions named; notification and settings webhook keyboard/target audit remains. |

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
| `app/dashboard/requests/[id]/page.tsx` | Direct request detail route. | Review route consistency with modal/sheet, loading, missing/foreign request states. |
| `app/requests/new/page.tsx` | Guided three-step request creation. | Compact progress/header implemented; validate all wizard steps and persistence. |
| `app/dashboard/import/page.tsx` | ZIP import and legacy broker scanner. | Import workflow review; legacy random broker scanner must not be presented as evidence. |
| `app/dashboard/graph/page.tsx` | Graph exploration workspace. | Responsive inspector/control implementation needs live node-selection proof. |
| `app/dashboard/insights/page.tsx` | Personal Insights server boundary and stable time seed. | Authority, rendering and 1024px overflow verified; partial/error behavior remains. |
| `app/dashboard/onsit/page.tsx` | Real asynchronous footprint discovery workflow. | Persist task/findings history, qualify provider claims, and test narrow forms. |
| `app/dashboard/settings/page.tsx` | Settings sections and navigation. | Responsive horizontal/vertical navigation implemented; every section needs field-level review. |

### Dashboard components

| Component | What it does | Current need / status |
|---|---|---|
| `dashboard/ActivityFeed.tsx` | Displays recent activity. | Review empty/error states, timestamp hydration and narrow row wrapping. |
| `dashboard/AgentManager.tsx` | Displays agent schedules and run actions. | Controls no longer overlap; replace local schedules/incompatible endpoints with truthful jobs. |
| `dashboard/ComplianceGauge.tsx` | Shows deadline/response evidence. | Review terminology, chart scaling and no-data semantics. |
| `dashboard/DatabrokerScanner.tsx` | Simulates scans of a static broker list. | Truthfulness defect: replace with persisted profile-scoped discovery or remove from operational UI. |
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
| `dashboard/ZipImporter.tsx` | Uploads GDPR export archives. | Review large-file progress, cancellation, error recovery, privacy disclosure and mobile dropzone. |

### Request components

| Component | What it does | Current need / status |
|---|---|---|
| `requests/AddManualRequestDialog.tsx` | Creates externally initiated requests and optionally scans a policy. | Responsive fields and server refresh implemented; test immediate new-card appearance and sanitize policy rendering. |
| `requests/DataViewer.tsx` | Presents received/request data. | Review large payload virtualization, long values, download actions and mobile navigation. |
| `requests/RequestCard.tsx` | Summarizes one request with actions. | Review 320px labels/actions, keyboard interaction and truthful deadlines. |
| `requests/RequestDetailModal.tsx` | Full activity/evidence/request workspace. | Responsive stacked layout implemented; test all tabs/actions and remove duplicate detail implementation. |
| `requests/RequestDetailSheet.tsx` | Alternate sheet-based request detail. | Width/tabs repaired; decide canonical detail surface and retire duplication. |
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
| `settings/SourceConnectorsSection.tsx` | Configures source connectors. | Review connection health, credential boundaries, errors and compact cards. |
| `settings/EmailConnectorSection.tsx` | Configures inbox connector. | Review password handling, test result, schedule dependency and responsive fields. |
| `settings/TaskRoutesSection.tsx` | Configures processing/model routes. | Priority split-screen audit; long engine/model/fallback controls must reflow without clipping. |
| `settings/WorkflowSettingsSection.tsx` | Configures workflow preferences. | Review persisted state, dependency warnings and narrow rows. |
| `settings/RetentionSettingsSection.tsx` | Configures retention policy. | Review irreversible-action language, confirmation and policy/version evidence. |
| `settings/PrivacySecuritySection.tsx` | Configures processing/privacy mode. | Review fail-closed explanations, dependent controls and mobile layout. |
| `settings/AICredentialsSection.tsx` | Manages model credentials. | Review secret masking/storage, provider aliases, test feedback and mobile forms. |
| `settings/APICredentialsSection.tsx` | Manages ONSIT/provider API credentials. | Review secret handling, scope descriptions, errors and mobile forms. |
| `settings/N8NWebhooksSection.tsx` | Configures workflow webhooks. | Review URL validation, secret disclosure, test action and responsive list. |

### Layout components

| Component | What it does | Current need / status |
|---|---|---|
| `layout/DashboardLayout.tsx` | Navigation, headers, profile and shell. | Responsive breakpoint/min-width and truthful neutral health wording implemented; aggregate service health and 400% zoom remain. |
| `layout/NotificationsBell.tsx` | Displays and manages notifications. | Viewport-safe width implemented; fix render-time clock purity and icon-button labels. |

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

## Verification log

| Date | Check | Result |
|---|---|---|
| 2026-08-15 | Frontend TypeScript and focused ESLint before responsive tranche | Passed; one pre-existing unused import removed. |
| 2026-08-15 | Docker frontend health and localhost mapping | Healthy on `localhost:3000`. |
| 2026-08-15 | Access Requests at 1024×576 | No horizontal overflow; header actions form one equal-width row; search uses a full row and filters use two equal columns. |
| 2026-08-15 | Personal Insights authority/hydration retest at 1024×576 | Route remained `/dashboard/insights`; all seven module APIs returned 200; full dashboard rendered with no page-level overflow or hydration log. |
