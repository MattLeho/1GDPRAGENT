# GDPR Automation App - Feature Analysis & Next Steps

> **Document Updated:** 2025-12-16  
> **Status:** Comprehensive feature comparison between planned documentation and current implementation.

---

# 🚨 PRIORITY ZERO: Mock/Placeholder Implementations to Replace

Before building new features, we must replace all mock implementations with real functionality. These are blocking the app from being actually useful.

## Mock Implementation Checklist

### High Priority - Core Functionality Blocked

| # | File | Function/Location | Mock Description | Real Implementation Needed | User Action Required? |
|---|------|-------------------|------------------|---------------------------|----------------------|
| 1 | `components/wizard/UrlAnalyzer.tsx` | `handleAnalyze()` (line 16-53) | Returns hardcoded `mockResult` after 2s delay | N8N webhook to scrape privacy policy & extract DPO email | ❌ No |
| 2 | `lib/actions/dashboard.ts` | `getDashboardStats()` (line 30-48) | Calculates fake volume as `name.length * 0.5 GB` | Sum actual `received_data.file_size_mb` grouped by company | ❌ No |
| 3 | `app/dashboard/home/page.tsx` | `reviewItems` (line 26-30) | Hardcoded array of 2 fake review items | Query `messages` table for unread items | ❌ No |
| 4 | `app/dashboard/settings/page.tsx` | `handleSave()` (line 16-24) | Fake 1.5s delay, no actual save | Store email credentials encrypted, test IMAP connection | ⚠️ App Password |
| 5 | `app/dashboard/requests/[id]/page.tsx` | `MOCK_REQUEST` (line 31-82) | Entire page uses hardcoded Spotify request with fake messages | Fetch real request by ID, real messages from DB | ❌ No |
| 6 | `components/requests/RequestDetailSheet.tsx` | Timeline section (line 71-88) | Hardcoded "Sent Request" and "Processing" timeline items | Fetch real timeline events from messages table | ❌ No |
| 7 | `components/wizard/IdentitySelector.tsx` | `MOCK_DEFAULTS` (line 40-53) | Hardcoded personas with fake data | Fetch from Neo4j graph, or fall back to Postgres profiles | ❌ No |
| 8 | `lib/db.ts` | `db.query()` (line 17-28) | Returns empty mock result when Docker is down | Should throw proper error or show connection status | ❌ No |

### Medium Priority - Simulated Delays

| # | File | Location | Issue | Fix |
|---|------|----------|-------|-----|
| 9 | `lib/actions/requests.ts` | Line 24 | 500ms artificial delay | Remove `setTimeout` |
| 10 | `lib/actions/dashboard.ts` | Line 16 | 300ms artificial delay | Remove `setTimeout` |
| 11 | `components/wizard/UrlAnalyzer.tsx` | Line 41 | 1s delay before `nextStep()` | Keep for UX, but remove mock data |

### Lower Priority - TODOs in Code

| # | File | Line | TODO |
|---|------|------|------|
| 12 | `lib/actions/requests/submit.ts` | 15 | `identity: unknown; // TODO: strict typing` |
| 13 | `lib/actions/requests/submit.ts` | 82 | `// TODO: Insert request_details (identity info)` |

### Placeholders Noted (Not Urgent)

| File | Location | Note |
|------|----------|------|
| `app/dashboard/settings/page.tsx` | Line 101 | `{/* Identity / Profile Card (Placeholder for future) */}` |
| `components/wizard/IdentitySelector.tsx` | Line 84 | `encrypted_address: encryptData("Address Placeholder", ...)` |
| `components/wizard/IdentityBuilder.tsx` | Line 101 | `encrypted_address: encryptData("Address Placeholder", ...)` |

---

## ⚙️ External Setup Required (User Action)

To replace some mocks, you'll need to set up external services:

### 1. Email Integration (Settings Page)
**Status:** UI built, backend missing

**You need to provide:**
- Gmail/Outlook App Password (not regular password)
- IMAP host and port

**How to get Gmail App Password:**
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Enable 2-Factor Authentication
3. Go to "App Passwords" → Generate new app password
4. Select "Mail" and "Windows Computer"
5. Copy the 16-character password

### 2. N8N Workflow (URL Analyzer)
**Status:** Container running, workflows not created

**You need to:**
1. Open http://localhost:5678 (N8N interface)
2. Create workflow with:
   - Webhook trigger (receive URL)
   - HTTP Request node (fetch privacy policy page)
   - OpenAI node (extract DPO email, address, data types)
   - Respond to Webhook node (return JSON)

**You need to provide:**
- OpenAI API Key (set in N8N credentials)

### 3. Neo4j Graph Seeding
**Status:** Container running, empty database

**You need to:**
- Run seed script to create root User node and sample Personas
- OR manually create via Neo4j Browser (http://localhost:7474)

---

## Step-by-Step Mock Replacement Guide

### Mock #1: URL Analyzer → Real N8N Webhook

**Current (Mock):**
```typescript
// components/wizard/UrlAnalyzer.tsx line 23-35
await new Promise((resolve) => setTimeout(resolve, 2000))
const mockResult = { dpo_email: "privacy@example.com", ... }
```

**Replace with:**
```typescript
const response = await fetch('/api/analyze', {
  method: 'POST',
  body: JSON.stringify({ url })
});
const result = await response.json();
```

**Subtasks:**
1. [ ] Create N8N workflow: Webhook → HTTP Fetch → OpenAI Extract → Response
2. [ ] Create Next.js API route `/api/analyze` that proxies to N8N webhook
3. [ ] Handle error states (site unreachable, no privacy policy found)
4. [ ] Update `UrlAnalyzer.tsx` to call real API
5. [ ] Add retry logic and better error messages

---

### Mock #2: Dashboard Volume Stats → Real Database Query

**Current (Mock):**
```typescript
// lib/actions/dashboard.ts line 38
const size = name.length * 0.5; // Mock size
```

**Replace with:**
```sql
SELECT company_name, SUM(file_size_mb) as total_mb
FROM received_data rd
JOIN requests r ON rd.request_id = r.id
GROUP BY company_name
ORDER BY total_mb DESC
LIMIT 5
```

**Subtasks:**
1. [ ] Verify `received_data` table has `file_size_mb` column
2. [ ] Create real SQL query to sum file sizes by company
3. [ ] Handle case when no data exists yet (show empty state)
4. [ ] Convert MB to GB for display
5. [ ] Add caching to avoid repeated queries

---

### Mock #3: Review Queue → Real Messages Query

**Current (Mock):**
```typescript
// app/dashboard/home/page.tsx line 26-30
const reviewItems = [
    { id: '1', type: 'email', title: 'New response from Spotify', ... }
]
```

**Replace with:**
```typescript
const reviewItems = await getUnreadItems(); // New server action
```

**Subtasks:**
1. [x] Create server action `getUnreadItems()` in `lib/actions/messages.ts` ✅ IMPLEMENTED
2. [x] Query `messages` WHERE `sender = 'company'` ✅ IMPLEMENTED
3. [x] Query `received_data` for pending files ✅ IMPLEMENTED
4. [ ] Mark items as read when user clicks "Review"
5. [ ] Add "Mark All Read" button

---

### Mock #4: Settings Save → Real Credential Storage

**Current (Mock):**
```typescript
// app/dashboard/settings/page.tsx line 18-19
await new Promise(resolve => setTimeout(resolve, 1500));
setConnectionStatus('success');
```

**Replace with:**
```typescript
const result = await saveEmailCredentials({ email, password, imapHost, port });
setConnectionStatus(result.success ? 'success' : 'failed');
```

**Subtasks:**
1. [x] Create `email_settings` table with encrypted credential storage ✅ IMPLEMENTED in 02_DATABASE_SCHEMA.sql
2. [x] Create server action `saveEmailCredentials()` ✅ IMPLEMENTED in lib/actions/email-settings.ts
3. [ ] Encrypt password using AES before storing
4. [x] Create `testImapConnection()` stub ✅ IMPLEMENTED (awaiting N8N workflow)
5. [ ] Display real error messages on failure

---

### Mock #5: Request Detail Page → Real Data Fetch

**Current (Mock):**
```typescript
// app/dashboard/requests/[id]/page.tsx line 91
const request = MOCK_REQUEST; // Hardcoded Spotify
```

**Replace with:**
```typescript
const request = await getRequestById(params.id);
const messages = await getMessages(params.id);
```

**Subtasks:**
1. [ ] Create server action `getRequestById(id)` 
2. [x] Create server action `getMessages(requestId)` ✅ IMPLEMENTED in lib/actions/messages.ts
3. [ ] Convert page to Server Component for data fetching
4. [ ] Handle 404 case (request not found)
5. [ ] Add loading skeleton while fetching

---

# 📊 Overview Summary

| Category | Completed | In Progress | Not Started |
|----------|-----------|-------------|-------------|
| Infrastructure | 7 | 0 | 0 |
| Dashboard | 6 | 0 | 2 |
| New Request Wizard | 4 | 1 | 3 |
| View Requests | 6 | 0 | 2 |
| Identity System | 3 | 0 | 3 |
| **Knowledge Graph** | 6 | 0 | 3 |
| Automation/Agents | 0 | 0 | 4 |
| Advanced Features | 0 | 0 | 6 |

---

## ✅ COMPLETED FEATURES

### 1. Docker Infrastructure & Local Deployment
**Status:** ✅ Complete

- [x] Docker Compose with `gdpr-net` network
- [x] PostgreSQL 16 Alpine container with health checks
- [x] N8N automation engine container
- [x] Neo4j 5 Community container
- [x] Qdrant vector database container ✅ NEW
- [x] Next.js container with hot-reload
- [x] Start scripts (`start-app.bat` / `start-app.sh`)

### 2. Database Schema
**Status:** ✅ Complete

- [x] `profiles`, `requests`, `request_details`, `messages`, `received_data` tables
- [x] `email_settings` table ✅ NEW

### 3. Dashboard Layout / App Shell
**Status:** ✅ Complete

- [x] `DashboardLayout.tsx` with sidebar navigation
- [x] Responsive mobile menu
- [x] Top header bar with user profile

### 4. Home Page / Dashboard
**Status:** ✅ Complete (with mock data)

- [x] `StatsOverview`, `DataVolumeChart`, `TaskWidget`, `ReviewQueue` components

### 5. New Request Wizard
**Status:** ✅ Complete (mock analyzer)

- [x] 3-step wizard with Zustand state
- [x] `UrlAnalyzer`, `IdentityBuilder`, `ScopeSelector`
- [x] `submitRequest` server action

### 6. View Requests Dashboard
**Status:** ✅ Complete

- [x] `RequestsGrid`, `RequestCard`, `RequestDetailSheet`
- [x] `SearchToolbar` with debounced search ✅ NEW
- [x] Filter by status dropdown ✅ NEW
- [x] Sort by date/name/status ✅ NEW
- [x] URL params sync ✅ NEW

### 7. Settings Page
**Status:** ✅ Complete (UI only)

- [x] Email Integration card
- [x] Agent Identity card

---

# 🆕 NEW FEATURE: Knowledge Graph Page

Based on `knowledgegraph.md`, this is a major new page to implement.

## Feature Overview

**Route:** `/dashboard/graph`  
**Purpose:** Interactive visualization of your "Digital Twin" - all companies, accounts, and data points connected in a graph.

## Implementation Subtasks

### Phase 1: Infrastructure ✅ COMPLETE

1. [x] Neo4j container in Docker Compose
2. [x] `lib/graph.ts` - Neo4j driver connection
3. [x] Add Qdrant vector database to `docker-compose.yml` ✅ IMPLEMENTED
4. [ ] Create `lib/qdrant.ts` - Qdrant client connection
5. [x] Update sidebar to include "Data Graph" navigation item ✅ IMPLEMENTED

### Phase 2: Graph Data API ✅ PARTIAL

1. [x] Create `GET /api/graph/data` endpoint ✅ IMPLEMENTED at `app/api/graph/route.ts`
2. [ ] Create `POST /api/graph/node` to create new nodes manually
3. [ ] Create `DELETE /api/graph/node/:id` to remove nodes
4. [ ] Create `POST /api/graph/merge` to merge duplicate nodes
5. [x] Create `GET /api/graph/stats` endpoint ✅ IMPLEMENTED at `app/api/graph/stats/route.ts`

### Phase 3: Graph Page UI ✅ COMPLETE

1. [x] Create `app/dashboard/graph/page.tsx` ✅ IMPLEMENTED
2. [x] Install and configure `react-force-graph-2d` ✅ ADDED TO package.json
3. [x] Implement Zone A: `GraphCanvas.tsx` component ✅ IMPLEMENTED
4. [x] Implement Zone B: `InspectorPanel.tsx` component ✅ IMPLEMENTED
5. [x] Implement Zone C: `ShadowProfileChat.tsx` component ✅ IMPLEMENTED

### Phase 4: Graph Visualization Features ✅ COMPLETE

1. [x] Node styling: User (purple), Persona (blue), Company (green), Attribute (cyan) ✅ IMPLEMENTED
2. [x] Edge styling: Gray normal, red for high-risk ✅ IMPLEMENTED
3. [x] Pan/Zoom controls ✅ IMPLEMENTED
4. [x] `onNodeClick` to select and show in inspector ✅ IMPLEMENTED
5. [ ] `onNodeDoubleClick` to expand neighbors

### Phase 5: Inspector Panel Features ✅ COMPLETE

1. [x] Default state: Show graph stats (node count, risk count, last updated) ✅ IMPLEMENTED
2. [x] Selected state: Show node properties, evidence placeholder ✅ IMPLEMENTED
3. [x] Action buttons: "Delete Node", "Merge with...", "Flag as Incorrect" ✅ IMPLEMENTED (UI only)
4. [ ] Quick filters: Filter by node type
5. [ ] Search bar to find specific nodes

### Phase 6: Shadow Profile Chat ✅ COMPLETE

1. [x] Create chat input component ✅ IMPLEMENTED
2. [x] Example query buttons ✅ IMPLEMENTED
3. [x] Mock natural language responses ✅ IMPLEMENTED (awaiting real graph query)
4. [ ] Highlight matching nodes in graph on query result
5. [ ] Convert user queries to Cypher with LLM

### Phase 7: Data Ingestion Pipeline (N8N + Python)

1. [ ] Create N8N workflow to receive uploaded GDPR PDFs
2. [ ] Create Python script `scripts/ingest_pdf.py` for text extraction
3. [ ] Implement chunking (500 tokens) and embedding via `nomic-embed-text`
4. [ ] Store chunks in Qdrant with source file metadata
5. [ ] LLM triple extraction: entities and relationships to JSON

### Phase 8: Integrity Council (MAKGED)

1. [ ] Create "Forward Agent" that argues FOR a new triple
2. [ ] Create "Backward Agent" that argues AGAINST based on context
3. [ ] Implement voting/consensus mechanism
4. [ ] Only write to Neo4j if consensus reached
5. [ ] Log rejected triples for human review

### Phase 9: Auditor Agent (GIVE)

1. [ ] Create nightly cron job for graph analysis
2. [ ] Identify "Open Triples" - indirect connections between accounts
3. [ ] Generate risk inferences (e.g., "Home address likely compromised")
4. [ ] Create `(:Inference)` nodes with confidence scores
5. [ ] Display high-risk inferences on dashboard as alerts

---

## ⏳ IN PROGRESS / PARTIAL FEATURES

### 10. Identity Builder UI – Advanced Features
**Status:** 🔄 Partial

**Subtasks to Complete:**
1. [ ] Implement `IdentityMiniMap.tsx` for visual chain
2. [ ] Add edit mode to persona cards
3. [ ] Implement delete with orphan warnings
4. [ ] Wire "Save to Graph" checkbox
5. [ ] Auto-filter emails/names by persona

### 11. View Requests – Filtering & Search
**Status:** ✅ Complete

**Completed:**
1. [x] Add `useDebounce` hook ✅ IMPLEMENTED at `hooks/use-debounce.ts`
2. [x] Push `?q=` URL params on search ✅ IMPLEMENTED
3. [x] Create Filter dropdown by status ✅ IMPLEMENTED
4. [x] Wire sort toggle ✅ IMPLEMENTED
5. [x] `SearchToolbar.tsx` component ✅ IMPLEMENTED

### 12. Messages System
**Status:** ✅ Complete (Server Actions)

**Completed:**
1. [x] `getMessages(requestId)` ✅ IMPLEMENTED at `lib/actions/messages.ts`
2. [x] `sendMessage(requestId, content)` ✅ IMPLEMENTED
3. [x] `getUnreadItems()` for ReviewQueue ✅ IMPLEMENTED

### 13. Received Data Actions
**Status:** ✅ Complete (Server Actions)

**Completed:**
1. [x] `getReceivedData(requestId)` ✅ IMPLEMENTED at `lib/actions/data.ts`
2. [x] `getRequestDataVolume(requestId)` ✅ IMPLEMENTED

---

## ❌ NOT STARTED FEATURES

### 12. URL Analyzer – Real N8N Integration
### 13. Email Integration – Backend
### 14. Message/Communication System
### 15. Data Files / Received Data Viewer
### 16. Client-Side Encryption (CryptoJS)
### 17. Request Scheduling
### 18. Data Broker Crawler (Phase 1.1)
### 19. Cookie Banner Interceptor (Phase 1.2)
### 20. OSINT / Breach Check (Phase 1.3)
### 21. Vector Database / Hybrid RAG (Phase 2)
### 22. AI Analyst Swarm (Phase 3)
### 23. Shadow Profile Chatbot (Phase 4.1)
### 24. "Shock Value" Risk Report (Phase 4.2)
### 25. NAS/Home Lab Deployment (Phase 5)

*(See previous version for detailed subtasks on each)*

---

## 📋 Priority Order for Development

1. **Replace Mock #1-5** (Core functionality is broken without real data)
2. **Knowledge Graph Page** (New flagship feature)
3. **Search/Filter in View Requests** (Quick win, UI exists)
4. **Email Backend** (Required for actual request sending)
5. **Real N8N Analyzer Workflow** (Makes wizard useful)

---

## 🔗 Quick Reference: File Locations

| Feature | Key Files |
|---------|-----------|
| Dashboard | `app/dashboard/home/page.tsx`, `components/dashboard/*` |
| Requests | `app/dashboard/requests/page.tsx`, `components/requests/*` |
| Wizard | `app/requests/new/page.tsx`, `components/wizard/*` |
| **Graph Page** | `app/dashboard/graph/page.tsx`, `components/graph/*` ✅ NEW |
| State | `lib/stores/request-store.ts` |
| Actions | `lib/actions/requests.ts`, `lib/actions/dashboard.ts`, `lib/actions/messages.ts` ✅ NEW |
| Database | `lib/db.ts`, `02_DATABASE_SCHEMA.sql` |
| Graph | `lib/graph.ts`, `lib/graph/upsert.ts` |
| Search | `components/requests/SearchToolbar.tsx`, `hooks/use-debounce.ts` ✅ NEW |
| Email | `lib/actions/email-settings.ts` ✅ NEW |
