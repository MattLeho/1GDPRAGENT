# GDPR Automation Agent System

> **Created:** 2025-12-16
> **Purpose:** Technical specifications for N8N AI Agent workflows powering the GDPR Automation App
> **LLM Provider:** Google Gemini (API Key: GEMINI_API_KEY in credentials)

---

## System Overview

The GDPR Automation App uses a multi-agent architecture where specialized AI agents handle different aspects of the GDPR request lifecycle. Each agent is implemented as an N8N workflow that can be triggered via webhooks from the Next.js frontend.

### Agent Communication Flow

```
┌─────────────────────┐
│   Next.js Frontend  │
│ (localhost:3000)    │
└──────────┬──────────┘
           │ POST /api/*
           │ (Webhook Triggers)
           ▼
┌─────────────────────┐
│      N8N Engine     │
│ (localhost:5678)    │
├─────────────────────┤
│ ┌─────────────────┐ │
│ │ Policy Analyzer │ │
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │ Request Drafter │ │
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │ Email Automator │ │
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │ Response Parser │ │
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │ Knowledge Graph │ │
│ │    Ingestor     │ │
│ └─────────────────┘ │
│ ┌─────────────────┐ │
│ │  Shadow Profile │ │
│ │      Oracle     │ │
│ └─────────────────┘ │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│   PostgreSQL DB     │     ┌─────────────────┐
│ (localhost:5432)    │◄────┤  Neo4j Graph    │
└─────────────────────┘     │ (localhost:7687)│
                            └─────────────────┘
```

---

## Agent 1: Policy Analyzer Agent

### Purpose
Analyzes a company's privacy policy URL to extract key information needed for GDPR requests.

### Trigger
- **Webhook:** `POST /webhook/analyze-policy`
- **Called from:** Frontend URL Analyzer component (`/requests/new`)

### Input Schema
```json
{
  "url": "string",           // Company URL (e.g., "spotify.com")
  "requestType": "access | deletion"
}
```

### Processing Steps
1. **HTTP Request Node:** Fetch the privacy policy page
   - Try common paths: `/privacy`, `/privacy-policy`, `/legal/privacy`
   - Follow redirects, handle HTTPS

2. **AI Agent Node (Google Gemini):**
   - **System Prompt:** 
     ```
     You are a GDPR privacy policy expert. Analyze the provided privacy policy text and extract:
     1. Company legal name
     2. Data Protection Officer (DPO) email address
     3. GDPR request submission method (email, web form URL, postal address)
     4. Types of personal data collected
     5. Data retention periods if mentioned
     6. Third parties data is shared with
     
     Return a structured JSON response.
     ```

3. **Respond to Webhook Node:** Return extracted data

### Output Schema
```json
{
  "success": true,
  "data": {
    "company_name": "string",
    "dpo_email": "string | null",
    "request_url": "string | null",
    "postal_address": "string | null",
    "data_types": ["string"],
    "third_parties": ["string"],
    "analysis_summary": "string"
  }
}
```

### N8N Nodes Used
- Webhook Trigger
- HTTP Request (fetch privacy policy)
- Google Gemini Chat Model (analysis)
- AI Agent (structured extraction)
- Respond to Webhook

---

## Agent 2: Request Drafter Agent

### Purpose
Generates a legally compliant GDPR request email based on user input and policy analysis.

### Trigger
- **Webhook:** `POST /webhook/draft-request`
- **Called from:** Frontend when user clicks "Generate Request"

### Input Schema
```json
{
  "requestType": "access | deletion",
  "companyName": "string",
  "dpoEmail": "string",
  "identity": {
    "name": "string (encrypted)",
    "email": "string (encrypted)",
    "additionalFields": [
      {"key": "username", "value": "string (encrypted)"}
    ]
  },
  "scope": {
    "allData": true,
    "specificCategories": ["string"],
    "dateRange": {"start": "ISO date", "end": "ISO date"}
  },
  "context": "string (optional notes)"
}
```

### Processing Steps
1. **Decrypt Identity Data:** Use stored encryption key
2. **AI Agent Node (Google Gemini):**
   - **System Prompt:**
     ```
     You are a legal expert specializing in GDPR (EU) and CCPA (US) data privacy requests.
     
     Generate a formal data subject request email that:
     1. Cites the appropriate legal articles (Article 15 for access, Article 17 for deletion)
     2. Includes all required identity verification information
     3. Is professional but firm in tone
     4. Specifies the 30-day legal deadline for response
     5. Requests confirmation of receipt
     
     The request should be ready to send without modification.
     ```

3. **Store Draft in DB:** Save to `requests` table with status "draft"
4. **Respond to Webhook:** Return draft for user review

### Output Schema
```json
{
  "success": true,
  "requestId": "uuid",
  "draft": {
    "subject": "string",
    "body": "string",
    "to": "email",
    "legalBasis": "Article 15 | Article 17"
  }
}
```

### N8N Nodes Used
- Webhook Trigger
- Code Node (decryption)
- Google Gemini Chat Model
- AI Agent
- Postgres Node (save draft)
- Respond to Webhook

---

## Agent 3: Email Automator Agent

### Purpose
Sends GDPR requests via email and monitors for responses using IMAP.

### Subflows

#### 3A: Email Sender
- **Trigger:** `POST /webhook/send-request`
- **Action:** Send the approved request email via SMTP

#### 3B: Inbox Monitor (Scheduled)
- **Trigger:** Schedule Trigger (every 15 minutes)
- **Action:** Check IMAP inbox for responses from companies

### Email Sender Input
```json
{
  "requestId": "uuid",
  "to": "email",
  "subject": "string",
  "body": "string"
}
```

### Processing Steps (Sender)
1. **Postgres Node:** Fetch request details
2. **Send Email Node:** Use stored IMAP credentials
3. **Postgres Node:** Update status to "sent", record timestamp
4. **Create Follow-up Schedule:** Set reminder for 30-day deadline

### Processing Steps (Monitor)
1. **IMAP Node:** Fetch new emails
2. **Filter Node:** Check if sender matches any active request
3. **AI Agent (Google Gemini):**
   - **System Prompt:**
     ```
     Analyze this email response to a GDPR request. Classify it as:
     1. ACKNOWLEDGMENT - They received the request
     2. VERIFICATION_NEEDED - They need identity verification
     3. PROCESSING - Request is being processed
     4. DATA_ATTACHED - They sent the requested data
     5. REJECTION - Request was denied (extract reason)
     6. COMPLETION - Request is complete
     
     Also extract any attachments or download links.
     ```
4. **Postgres Node:** Create message record, update request status
5. **Conditional:** If DATA_ATTACHED, trigger Ingestor Agent

### N8N Nodes Used
- Webhook/Schedule Trigger
- IMAP Email Read
- Send Email
- Google Gemini Chat Model
- AI Agent
- Postgres Node
- If/Switch Node

---

## Agent 4: Response Parser Agent

### Purpose
Processes data files received from companies (GDPR responses) and extracts structured information.

### Trigger
- **Webhook:** `POST /webhook/parse-response`
- **Called from:** Email Automator when data is attached

### Input Schema
```json
{
  "requestId": "uuid",
  "attachments": [
    {
      "filename": "string",
      "mimeType": "string",
      "content": "base64 string | URL"
    }
  ]
}
```

### Processing Steps
1. **Binary Data Node:** Download/decode attachments
2. **Switch Node:** Route by file type
   - PDF → PDF Parse Node
   - ZIP → Unzip + recursive processing
   - JSON → Direct parse
   - CSV → CSV Parse Node
3. **AI Agent (Google Gemini):**
   - **System Prompt:**
     ```
     Analyze this data export from a company responding to a GDPR request.
     
     Extract and categorize all personal data found:
     1. Contact Information (emails, phones, addresses)
     2. Account Information (usernames, IDs, subscription details)
     3. Activity Data (logs, history, usage patterns)
     4. Financial Data (transactions, payment methods)
     5. Technical Data (IP addresses, device IDs)
     6. Inferred Data (preferences, scores, predictions)
     
     For each data point, note the category and potential privacy risk level (LOW/MEDIUM/HIGH).
     ```

4. **Postgres Node:** Store file metadata in `received_data`
5. **Trigger Ingestor:** Send to Knowledge Graph Ingestor

### Output Schema
```json
{
  "success": true,
  "requestId": "uuid",
  "filesProcessed": 3,
  "totalDataSize": "5.2 MB",
  "categories": {
    "contact": 12,
    "activity": 847,
    "financial": 23
  },
  "highRiskItems": [
    {"type": "IP address", "count": 156}
  ]
}
```

### N8N Nodes Used
- Webhook Trigger
- HTTP Request (download URLs)
- Switch Node
- PDF Parse / Unzip / CSV Parse
- Google Gemini Chat Model
- AI Agent
- Postgres Node

---

## Agent 5: Knowledge Graph Ingestor Agent

### Purpose
Populates the Neo4j Knowledge Graph with extracted data points and relationships.

### Trigger
- **Webhook:** `POST /webhook/ingest-data`
- **Called from:** Response Parser after processing

### Input Schema
```json
{
  "requestId": "uuid",
  "companyName": "string",
  "extractedData": [
    {
      "category": "string",
      "type": "string",
      "value": "string",
      "riskLevel": "LOW | MEDIUM | HIGH",
      "source": "filename"
    }
  ]
}
```

### Processing Steps
1. **AI Agent (Google Gemini) - Triple Extraction:**
   - **System Prompt:**
     ```
     Convert this data into knowledge graph triples.
     
     Rules:
     1. Shared identifiers (emails, phones, IPs, device IDs) become Attribute nodes
     2. Company-specific data becomes DataPoint nodes linked to Company
     3. Identify relationships between entities
     4. Assign risk levels based on sensitivity
     
     Output Cypher MERGE statements for Neo4j.
     ```

2. **Neo4j Node:** Execute Cypher queries
   - MERGE Company node
   - MERGE Account node (if new)
   - MERGE Attribute nodes (shared identifiers)
   - CREATE DataPoint nodes
   - CREATE relationships

3. **Postgres Node:** Update request with graph sync status

### Neo4j Schema Actions
```cypher
// Example generated Cypher
MERGE (c:Company {name: $companyName, domain: $domain})
MERGE (a:Account {id: $accountId})-[:HELD_BY]->(c)
MERGE (attr:Attribute {value: $email, type: 'email'})
MERGE (a)-[:LINKED_TO]->(attr)
CREATE (dp:DataPoint {category: $category, value: $value, riskLevel: $risk})
CREATE (c)-[:COLLECTS]->(dp)
```

### N8N Nodes Used
- Webhook Trigger
- Google Gemini Chat Model
- AI Agent
- Code Node (Cypher generation)
- Neo4j Node (graph writes)
- Postgres Node

---

## Agent 6: Shadow Profile Oracle Agent

### Purpose
Answers natural language questions about the user's digital footprint using the Knowledge Graph.

### Trigger
- **Webhook:** `POST /webhook/shadow-chat`
- **Called from:** Knowledge Graph page chat interface

### Input Schema
```json
{
  "question": "string",
  "sessionId": "string (for memory)"
}
```

### Processing Steps
1. **Simple Memory Node:** Load conversation context

2. **AI Agent (Google Gemini) - Query Generator:**
   - **Tools Available:**
     - `graphQuery`: Execute Cypher against Neo4j
     - `vectorSearch`: Search Qdrant for context (future)
   - **System Prompt:**
     ```
     You are the user's "Shadow Profile Oracle" - an AI that reveals what companies know about them.
     
     You have access to a Knowledge Graph containing:
     - Companies the user has accounts with
     - Personal data each company has collected
     - Shared identifiers linking accounts together
     
     When answering questions:
     1. Query the graph to find relevant data
     2. Explain connections between different data points
     3. Highlight privacy risks (e.g., "Facebook and Google can both identify you via your phone number")
     4. Suggest actionable next steps (e.g., "Consider deleting this account")
     
     Be conversational but informative. Use the graph data as evidence.
     ```

3. **Neo4j Tool Node:** Execute generated Cypher
4. **Respond to Webhook:** Return formatted answer

### Output Schema
```json
{
  "answer": "string",
  "graphNodes": ["nodeId"],  // For highlighting in UI
  "suggestedQueries": ["string"],
  "riskAlerts": [
    {"message": "string", "severity": "LOW | MEDIUM | HIGH"}
  ]
}
```

### N8N Nodes Used
- Webhook Trigger
- Window Buffer Memory
- Google Gemini Chat Model
- AI Agent
- Neo4j Tool (custom)
- Respond to Webhook

---

## Agent 7: Integrity Council Agent (MAKGED)

### Purpose
Validates new Knowledge Graph entries to prevent AI hallucinations using a multi-agent debate framework.

### Trigger
- **Internal Call:** Invoked by Ingestor before graph writes
- **Webhook:** `POST /webhook/validate-triple`

### Input Schema
```json
{
  "triple": {
    "subject": "string",
    "predicate": "string", 
    "object": "string"
  },
  "sourceText": "string",
  "confidence": 0.0-1.0
}
```

### Processing Steps (Parallel Agent Debate)
1. **Forward Agent (Google Gemini):**
   - **System Prompt:**
     ```
     You are the FORWARD AGENT. Your job is to ARGUE IN FAVOR of this proposed knowledge graph triple.
     
     Triple: {subject} --[{predicate}]--> {object}
     Source: {sourceText}
     
     Provide evidence from the source text that supports this relationship.
     Rate your confidence 0-10.
     ```

2. **Backward Agent (Google Gemini):**
   - **System Prompt:**
     ```
     You are the BACKWARD AGENT. Your job is to ARGUE AGAINST this proposed knowledge graph triple.
     
     Triple: {subject} --[{predicate}]--> {object}
     Source: {sourceText}
     
     Look for:
     - Misinterpretations
     - Missing context
     - Alternative explanations
     - Potential hallucinations
     
     Rate your objection strength 0-10.
     ```

3. **Judge Agent (Google Gemini):**
   - Reviews both arguments
   - Makes final decision: ACCEPT / REJECT / NEEDS_REVIEW

4. **Return:** Validated status

### Output Schema
```json
{
  "decision": "ACCEPT | REJECT | NEEDS_REVIEW",
  "forwardScore": 8,
  "backwardScore": 3,
  "reasoning": "string",
  "modifiedTriple": null | {...}
}
```

---

## Credential Configuration

All workflows use the following N8N credential:

### Google Gemini (PaLM) API Credential
- **Name:** `Google Gemini API`
- **Type:** `googleGeminiApi`
- **Host:** `https://generativelanguage.googleapis.com`
- **API Key:** Environment variable `GEMINI_API_KEY`

### PostgreSQL Credential
- **Name:** `GDPR Postgres`
- **Type:** `postgres`
- **Host:** `postgres` (Docker network) or `localhost`
- **Database:** `gdpr_local`
- **User:** From environment `POSTGRES_USER`
- **Password:** From environment `POSTGRES_PASSWORD`

### Neo4j Credential
- **Name:** `GDPR Neo4j`
- **Type:** `neo4j`
- **Host:** `bolt://neo4j:7687` (Docker network)
- **User:** `neo4j`
- **Password:** From environment `NEO4J_PASSWORD`

---

## File Naming Convention

Each agent workflow will be exported as a JSON file in `d:\1GDPRAGENT\agents\`:

| Agent | Filename |
|-------|----------|
| Policy Analyzer | `01_policy_analyzer.json` |
| Request Drafter | `02_request_drafter.json` |
| Email Sender | `03a_email_sender.json` |
| Inbox Monitor | `03b_inbox_monitor.json` |
| Response Parser | `04_response_parser.json` |
| Knowledge Graph Ingestor | `05_kg_ingestor.json` |
| Shadow Profile Oracle | `06_shadow_oracle.json` |
| Integrity Council | `07_integrity_council.json` |

---

## API Endpoints Summary

| Frontend Route | N8N Webhook | Agent |
|---------------|-------------|-------|
| `POST /api/analyze` | `/webhook/analyze-policy` | Policy Analyzer |
| `POST /api/draft` | `/webhook/draft-request` | Request Drafter |
| `POST /api/send` | `/webhook/send-request` | Email Sender |
| `POST /api/parse` | `/webhook/parse-response` | Response Parser |
| `POST /api/ingest` | `/webhook/ingest-data` | KG Ingestor |
| `POST /api/chat/shadow` | `/webhook/shadow-chat` | Shadow Oracle |

---

## Implementation Priority

1. **Phase 1 (Core):** Policy Analyzer + Request Drafter
2. **Phase 2 (Email):** Email Sender + Inbox Monitor
3. **Phase 3 (Data):** Response Parser + KG Ingestor
4. **Phase 4 (Intelligence):** Shadow Oracle + Integrity Council
