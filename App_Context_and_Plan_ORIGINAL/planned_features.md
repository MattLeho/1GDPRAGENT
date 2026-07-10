
# PLANNED_FEATURES.md

**Project Vision:** To evolve the local GDPR App from a passive request tool into an active **Personal Data Intelligence System**. This system will hunt for data brokers, autonomously map the user's digital self using Hybrid RAG, and host an AI Analyst Team on local infrastructure (NAS) that employs advanced academic frameworks for reasoning and error detection.

---

## 🏗️ Phase 1: The "Hunter" Module (Automated Discovery)
**Goal:** Active reconnaissance to find companies holding your data without your explicit knowledge.

### 1.1. Data Broker Crawler
*   **Functionality:** An automated agent that scrapes known government registries (e.g., California/Vermont Data Broker Registries) and privacy activist lists (e.g., PrivacyRights.org).
*   **Action:** Automatically adds these entities to the Requests queue with a "High Priority" tag.
*   **Tech:** Python Scrapy or N8N `HTML Extract` nodes.

### 1.2. The "Cookie Banner" Interceptor
*   **Functionality:** A browser extension or headless browser (Puppeteer) agent that visits sites you frequent.
*   **Logic:** It opens the "Manage Cookies" or "Vendor List" modal (IAB TCF framework), parses the hundreds of "Partners" listed there, and cross-references them against your Request Database.
*   **Output:** "You visited `news-site.com`, which exposed your IP to 43 ad-tech vendors. Auto-drafting requests for them."

### 1.3. OSINT Cross-Reference
*   **Functionality:** Uses APIs (like HaveIBeenPwned or DeHashed) to find where your email has appeared in breaches.
*   **Action:** If a breach is found from a specific source, the system assumes that source has your data and initiates a "Delete" or "Access" request.

---

## 🧠 Phase 2: The "Brain" (Hybrid RAG Architecture)
**Goal:** To understand *context* (unstructured text) and *relationships* (structured graph) simultaneously, utilizing the **TCR-QF Framework** to fix sparse data.

### 2.1. Vector Database Integration
*   **New Component:** **Weaviate** or **Qdrant** (Local Docker).
*   **Functionality:** Every privacy policy, email response, and GDPR PDF dump is "chunked" and embedded (using local models like `nomic-embed-text`) and stored for semantic search.

### 2.2. Context-Aware Graph Construction (🔬 Academic Upgrade: TCR)
*   **Concept:** Based on **Triple Context Restoration (TCR)**.
*   **The Problem:** Converting a sentence like "We share your location with marketing partners" into a simple triple `(Company)-[:SHARES]->(Location)` loses the nuance.
*   **The Solution:** When the *Ingestor Agent* creates a triple in Neo4j, it must also attach a **Context Hash** pointing to the exact vector chunk in Qdrant that generated it.
*   **Benefit:** The graph knows *what* is happening; the vector DB knows *why* and *how*.

### 2.3. Query-Driven Feedback Loop (🔬 Academic Upgrade: QF)
*   **Concept:** Based on **Query-Driven Feedback (QF)**.
*   **Workflow:** When you ask a question like "Who has my health data?", the system does not just look at the current Graph.
    1.  **Identify Missing Info:** The LLM analyzes the query against the current Graph.
    2.  **Dynamic Retrieval:** If the Graph is incomplete, it triggers a search in the Vector DB (PDFs) to find missing links.
    3.  **Graph Enrichment:** It temporarily adds these new findings to the Graph *during the reasoning process*.
    4.  **Answer:** Returns a comprehensive answer based on the enriched graph.

---

## 🕵️ Phase 3: The "Analyst Swarm" (Agentic Workflow)
**Goal:** A team of specialized AI agents working in a loop to refine the Knowledge Graph, utilizing **MAKGED** for accuracy and **GIVE** for reasoning.

### 3.1. The Framework
*   **Tech:** **CrewAI** or **AutoGen** (Python microservice running locally).
*   **Input:** Academic papers on Privacy Engineering, Surveillance Capitalism, and Data Inference.

### 3.2. The Agents

#### A. The Ingestor (The Builder)
*   **Role:** Reads incoming GDPR PDF dumps, OCRs them, and splits them into text/triples.

#### B. The Integrity Council (🔬 Academic Upgrade: MAKGED)
*   **Role:** Ensures the Knowledge Graph doesn't contain false data (Hallucination prevention).
*   **Concept:** Based on the **MAKGED Multi-Agent Framework**.
*   **Workflow:** When the Ingestor proposes a new risky link (e.g., "Google knows my Medical History"), it triggers a debate:
    1.  **Forward Agent:** Argues *for* the link based on the PDF text.
    2.  **Backward Agent:** Argues *against* it, checking if the context supports the claim.
    3.  **Voting:** They debate for 2 rounds. If no consensus, a "Judge" agent makes the final call.
*   **Result:** A highly accurate "Digital Twin" free of AI hallucinations.

#### C. The Auditor (The Reasoner)
*   **Role:** Infers hidden risks that aren't explicitly stated in the files.
*   **Concept:** Based on **GIVE (Graph Inspired Veracity Extrapolation)**.
*   **Logic:**
    1.  **Entity Grouping:** It clusters concepts (e.g., 'GPS Coordinates' from Uber + 'Timestamp' from Instagram).
    2.  **Veracity Extrapolation:** It prompts the LLM: "Given these two separate facts, is it possible to infer the User's home address?"
    3.  **Graph Inspiration:** It uses the sparse connections in the graph to "inspire" the LLM to find non-obvious links, effectively modeling how a data broker would profile you.

#### D. The Janitor
*   **Role:** Merges duplicate nodes (Entity Resolution) and archives old data.

---

## 🔮 Phase 4: The "Oracle" (Insights & Shock Value)
**Goal:** To translate raw data into human-understandable risks.

### 4.1. The "Shadow Profile" Chatbot
*   **Interface:** A chat window in the dashboard.
*   **Capabilities:**
    *   "What does Facebook know about my family?" (Queries Graph for Social connections).
    *   "Who knows where I live?" (Queries Graph for Address nodes).

### 4.2. The "Shock Value" Report
*   **Functionality:** A proactive agent that runs nightly "Risk Assessments."
*   **Output:** A "Morning Briefing" on the dashboard.
*   **Example:** "⚠️ **High Risk Alert:** By combining data from *Uber* (Rides) and *Tinder* (Matches), the **GIVE Algorithm** has calculated a 95% probability that an observer can deduce your romantic preferences. This link exists via your shared Email address `john.doe@gmail.com`."

---

## 🏰 Phase 5: Infrastructure (The NAS / Home Lab)
**Goal:** Robust, 24/7 operation without relying on your desktop PC being on.

### 5.1. NAS Deployment Strategy
*   **Hardware:** Synology, Unraid, or a Raspberry Pi 5 Cluster.
*   **Containerization:** The entire `docker-compose.yml` (Next.js, N8N, Neo4j, Postgres, Qdrant, Ollama) moves to the NAS.
*   **Remote Access:** Use **Tailscale** to access your dashboard securely from your phone while away from home.


---

## 📋 Action Plan for Implementation

1.  **Step 1:** Establish the **Neo4j Graph** with the "Hybrid Property" schema (Current Task).
2.  **Step 2:** Deploy **Qdrant** (Vector DB) to `docker-compose` to enable Hybrid RAG.
3.  **Step 3:** Implement the **Crawler Agent** in N8N to populate the "Target List."
4.  **Step 4:** Build the **MAKGED "Integrity Council"** (Python script) to validate new nodes before insertion.
5.  **Step 5:** Build the **GIVE "Auditor"** to run nightly inference jobs on the graph.
6.  **Step 6:** Migrate the full stack to the **NAS/Home Server**.