```markdown
# MASTER INSTRUCTIONS FOR AI AGENT

## ROLE
You are a Senior Full-Stack Architect and DevOps Engineer. You are building a "Local-First" GDPR Automation App.

## THE GOAL
Build a desktop-like web application that runs entirely on the user's machine using Docker.
- **Frontend:** Next.js 14 (App Router)
- **Backend Logic:** N8N (Self-hosted via Docker)
- **Database:** Supabase (Postgres) or standard Postgres (via Docker)
- **Orchestration:** Docker Compose

## EXECUTION PHASES
DO NOT hallucinate external cloud dependencies. Everything must run on `localhost`.

### PHASE 1: The Skeleton (Docker Compose)
1. Create a `docker-compose.yml` file.
2. It must include 3 services:
   - `postgres` (The database)
   - `n8n` (The automation engine)
   - `nextjs_app` (The frontend)
3. Ensure networks are configured so Next.js can talk to N8N and Postgres directly.
4. Create a `start-app.sh` (Linux) and `start-app.bat` (Windows) script that runs `docker-compose up` and opens `http://localhost:3000`.

### PHASE 2: Database Setup
1. Use `02_DATABASE_SCHEMA.sql` to initialize the Postgres database.
2. Create a migration script or a seed script to ensure tables exist on first startup.

### PHASE 3: Frontend Implementation
1. Initialize the Next.js app in a `./frontend` folder.
2. implement the UI based **strictly** on `03_FRONTEND_COMPONENTS.md`.
3. Use Tailwind CSS and Shadcn/UI.

### PHASE 4: N8N Integration
1. Write a guide on how to import the workflows.
2. Create the API routes in Next.js that proxy requests to the N8N webhook URLs (e.g., `POST /api/analyze` -> `http://n8n:5678/webhook/...`).

## CRITICAL RULES
- **No Cloud Supabase:** Use a local Postgres container.
- **Security:** Do not commit API Keys. Use a `.env` file.
- **Style:** Use "Shadcn/UI" for all components.
```

---

### File 2: `01_ARCHITECTURE.md`

```markdown
# SYSTEM ARCHITECTURE

## 1. Container Structure
The app runs as a cluster of containers.
- **Host:** localhost
- **Network:** `gdpr-net` (Bridge network)

| Service | Internal Port | External Port | Role |
| :--- | :--- | :--- | :--- |
| `db` | 5432 | 5432 | Stores Requests, User Profiles, Messages |
| `n8n` | 5678 | 5678 | Runs the "Agents" (Scraper, Emailer) |
| `app` | 3000 | 3000 | The User Interface (Next.js) |

## 2. Data Flow
1. **User** opens `localhost:3000`.
2. **User** submits a URL in "New Request".
3. **Next.js** sends payload to `http://n8n:5678/webhook/analyze`.
4. **N8N** scrapes web, calls OpenAI, and inserts data into **Postgres (`db`)**.
5. **Next.js** listens to **Postgres** (via polling or Server Actions) to update UI.

## 3. Environment Variables (.env)
```
POSTGRES_USER=admin
POSTGRES_PASSWORD=securepassword
POSTGRES_DB=gdpr_local
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin
OPENAI_API_KEY=sk-... (User must provide)
```
```

---

### File 3: `02_DATABASE_SCHEMA.sql`

```sql
-- ENABLE UUID EXTENSION
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. PROFILES (The User Identities)
CREATE TABLE profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    identity_name TEXT NOT NULL, -- e.g. "Personal", "Work"
    encrypted_name TEXT,         -- AES Encrypted Real Name
    encrypted_email TEXT,        -- AES Encrypted Email
    encrypted_address TEXT,      -- AES Encrypted Address
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 2. REQUESTS (The Core Entity)
CREATE TABLE requests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_name TEXT NOT NULL,
    company_url TEXT,
    status TEXT DEFAULT 'draft', -- draft, processing, sent, replied, complete
    request_type TEXT DEFAULT 'access', -- access, deletion
    data_volume_mb NUMERIC DEFAULT 0,
    deadline_date TIMESTAMP WITH TIME ZONE,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 3. REQUEST_DETAILS (Account specific info for that company)
CREATE TABLE request_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    field_key TEXT,  -- e.g. "username", "phone"
    field_value_encrypted TEXT
);

-- 4. MESSAGES (History)
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id UUID REFERENCES requests(id) ON DELETE CASCADE,
    sender TEXT, -- 'user', 'agent', 'company'
    content TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

### File 4: `03_FRONTEND_COMPONENTS.md`

```markdown
# FRONTEND SPECIFICATIONS
**Tech:** Next.js 14, Tailwind, Lucide Icons, Shadcn/UI, Recharts, React Hook Form.

## 1. HOME PAGE (`/dashboard/home`)
**Layout:** Grid System (2 columns on desktop).

### Component A: Data Volume Chart
- **Library:** `recharts`
- **Type:** Pie Chart / Donut
- **Visuals:** Shows "Total Data Retrieved" in GB.
- **Logic:** Fetch sum of `requests.data_volume_mb` grouped by `company_name`.
- **Interactivity:** Hovering a slice shows a custom black tooltip with GB size. Clicking a slice filters the request list.

### Component B: Task List / Schedule
- **Library:** Shadcn `Card` + `Table`
- **Content:** List of requests where `status` != 'complete'.
- **Visuals:** 
  - "Amazon" | "Scheduled: 12/09/2025" | [View Button]
- **Logic:** Sorted by `deadline_date` ascending.

---

## 2. NEW REQUEST WIZARD (`/requests/new`)
**Layout:** Multi-step wizard using `Zustand` for state.

### Step 1: The Analyzer Input
- **Component:** `UrlAnalyzer.tsx`
- **Input:** Text field for URL (e.g., "spotify.com").
- **Button:** "Analyze Policy" (Sparkles Icon).
- **Action:** Triggers `POST /api/analyze` (calls N8N).
- **Loading:** Shows spinner while N8N scrapes.
- **Result:** Auto-fills the "Company Name" and "DPO Email" fields below.

### Step 2: Identity & Account Panel
- **Component:** `IdentitySelector.tsx`
- **Logic:**
  1. Load profiles from DB.
  2. User selects "My Personal ID".
  3. **Encryption:** All PII (Name, Email) is encrypted client-side using `CryptoJS` before saving to state.
  4. **Dynamic Fields:** "Add Field" button to add specific account info (e.g., "Username: gamer123").

### Step 3: Scope & Submit
- **Controls:** Checkbox for "Delete Data" (Article 17). Date Range Picker.
- **Action:** "Start Request" button sends JSON payload to `POST /api/requests`.

---

## 3. VIEW REQUESTS (`/dashboard/requests`)
**Layout:** Searchable Grid of Cards.

### Component: Request Card
- **Visual:** White card, shadow-sm.
- **Header:** Company Logo (fetch from `logo.clearbit.com/domain.com`) + Name.
- **Status Bar:** Visual timeline. Green dot (Sent) -> Red dot (Deadline).
- **Interaction:** Clicking "Zoom" icon opens a Dialog Modal.

### Component: Detail Modal
- **Tabs:** 
  1. **Timeline:** Chat-like view of emails sent/received.
  2. **Data:** List of files received.
  3. **Context:** Notes/Receipts uploaded by user.
- **Actions:** "Mark Complete", "Export Data".
```

