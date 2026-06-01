Here is the comprehensive technical design document for the **Knowledge Graph** module.

Save this file as `KNOWLEDGEGRAPH.md` in your project root. This document serves as the blueprint for integrating Neo4j, Qdrant, and the Agentic Swarm into your application.

***

# KNOWLEDGEGRAPH.md

## 1. Project Vision: The "Digital Twin"
The Knowledge Graph is not just a visualization; it is the central "Brain" of the Personal Data Intelligence System. It maps the user's digital existence, linking disparate accounts via shared attributes (emails, IPs, devices) and uncovering hidden data collected by corporations.

It combines **Structured Data** (Neo4j) for relationships with **Unstructured Data** (Qdrant Vector DB) for context, managed by a team of local AI agents.

---

## 2. User Experience (Frontend Integration)

### 2.1. Navigation & Access
*   **Sidebar Update:** Add a new item to `DashboardLayout`:
    *   **Label:** "Data Graph"
    *   **Icon:** `Share2` (Lucide React) or `Network`
    *   **Route:** `/dashboard/graph`

### 2.2. The Graph Page Layout (`/app/dashboard/graph/page.tsx`)
The page is divided into three zones:

1.  **Zone A: The Canvas (70% width)**
    *   **Tech:** `react-force-graph-2d` (or `3d` if preferred).
    *   **Interaction:** Pan/Zoom capable.
    *   **Visuals:**
        *   **User Node:** Central, large, glowing.
        *   **Company Nodes:** Logos as images inside nodes.
        *   **Attribute Nodes:** Small colored dots (Red=IP, Blue=Email, Green=Phone).
        *   **Risk Edges:** Thick red lines for high-risk data flows.
    *   **Events:** `onNodeClick` opens the Detail Panel.

2.  **Zone B: The Inspector Panel (Right Sidebar)**
    *   **Default State:** Shows "Graph Stats" (Total Nodes, High Risk Connections).
    *   **Selected State:** When a node is clicked:
        *   Shows all properties (JSON dump).
        *   Shows "Evidence" (Snippets from the GDPR PDF that created this node).
        *   Actions: "Delete Node", "Merge with...", "Wrong Info? (Trigger MAKGED Agent)".

3.  **Zone C: The "Shadow Profile" Chat (Floating/Bottom)**
    *   **Interface:** Chat input.
    *   **Function:** Allows natural language querying of the graph (e.g., "Show me everyone who has my phone number").

---

## 3. The Hybrid Graph Schema
We utilize the **Adaptable Hybrid Property Graph** model to balance flexibility and connectivity.

### 3.1. Nodes (The Entities)
| Label | Description | Key Properties |
| :--- | :--- | :--- |
| **`User`** | The Root Node (You). | `uid`, `name` |
| **`Persona`** | Contextual identity. | `name` (e.g., "Gamer", "Professional") |
| **`Company`** | The Data Controller. | `name`, `domain`, `privacy_policy_url` |
| **`Account`** | Your specific account. | `username`, `join_date`, `internal_id` |
| **`Attribute`** | **Shared** identifiers. | `value`, `type` (Email, Phone, IP, AdID, DeviceID) |
| **`DataPoint`** | Specific collected data. | `category` (Health, Location), `value`, `risk_level` |
| **`Inference`** | AI-deduced risk. | `prediction`, `confidence_score` |

### 3.2. Relationships (The Links)
*   `(:User)-[:HAS_PERSONA]->(:Persona)`
*   `(:Persona)-[:OWNS_ACCOUNT]->(:Account)`
*   `(:Account)-[:HELD_BY]->(:Company)`
*   `(:Account)-[:LINKED_TO]->(:Attribute)` *(CRITICAL: This creates the map)*
*   `(:Company)-[:COLLECTS]->(:DataPoint)`
*   `(:DataPoint)-[:DERIVED_FROM]->(:Attribute)`
*   `(:Inference)-[:BASED_ON]->(:DataPoint)`

---

## 4. Data Ingestion & Processing Pipeline
How a raw GDPR PDF becomes a node in the graph. This runs on **N8N** (local) or **Python Scripts** on the NAS.

### Step 1: Ingestion & Vectorization
1.  **Input:** PDF File (GDPR Response).
2.  **Processing:** Extract text (OCR if needed).
3.  **Chunking:** Split text into 500-token chunks.
4.  **Vector Store:**
    *   Embed chunk using `nomic-embed-text`.
    *   Save to **Qdrant**: `Payload: { text: "...", source_file: "Amazon_GDPR.pdf", company: "Amazon" }`.
    *   *Purpose:* This enables **Triple Context Restoration (TCR)**. We never lose the source text.

### Step 2: Triple Extraction (The LLM)
1.  **Prompt:** "Extract entities and relationships. If you see an Email, IP, or Phone, mark it as a Shared Attribute."
2.  **Output:** JSON Triples.
    ```json
    [
      { "source": "Amazon", "rel": "COLLECTS", "target": "192.168.1.1", "target_type": "IP" },
      { "source": "Amazon", "rel": "COLLECTS", "target": "Purchase History", "target_type": "DataPoint" }
    ]
    ```

### Step 3: The Integrity Council (MAKGED Framework)
*Before writing to Neo4j, a multi-agent debate occurs to prevent hallucinations.*
1.  **Agent A (Forward):** "I see Amazon collects Heart Rate."
2.  **Agent B (Backward):** "Checking context... That text is actually from a product description of a Fitbit sold on Amazon, not user data."
3.  **Result:** Triple rejected.

### Step 4: Graph Write (Upsert)
1.  **Cypher Query:**
    *   `MERGE` Company.
    *   `MERGE` Account.
    *   If Target is a Shared Attribute (IP/Email), `MERGE` it as a unique node (connecting it to other companies).
    *   If Target is unique data, set it as a Property or DataPoint node.

---

## 5. Agentic Enhancement (The Swarm)
These agents run periodically (cron jobs) to upgrade the graph.

### 5.1. The "Auditor" Agent (GIVE Framework)
*   **Goal:** Veracity Extrapolation.
*   **Logic:** It looks for "Open Triples" (indirect paths).
    *   *Input:* `(:Account {platform: 'Strava'})-[:LINKED_TO]->(:Location)` AND `(:Account {platform: 'Instagram'})-[:LINKED_TO]->(:Photo)`.
    *   *Reasoning:* "Photos often contain EXIF GPS data. Strava contains GPS data. Both accounts share the username 'Runner88'."
    *   *Action:* Create inference node: `(:Inference {desc: 'Home Address Likely Compromised'})`.

### 5.2. The "Oracle" Agent (TCR-QF)
*   **Goal:** answering user questions.
*   **Scenario:** User asks "Does Google know I'm depressed?"
*   **Process:**
    1.  **Graph Lookup:** Checks for `(:DataPoint {value: 'Depression'})`. (Likely fails).
    2.  **Vector Feedback:** Searches Qdrant for "mental health", "mood", "medication" in Google PDFs.
    3.  **Synthesis:** "The Graph doesn't explicitly say 'Depression', but the Vector Search found search history for 'SSRI side effects'. I am updating the graph with an `(:Inference)` node."

---

## 6. Implementation Steps

### Phase 1: Database Setup
1.  **Docker:** Add `neo4j` and `qdrant` services to `docker-compose.yml`.
2.  **Env:** Add `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` to `.env.local`.

### Phase 2: Frontend
1.  Install `neo4j-driver` and `react-force-graph-2d`.
2.  Create `app/dashboard/graph/page.tsx`.
3.  Create `lib/graph/neo4j.ts` (Driver Singleton).
4.  Create API `GET /api/graph/data` to fetch nodes/links for visualization.

### Phase 3: The "Ingestor" Script
1.  Create `scripts/ingest_pdf.py` (using Python allows easier LangChain integration for RAG).
2.  Connect it to the local Qdrant and Neo4j instances.

### Phase 4: Agent Logic
1.  Implement **MAKGED** logic in the python script (using AutoGen or simple prompt chaining).
2.  Implement **GIVE** logic as a nightly analysis script.