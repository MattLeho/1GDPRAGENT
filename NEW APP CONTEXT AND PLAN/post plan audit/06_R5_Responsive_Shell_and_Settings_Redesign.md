# R5 — Responsive Shell and Settings Redesign

## Goal

Make the entire app usable in full-screen, split-screen, narrow desktop and mobile-width layouts without clipped controls, inaccessible actions or misleading health indicators.

This plan owns presentation architecture, not model or connector business logic.


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
- R1 shared profile/session state exists.
- R3/R4 component interfaces are frozen or merged.

## Lead-agent ownership

The lead agent owns the responsive design system, shell modes, container-query policy, settings information architecture, accessibility standard, visual acceptance matrix and conflict resolution with R3/R4.

## Subagent delegation

### A — Dashboard shell

Implement expanded sidebar, icon rail, narrow overlay and persistent state.

### B — Responsive primitives

Create container-query cards, form grids, toolbars and overflow guards.

### C — Settings composition

Redesign seven-section navigation and responsive section composition without changing domain semantics.

### D — Graph responsiveness

Adapt graph, toolbar, inspector and chat to container width.

### E — Page audit

Audit Home, Requests, Graph, Insights, ONSIT, New Request and all settings sections.

### F — Status/error/loading

Replace hardcoded health and create explicit error/configuration states.

### G — Playwright/accessibility

Own viewport, overlap, keyboard, zoom, theme and reduced-motion tests.

## Layout principles

- Use container width for embedded components.
- Use `minmax(0, 1fr)` and `min-width: 0`.
- Avoid fixed widths where content must shrink.
- Never place the only save action off-screen.
- Use horizontal scrolling only for dense data or intentional tab strips.
- Test a narrow component inside a wide viewport.

## Sidebar

Modes:

```text
expanded: about 256 px
icon rail: about 64–72 px
overlay/hidden: narrow layouts
```

Requirements:

- accessible collapse button;
- tooltips in icon mode;
- remembered preference;
- no reset on route change;
- adaptive status panel;
- no graph resize breakage.

## Header/profile

Use R1 shared profile state. Name/email collapse gracefully; avatar and controls never overlap. Invalid sessions must not leave the header over a broken page.

## Settings

Wide:

```text
section navigation | content
```

Narrow:

```text
section select or deliberate horizontal tabs
single-column content
```

### Processing routes

Use stacked cards:

```text
task identity
privacy/location
primary engine/model
health
fallback chain
advanced controls
save state
```

### Connectors and credentials

Actions and permission summaries stack without clipping.

## Graph

Wide:

```text
canvas + inspector
chat dock/below
```

Narrow:

```text
canvas
inspector drawer
collapsible chat
```

Remove hard `400 px` canvas floors when container is narrower. Mode controls must wrap or scroll deliberately.

## Real system status

Aggregate:

- session;
- PostgreSQL;
- Neo4j;
- Redis;
- intelligence;
- Celery;
- Qdrant;
- n8n when enabled;
- configured engines;
- connector auth failures.

States:

```text
Healthy
Degraded
Configuration required
Authentication required
Offline
```

Clicking opens per-service diagnostics.

## Error boundaries

Distinguish:

- expired session;
- missing configuration;
- service unavailable;
- query failure;
- permission denied;
- empty data;
- loading.

Failure is not an empty state.

## Accessibility

- keyboard navigation;
- visible focus;
- labelled icon buttons;
- adequate targets;
- no colour-only states;
- screen-reader announcements;
- reduced motion;
- semantic forms/headings.

## Viewport matrix

```text
1920×1080
1440×900
1366×768
1024×768
800×900
600×900
390×844
```

Also test browser zoom at `125%` and `150%`, dark/light themes and a narrow container within `1440 px`.

## Automated assertions

- no document-level horizontal overflow;
- primary actions remain visible;
- interactive controls do not overlap;
- save buttons are clickable;
- graph dimensions match its container;
- inspector changes to drawer;
- sidebar state persists;
- status reflects injected failure;
- keyboard reaches all actions.

## Definition of done

- Viewport matrix passes.
- Sidebar collapses and persists.
- Settings adapt to container width.
- Processing/connectors work in split-screen.
- Graph inspector becomes a drawer.
- Health is real, not hardcoded.
- Errors are explicit.
- Keyboard/screen-reader basics pass.
- Independent visual/accessibility audits pass.

## Paste-ready `/goal`

```text
Execute R5 — Responsive Shell and Settings Redesign.

Audit R0–R4 first. Build a responsive shell with expanded, icon-rail and overlay sidebar modes. Introduce container-query primitives and refactor every page/settings section so split-screen and narrow containers do not clip or overlap. Preserve R3 model and R4 connector semantics.

Replace hardcoded System Online with real aggregate diagnostics. Add distinct loading, empty, configuration, authentication and failure states. Make graph inspector/chat responsive and implement keyboard/accessibility basics.

Delegate shell, responsive primitives, settings, graph layout, page audits, status/error UI and Playwright accessibility tests to bounded subagents. Keep design-system contracts, shared layout changes, cross-plan integration and final visual acceptance under the lead agent.

Before completion, run the viewport matrix, narrow-container, zoom, theme and keyboard tests. Commission independent visual and accessibility audits.
```
