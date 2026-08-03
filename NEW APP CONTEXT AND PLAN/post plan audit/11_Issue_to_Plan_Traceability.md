# Issue-to-Plan Traceability

| ID | Problem | Plan | Required proof |
|---|---|---|---|
| AUTH-001 | Dashboard renders while session is invalid or expired | R1 | Invalid cookie cleared and redirect occurs before protected content |
| AUTH-002 | Connectors and Graph return `401` inside the dashboard | R1 | One authority contract across shell and APIs |
| AUTH-003 | Sensitive settings routes lack consistent authentication | R1 | Route inventory and unauthorised API suite |
| AUTH-004 | Personal Insights uses the first user rather than the active profile | R1/R6 | Cross-profile isolation tests |
| PROFILE-001 | Saved profile does not update the top-right identity | R1 | Header updates immediately without reload |
| DB-001 | Dashboard queries missing `requests.updated_at` | R2 | Migration plus execution of every request query |
| DB-002 | `requests` and `access_requests` are used inconsistently | R2 | Canonical repository and static invariant |
| DB-003 | Response and deadline dates are inferred from unrelated updates | R2 | Explicit lifecycle timestamps and deterministic deadline engine |
| MODEL-001 | Request chat fails because Google is still the hidden default | R3 | Non-Google route works with zero Google calls |
| MODEL-002 | Legacy `model_preferences` remains active | R3 | No runtime reads; migration complete |
| MODEL-003 | Discovered models are not shown in the selector | R3 | Searchable discovered dropdown and `Other` option |
| MODEL-004 | Fallback provider has no separately selectable model | R3 | Ordered engine/provider/model fallback editor |
| MODEL-005 | Task recommendations do not prefer suitable small models | R3 | Deterministic task suitability scoring |
| MODEL-006 | NVIDIA and local visual labels are ambiguous | R3 | Explicit provider/runtime naming |
| MODEL-007 | Health cannot guide or install missing local models | R3 | Bounded hardware-aware setup job |
| CONN-001 | Source type appears non-functional | R1/R4 | Valid session loads definitions and onboarding |
| CONN-002 | Gmail OAuth is absent | R4 | OAuth, backfill, incremental sync and revocation |
| CONN-003 | Outlook OAuth is absent | R4 | OAuth, Graph delta sync and revocation |
| CONN-004 | Browser history pairing is hidden and manual | R4 | Guided extension installation and pairing |
| CONN-005 | Celery may not receive the credential encryption key | R4/R7 | Worker decryption and rotation test |
| GRAPH-001 | Graph shows `401` despite Neo4j running | R1/R6 | Session fixed and server-side Neo4j test |
| GRAPH-002 | Product implies Neo4j browser login is relevant | R6 | Protected infrastructure diagnostics |
| GRAPH-003 | Temporal controls are date inputs rather than sliders | R6 | Point and dual-handle sliders |
| GRAPH-004 | Through-time graph animation is missing | R6 | Snapshot playback test |
| UI-001 | Processing settings crush in split-screen | R5 | Narrow-container Playwright test |
| UI-002 | Home and other pages clip or waste available space | R5 | Complete viewport matrix |
| UI-003 | Sidebar is fixed and consumes graph space | R5 | Persistent collapse and icon rail |
| UI-004 | Graph inspector is fixed width | R5 | Drawer transition at narrow width |
| OPS-001 | “System Online” is hardcoded | R5/R7 | Aggregate health reflects injected failures |
| SEM-001 | Privacy/compliance metrics are fabricated from request counts | R2/R7 | Removal or evidence-grounded replacement |
| SEC-001 | Policy URL acquisition permits SSRF | R7 | Private-network and redirect blocking tests |
| SEC-002 | AI credentials use a duplicate weaker encryption path | R3/R7 | Unified authenticated AES-GCM store |
| SEC-003 | Infrastructure ports and default credentials are unsafe | R7 | Localhost binding and configuration scan |
| OPS-002 | Runtime installs dependencies and uses development servers | R7 | Production image and cold-start tests |
| QA-001 | Acceptance reports overstate integrated completion | R0/R8 | Revised evidence ledger and final independent audit |
| QA-002 | Browser acceptance relies heavily on source-string tests | R0/R8 | Authenticated interaction evidence |
