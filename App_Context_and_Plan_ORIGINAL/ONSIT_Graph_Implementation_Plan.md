# ONSIT & Graph Enhancement - Final Implementation Plan

> **Document Type:** Implementation Plan  
> **Created:** 2026-01-21  
> **Status:** READY FOR APPROVAL

---

## Table of Contents

1. [Overview & User Decisions](#1-overview--user-decisions)
2. [Architecture: Python Intelligence Layer](#2-architecture-python-intelligence-layer)
3. [N8N Agent Translation Strategy](#3-n8n-agent-translation-strategy)
4. [Complete Feature Catalog](#4-complete-feature-catalog)
5. [LLM Provider Configuration](#5-llm-provider-configuration)
6. [Enricher API Selection](#6-enricher-api-selection)
7. [Graph Page Rebuild Strategy](#7-graph-page-rebuild-strategy)
8. [Authenticated Crawling Setup](#8-authenticated-crawling-setup)
9. [Phased Implementation Schedule](#9-phased-implementation-schedule)
10. [Codebase Integration Map](#10-codebase-integration-map)
11. [Verification Plan](#11-verification-plan)

---

## 1. Overview & User Decisions

Based on user responses, the following architectural decisions have been finalized:

| Decision | User Choice | Implementation Impact |
|----------|-------------|----------------------|
| Intelligence Layer | **Python services** (FastAPI + Celery) | Translate N8N agents 05-08, 10 to Python |
| LLM Provider | **Gemini 3 Pro/Flash via API** (no GPU) | Cloud-only, no Ollama |
| Enricher APIs | **Cost-effective combination** | HIBP (free tier) + ipinfo.io + custom |
| Feature Scope | **ALL features from all 4 codebases** | Hybrid approach for overlaps |
| Graph Page | **Fresh rebuild** | Keep accessibility, new implementation |
| Authenticated Crawling | **Optional with Settings UI** | Easy credential management |

---

## 2. Architecture: Python Intelligence Layer

### 2.1 New Service Architecture

```mermaid
flowchart TB
    subgraph Frontend["Next.js Frontend (localhost:3000)"]
        UI[React Components]
        API[API Routes]
    end
    
    subgraph N8N["N8N (localhost:5678) - Orchestration Only"]
        WEBHOOKS[Webhook Triggers]
        NOTIFY[Notifications]
        SIMPLE[Simple Workflows]
    end
    
    subgraph Intelligence["Python Intelligence Layer (NEW)"]
        FASTAPI["FastAPI Service<br>(localhost:8000)"]
        CELERY[Celery Workers]
        
        subgraph Agents["Agent Modules"]
            ONSIT_AGT[ONSIT Discovery]
            EXTRACT_AGT[Extraction Engine]
            GRAPH_AGT[Graph Enrichment]
            VALID_AGT[MAKGED Validator]
        end
    end
    
    subgraph Storage["Storage Layer"]
        PG[(PostgreSQL)]
        NEO[(Neo4j)]
        QD[(Qdrant)]
        REDIS[(Redis)]
    end
    
    UI --> API
    API --> FASTAPI
    API --> WEBHOOKS
    WEBHOOKS --> FASTAPI
    FASTAPI --> CELERY
    CELERY --> Agents
    Agents --> Storage
    FASTAPI --> NOTIFY
```

### 2.2 New Docker Services

Add to `docker-compose.yml`:

```yaml
  redis:
    image: redis:7-alpine
    container_name: gdpr_redis
    restart: always
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - gdpr-net

  intelligence:
    build: ./intelligence
    container_name: gdpr_intelligence
    restart: always
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - GEMINI_MODEL_PRO=gemini-2.0-pro
      - GEMINI_MODEL_FLASH=gemini-2.0-flash
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - NEO4J_URI=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=password
      - QDRANT_URL=http://qdrant:6333
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - neo4j
      - qdrant
      - redis
    volumes:
      - ./intelligence:/app
    command: sh -c "pip install -r requirements.txt && uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
    networks:
      - gdpr-net

  celery-worker:
    build: ./intelligence
    container_name: gdpr_celery
    restart: always
    environment:
      - GOOGLE_API_KEY=${GOOGLE_API_KEY}
      - GEMINI_MODEL_PRO=gemini-2.0-pro
      - GEMINI_MODEL_FLASH=gemini-2.0-flash
      - REDIS_URL=redis://redis:6379/0
      - DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      - NEO4J_URI=bolt://neo4j:7687
      - QDRANT_URL=http://qdrant:6333
    depends_on:
      - redis
      - intelligence
    volumes:
      - ./intelligence:/app
    command: celery -A tasks worker -l INFO -c 4
    networks:
      - gdpr-net
```

### 2.3 New Directory Structure

```
1GDPRAGENT/
├── intelligence/                    # [NEW] Python Intelligence Service
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                      # FastAPI app
│   ├── tasks.py                     # Celery tasks
│   ├── config.py                    # Settings/env
│   │
│   ├── agents/                      # Translated N8N agents
│   │   ├── __init__.py
│   │   ├── kg_ingestor.py          # From 05_kg_ingestor.json
│   │   ├── shadow_oracle.py        # From 06_shadow_oracle.json
│   │   ├── integrity_council.py    # From 07_integrity_council.json
│   │   ├── identity_manager.py     # From 08_identity_manager.json
│   │   └── hybrid_rag.py           # From 10_hybrid_rag.json
│   │
│   ├── onsit/                       # ONSIT Discovery Module
│   │   ├── __init__.py
│   │   ├── crawler.py              # Photon-based crawler
│   │   ├── enrichers/              # Flowsint-style enrichers
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── email.py
│   │   │   ├── username.py
│   │   │   ├── domain.py
│   │   │   ├── breach.py
│   │   │   └── social.py
│   │   └── extractors.py           # Intel extraction patterns
│   │
│   ├── extraction/                  # Graph Extraction Module
│   │   ├── __init__.py
│   │   ├── spo_extractor.py        # AI-KG pipeline
│   │   ├── grounded_extractor.py   # LangExtract integration
│   │   ├── entity_resolver.py      # Deduplication
│   │   ├── inference_engine.py     # Relationship inference
│   │   └── chunker.py              # Document chunking
│   │
│   ├── validators/                  # MAKGED Multi-Agent Validation
│   │   ├── __init__.py
│   │   └── makged.py
│   │
│   ├── llm/                         # LLM Integration
│   │   ├── __init__.py
│   │   ├── gemini.py               # Gemini client
│   │   └── prompts.py              # All prompts
│   │
│   └── api/                         # FastAPI Routes
│       ├── __init__.py
│       ├── onsit.py
│       ├── extraction.py
│       └── graph.py
│
├── frontend/
│   ├── components/
│   │   ├── graph/                   # [REBUILD] New Graph Components
│   │   │   ├── GraphCanvas.tsx     # Fresh implementation
│   │   │   ├── NodeInspector.tsx   # Enhanced panel
│   │   │   ├── ShadowChat.tsx      # AI chat interface
│   │   │   ├── GraphToolbar.tsx    # Controls
│   │   │   ├── GraphLegend.tsx     # Node type legend
│   │   │   └── GraphContext.tsx    # React context
│   │   │
│   │   ├── onsit/                   # [NEW] ONSIT Components
│   │   │   ├── DiscoveryForm.tsx
│   │   │   ├── FindingsList.tsx
│   │   │   ├── FindingCard.tsx
│   │   │   ├── ProgressTracker.tsx
│   │   │   └── RiskBadge.tsx
│   │   │
│   │   └── settings/                # [NEW] Settings Components
│   │       └── CredentialsManager.tsx
│   │
│   ├── app/
│   │   ├── dashboard/
│   │   │   ├── graph/               # [REBUILD] Graph Page
│   │   │   │   └── page.tsx
│   │   │   ├── onsit/               # [NEW] ONSIT Page
│   │   │   │   └── page.tsx
│   │   │   └── settings/            # [NEW] Settings Page
│   │   │       └── page.tsx
│   │   │
│   │   └── api/
│   │       ├── graph/               # [NEW] Graph API
│   │       │   └── route.ts
│   │       ├── onsit/               # [NEW] ONSIT API
│   │       │   └── route.ts
│   │       └── intelligence/        # [NEW] Intelligence Proxy
│   │           └── route.ts
│   │
│   └── lib/
│       ├── intelligence-client.ts   # [NEW] Python service client
│       └── neo4j.ts                 # [ENHANCE] Add new queries
```

---

## 3. N8N Agent Translation Strategy

### 3.1 Agents to Translate to Python

| N8N Agent | File | Python Module | Reason for Translation |
|-----------|------|---------------|----------------------|
| 05_kg_ingestor | `05_kg_ingestor.json` | `agents/kg_ingestor.py` | Complex LLM + Neo4j logic |
| 06_shadow_oracle | `06_shadow_oracle.json` | `agents/shadow_oracle.py` | RAG + Graph queries |
| 07_integrity_council | `07_integrity_council.json` | `validators/makged.py` | Multi-agent debate |
| 08_identity_manager | `08_identity_manager.json` | `agents/identity_manager.py` | Entity resolution |
| 10_hybrid_rag | `10_hybrid_rag.json` | `agents/hybrid_rag.py` | Vector + Graph RAG |

### 3.2 Agents to Keep in N8N

| N8N Agent | File | Reason to Keep |
|-----------|------|----------------|
| 01_policy_analyzer | `01_policy_analyzer.json` | Simple web scraping workflow |
| 02_request_drafter | `02_request_drafter.json` | Template-based generation |
| 03a_email_sender | `03a_email_sender.json` | Email integration |
| 03b_inbox_monitor | `03b_inbox_monitor.json` | Email polling |
| 04_response_parser | `04_response_parser.json` | Document parsing trigger |
| 09_neo4j_query_tool | `09_neo4j_query_tool.json` | Simple query wrapper |

### 3.3 Translation Pattern

**From N8N (07_integrity_council.json):**

```json
{
    "name": "GDPR Integrity Council (MAKGED v2)",
    "nodes": [
        {
            "name": "3a. Head Forward Agent",
            "type": "@n8n/n8n-nodes-langchain.agent",
            "parameters": {
                "model": "gemini-2.5-flash-preview-04-17"
            }
        }
    ]
}
```

**To Python (validators/makged.py):**

```python
from intelligence.llm.gemini import GeminiClient

class MAKGEDValidator:
    def __init__(self):
        self.client = GeminiClient(model="gemini-2.0-flash")
        
    async def validate_triple(self, triple: Triple, context: str) -> ValidationResult:
        # Head Forward Agent
        forward_head = await self.client.complete(
            prompt=FORWARD_AGENT_PROMPT,
            context={"triple": triple, "evidence": context}
        )
        
        # Head Backward Agent  
        backward_head = await self.client.complete(
            prompt=BACKWARD_AGENT_PROMPT,
            context={"triple": triple, "forward_claim": forward_head}
        )
        
        # Tail agents and voting...
        return self._count_votes([forward_head, backward_head, ...])
```

## 4. Complete Feature Catalog

> [!IMPORTANT]
> This section catalogs **ALL** features from all four source codebases. Features are tagged with source and implementation file.

### 4.1 ONSIT Features (ALL from Photon + Flowsint)

#### 4.1.1 Crawler Core Features (from Photon)

| Feature | Source File | Implementation | Priority |
|---------|-------------|----------------|----------|
| Multi-level recursive crawling | `photon.py` | `onsit/crawler.py` | HIGH |
| Thread pool management | `core/flash.py` | `onsit/crawler.py` (Celery integration) | HIGH |
| robots.txt parsing | `core/zap.py` | `onsit/crawler.py` | HIGH |
| sitemap.xml extraction | `core/zap.py` | `onsit/crawler.py` | HIGH |
| Wayback Machine seeds | `--wayback` flag | `onsit/crawler.py` | HIGH |
| DNSDumpster integration | `plugins/dnsdumpster.py` | `onsit/plugins/dnsdumpster.py` | HIGH |
| Custom User-Agent rotation | `core/requester.py` | `onsit/crawler.py` | MEDIUM |
| Proxy support (HTTP/SOCKS5) | `core/utils.py` | `onsit/crawler.py` | MEDIUM |
| Cookie injection | `--cookie` flag | `onsit/crawler.py` | HIGH |
| Custom headers | `--headers` flag | `onsit/crawler.py` | MEDIUM |
| Timeout configuration | `--timeout` flag | `onsit/crawler.py` | LOW |
| Delay between requests | `--delay` flag | `onsit/crawler.py` | MEDIUM |
| URL exclusion patterns | `--exclude` regex | `onsit/crawler.py` | MEDIUM |
| Website cloning/archiving | `core/mirror.py` | `onsit/archiver.py` | LOW |

#### 4.1.2 Intel Detection Patterns (ALL from Photon core/regex.py)

| Pattern Name | What It Detects | ONSIT Use Case | Implementation |
|--------------|-----------------|----------------|----------------|
| `GENERIC_URL` | Standard and defanged URLs | Find all linked resources | `onsit/extractors.py` |
| `BRACKET_URL` | URLs with `[.]` notation | Forums, paste sites | `onsit/extractors.py` |
| `BACKSLASH_URL` | URLs with `\.` notation | Technical documents | `onsit/extractors.py` |
| `HEXENCODED_URL` | Hex-encoded URLs | Malware reports | `onsit/extractors.py` |
| `URLENCODED_URL` | URL-encoded URLs | Web archives | `onsit/extractors.py` |
| `B64ENCODED_URL` | Base64-encoded URLs | Encoded references | `onsit/extractors.py` |
| `IPV4` | IPv4 addresses with defangs | Exposed user IPs | `onsit/extractors.py` |
| `IPV6` | IPv6 addresses | Modern network exposure | `onsit/extractors.py` |
| `EMAIL` | Emails with defangs | All email variations | `onsit/extractors.py` |
| `MD5` | 32-char hex strings | Password breach indicators | `onsit/extractors.py` |
| `SHA1` | 40-char hex strings | Breach data | `onsit/extractors.py` |
| `SHA256` | 64-char hex strings | Modern breach data | `onsit/extractors.py` |
| `SHA512` | 128-char hex strings | Secure hash leaks | `onsit/extractors.py` |
| `CREDIT_CARD` | 16-digit patterns (Luhn) | Financial exposure | `onsit/extractors.py` |
| `YARA_PARSE` | YARA rule patterns | User in threat reports | `onsit/extractors.py` |
| `rentropy` | High-entropy strings | API keys, secrets | `onsit/extractors.py` |

#### 4.1.3 Data Output Categories (ALL from Photon)

| Category | Variable | Contents | Storage Target | Implementation |
|----------|----------|----------|----------------|----------------|
| `internal` | URLs | Same-domain pages | PostgreSQL + crawl queue | `onsit/storage.py` |
| `external` | URLs | External links | Neo4j relationships | `onsit/storage.py` |
| `files` | URLs | Document/media files | Download queue | `onsit/storage.py` |
| `intel` | Tuples | Email, social, credentials | Graph nodes | `onsit/storage.py` |
| `scripts` | URLs | JavaScript files | Endpoint extraction queue | `onsit/storage.py` |
| `endpoints` | Strings | API endpoints from JS | API mapping table | `onsit/storage.py` |
| `fuzzable` | URLs | URLs with parameters | Vulnerability notes | `onsit/storage.py` |
| `keys` | Strings | High-entropy secrets | Security alerts | `onsit/storage.py` |
| `robots` | URLs | From robots.txt | Site structure | `onsit/storage.py` |
| `subdomains` | Domains | Discovered subdomains | Domain graph | `onsit/storage.py` |
| `custom` | Strings | Custom regex matches | Flexible extraction | `onsit/storage.py` |
| `failed` | URLs | Failed requests | Retry queue | `onsit/storage.py` |

#### 4.1.4 Photon Plugins to Port

| Plugin | Source File | Functionality | Implementation | Priority |
|--------|-------------|---------------|----------------|----------|
| `find_subdomains` | `plugins/find_subdomains.py` | Subdomain enumeration via DNS brute + CT logs | `onsit/plugins/subdomains.py` | HIGH |
| `dnsdumpster` | `plugins/dnsdumpster.py` | DNS map visualization | `onsit/plugins/dnsdumpster.py` | HIGH |
| `exporter` | `plugins/exporter.py` | CSV/JSON export of results | `onsit/plugins/exporter.py` | MEDIUM |

#### 4.1.5 Flowsint Entity Types (ALL from flowsint-types)

| Entity Type | Properties | Graph Label | Use in ONSIT | Implementation |
|-------------|------------|-------------|--------------|----------------|
| `Domain` | name, registrar, created_date | `:Domain` | Website ownership | `onsit/models.py` |
| `IP` | address, asn, geo_location | `:IP` | Network mapping | `onsit/models.py` |
| `ASN` | number, name, country | `:ASN` | Infrastructure tracking | `onsit/models.py` |
| `CIDR` | range, size | `:CIDR` | IP range analysis | `onsit/models.py` |
| `Email` | address, provider | `:Email` | Identity pivot | `onsit/models.py` |
| `Phone` | number, country_code | `:Phone` | Identity pivot | `onsit/models.py` |
| `Username` | value, platform | `:Username` | Social media tracking | `onsit/models.py` |
| `Individual` | name, aliases | `:Individual` | Person of interest | `onsit/models.py` |
| `Organization` | name, type | `:Organization` | Company tracking | `onsit/models.py` |
| `Website` | url, title, technologies | `:Website` | Web presence | `onsit/models.py` |
| `SocialProfile` | platform, url, username | `:SocialProfile` | Public profiles | `onsit/models.py` |
| `Credential` | type, value, source | `:Credential` | Exposed credentials | `onsit/models.py` |
| `CryptoWallet` | address, type | `:CryptoWallet` | Blockchain activity | `onsit/models.py` |
| `Transaction` | hash, amount, timestamp | `:Transaction` | Financial tracking | `onsit/models.py` |
| `NFT` | contract, token_id | `:NFT` | Digital asset ownership | `onsit/models.py` |

#### 4.1.6 Enricher Catalog (ALL from flowsint-enrichers)

##### Domain Enrichers

| Enricher | Input → Output | API/Tool | Implementation |
|----------|----------------|----------|----------------|
| Reverse DNS | IP → Domains | DNS queries | `enrichers/domain.py` |
| DNS Resolution | Domain → IPs | DNS queries (A, AAAA, MX) | `enrichers/domain.py` |
| Subdomain Discovery | Domain → Subdomains | DNS brute + CT logs | `enrichers/domain.py` |
| WHOIS Lookup | Domain → Registration | WHOIS protocol | `enrichers/domain.py` |
| Domain to Website | Domain → Website | HTTP probe | `enrichers/domain.py` |
| Domain to Root | Domain → Root Domain | TLD extraction (PSL) | `enrichers/domain.py` |
| Domain to ASN | Domain → ASN | IP → ASN lookup | `enrichers/domain.py` |
| Domain History | Domain → Historical | Wayback, SecurityTrails | `enrichers/domain.py` |

##### IP Enrichers

| Enricher | Input → Output | API/Tool | Implementation |
|----------|----------------|----------|----------------|
| IP Information | IP → GeoIP data | MaxMind, ipinfo.io | `enrichers/ip.py` |
| IP to ASN | IP → ASN | RIPE, BGP tables | `enrichers/ip.py` |
| IP Reputation | IP → Risk score | VirusTotal, AbuseIPDB | `enrichers/ip.py` |

##### ASN Enrichers

| Enricher | Input → Output | API/Tool | Implementation |
|----------|----------------|----------|----------------|
| ASN to CIDRs | ASN → IP ranges | RIPE, BGPView | `enrichers/asn.py` |
| ASN Info | ASN → Org details | RIPEstat | `enrichers/asn.py` |

##### CIDR Enrichers

| Enricher | Input → Output | API/Tool | Implementation |
|----------|----------------|----------|----------------|
| CIDR to IPs | CIDR → IP list | Calculation | `enrichers/cidr.py` |
| CIDR Scan | CIDR → Active hosts | Port scan | `enrichers/cidr.py` |

##### Social Media Enrichers

| Enricher | Input → Output | API/Tool | Implementation |
|----------|----------------|----------|----------------|
| Maigret | Username → Profiles | Maigret lib (500+ platforms) | `enrichers/username.py` |
| Sherlock | Username → Profiles | Sherlock lib | `enrichers/username.py` |
| Platform-specific | Username → Profile | Per-platform API | `enrichers/social.py` |

##### Email Enrichers

| Enricher | Input → Output | API/Tool | Implementation |
|----------|----------------|----------|----------------|
| Gravatar | Email → Avatar/Profile | Gravatar API | `enrichers/email.py` |
| Breach Check | Email → Breaches | HIBP API | `enrichers/breach.py` |
| Email to Domains | Email → Domains | Reverse lookup | `enrichers/email.py` |
| Email Validation | Email → Valid/Invalid | SMTP check | `enrichers/email.py` |
| Email Provider | Email → Provider info | MX lookup | `enrichers/email.py` |

##### Phone Enrichers

| Enricher | Input → Output | API/Tool | Implementation |
|----------|----------------|----------|----------------|
| Phone Breach Check | Phone → Breaches | HIBP API | `enrichers/phone.py` |
| Phone Lookup | Phone → Carrier/Location | Carrier APIs | `enrichers/phone.py` |
| CallerID | Phone → Name | Various APIs | `enrichers/phone.py` |

##### Organization Enrichers

| Enricher | Input → Output | API/Tool | Implementation |
|----------|----------------|----------|----------------|
| Org to ASN | Org → ASNs | RIPEstat | `enrichers/org.py` |
| Org to Domains | Org → Domains | Reverse WHOIS | `enrichers/org.py` |
| Org Info | Org → Details | Company APIs | `enrichers/org.py` |

##### Cryptocurrency Enrichers

| Enricher | Input → Output | API/Tool | Implementation |
|----------|----------------|----------|----------------|
| Wallet Transactions | Wallet → Transactions | Blockchain APIs | `enrichers/crypto.py` |
| Wallet to NFTs | Wallet → NFTs | OpenSea, etc. | `enrichers/crypto.py` |
| Wallet Balance | Wallet → Balance | Blockchain APIs | `enrichers/crypto.py` |

##### Website Enrichers

| Enricher | Input → Output | API/Tool | Implementation |
|----------|----------------|----------|----------------|
| Website Crawler | URL → Structure | Photon-style | `enrichers/website.py` |
| Website to Links | URL → Links | HTML parsing | `enrichers/website.py` |
| Website to Domain | URL → Domain | URL parsing | `enrichers/website.py` |
| Webtracker Detection | URL → Trackers | Pattern matching | `enrichers/website.py` |
| Website to Text | URL → Text content | HTML to text | `enrichers/website.py` |
| Technology Detection | URL → Tech stack | Wappalyzer-style | `enrichers/website.py` |

##### Individual Enrichers

| Enricher | Input → Output | API/Tool | Implementation |
|----------|----------------|----------|----------------|
| Individual to Org | Person → Organizations | LinkedIn, etc. | `enrichers/individual.py` |
| Individual to Domains | Person → Domains | WHOIS search | `enrichers/individual.py` |

##### Integration Enrichers

| Enricher | Input → Output | Tool | Implementation |
|----------|----------------|------|----------------|
| N8N Connector | Any → Workflow | N8N webhook | `enrichers/n8n.py` |

#### 4.1.7 Flowsint Core Infrastructure

| Component | Purpose | Our Adaptation | Implementation |
|-----------|---------|----------------|----------------|
| Vault | Secure credential storage | Store API keys for enrichers | `onsit/vault.py` |
| Orchestrator | Task coordination | Coordinate enricher chains | `onsit/orchestrator.py` |
| Celery Tasks | Async job processing | Already planned for ONSIT | `tasks.py` |
| Event System | Real-time updates | WebSocket to frontend | `api/websocket.py` |
| Database adapters | Neo4j + PostgreSQL | Same stack, share code | `db/adapters.py` |

---

### 4.2 Graph Extraction Features (ALL from AI-KG + LangExtract)

#### 4.2.1 AI-Knowledge-Graph Extraction Pipeline

| Module | Source File | Functions | Implementation |
|--------|-------------|-----------|----------------|
| `text_utils` | `text_utils.py` | `chunk_text()` with overlap | `extraction/chunker.py` |
| `llm` | `llm.py` | `call_llm()`, `extract_json_from_text()` | `llm/gemini.py` |
| `prompts` | `prompts.py` | All extraction prompts | `llm/prompts.py` |
| `entity_standardization` | `entity_standardization.py` | `standardize_entities()`, `_resolve_entities_with_llm()` | `extraction/entity_resolver.py` |
| `main` | `main.py` | Full pipeline orchestration | `extraction/pipeline.py` |
| `config` | `config.py` | TOML config loading | `config.py` |
| `visualization` | `visualization.py` | PyVis graph generation | `extraction/visualizer.py` |

#### 4.2.2 AI-KG Prompts to Port

| Prompt Type | Purpose | Customization Needed | Implementation |
|-------------|---------|---------------------|----------------|
| SPO Extraction | Extract subject-predicate-object | Add GDPR-specific predicates | `llm/prompts.py` |
| Entity Resolution | Deduplicate similar entities | Add email/phone normalization | `llm/prompts.py` |
| Relationship Inference | Cross-community linking | Privacy-focused relationship types | `llm/prompts.py` |
| Within-Community | Dense local relationships | Data sharing relationships | `llm/prompts.py` |

#### 4.2.3 Graph Analysis Features (from AI-KG)

| Feature | Algorithm | Use in GDPR App | Implementation |
|---------|-----------|-----------------|----------------|
| Community Detection | Louvain algorithm | Group related companies | `extraction/inference_engine.py` |
| Centrality Metrics | Degree, betweenness, eigenvector | Identify key data brokers | `extraction/inference_engine.py` |
| Transitive Inference | If A→B→C then A→C | Infer data sharing chains | `extraction/inference_engine.py` |
| Lexical Similarity | Semantic entity matching | Link similar entities | `extraction/entity_resolver.py` |
| Disconnected Community Linking | Bridge graph islands | Connect ONSIT to GDPR data | `extraction/inference_engine.py` |

#### 4.2.4 AI-KG Visualization Features

| Feature | Description | Implementation |
|---------|-------------|----------------|
| Color-coded communities | Node colors by cluster | `extraction/visualizer.py` |
| Size by importance | Centrality-based sizing | `extraction/visualizer.py` |
| Solid vs dashed edges | Original vs inferred | `extraction/visualizer.py` |
| Interactive controls | Zoom, pan, hover, filter | `extraction/visualizer.py` |
| Dark/Light mode | Theme switching | `extraction/visualizer.py` |

---

### 4.3 LangExtract Integration (ALL Features)

#### 4.3.1 LangExtract Core Modules (Lazy-loaded)

| Module | Path | Key Functions | Use Case | Implementation |
|--------|------|---------------|----------|----------------|
| `annotation` | `langextract.annotation` | Annotation classes | Result structure | `extraction/grounded_extractor.py` |
| `chunking` | `langextract.chunking` | Document chunking | Long GDPR PDFs | `extraction/chunker.py` |
| `data` | `langextract.data` | `ExampleData`, `Extraction` | Define extraction tasks | `extraction/grounded_extractor.py` |
| `exceptions` | `langextract.exceptions` | Error handling | Graceful failures | `extraction/grounded_extractor.py` |
| `factory` | `langextract.factory` | Model creation | LLM instantiation | `llm/gemini.py` |
| `inference` | `langextract.inference` | Inference pipeline | Run extraction | `extraction/grounded_extractor.py` |
| `io` | `langextract.io` | File I/O, JSONL export | Result persistence | `extraction/storage.py` |
| `progress` | `langextract.progress` | Progress tracking | UI feedback | `api/websocket.py` |
| `prompting` | `langextract.prompting` | Prompt construction | Task definition | `llm/prompts.py` |
| `providers` | `langextract.providers` | LLM providers | Multi-model support | `llm/gemini.py` |
| `resolver` | `langextract.resolver` | Entity resolution | Deduplication | `extraction/entity_resolver.py` |
| `schema` | `langextract.schema` | Output schema | Structured results | `extraction/schemas.py` |
| `tokenizer` | `langextract.tokenizer` | Token counting | Chunk sizing | `extraction/chunker.py` |
| `visualization` | `langextract.visualization` | HTML visualization | Interactive review | `extraction/visualizer.py` |
| `plugins` | `langextract.plugins` | Extension system | Custom extractors | `extraction/plugins/` |

#### 4.3.2 LangExtract Extraction Parameters

| Parameter | Type | Description | Our Default |
|-----------|------|-------------|-------------|
| `text_or_documents` | str/list | Input text or URLs | PDF text content |
| `prompt_description` | str | Task description | GDPR-specific prompt |
| `examples` | list[ExampleData] | Few-shot examples | GDPR training examples |
| `model_id` | str | Model identifier | `gemini-2.0-flash` |
| `extraction_passes` | int | Number of passes | `3` (for recall) |
| `max_workers` | int | Parallel threads | `20` |
| `max_char_buffer` | int | Context window | Model-dependent |
| `fence_output` | bool | Use code fences | `False` (Gemini) |
| `use_schema_constraints` | bool | Enforce output schema | `True` |
| `language_model_params` | dict | Provider params | Rate limiting config |

#### 4.3.3 LangExtract Visualization API

```python
# Save extractions to JSONL
lx.io.save_annotated_documents([result], output_name="gdpr_extractions.jsonl")

# Generate interactive HTML with source highlighting
html_content = lx.visualize("gdpr_extractions.jsonl")

# Export to static file for embedding
with open("extraction_report.html", "w") as f:
    f.write(html_content)
```

---

### 4.4 Hybrid Approach for Overlapping Features

| Feature | AI-KG | LangExtract | Hybrid Strategy |
|---------|-------|-------------|-----------------|
| **Chunking** | 200 words + overlap | Token-based | Use LangExtract tokenizer for accuracy |
| **Entity Extraction** | SPO triples | Schema-enforced | Primary: LangExtract, fallback: SPO |
| **Entity Resolution** | LLM deduplication | Built-in resolver | Combine both for higher accuracy |
| **Visualization** | PyVis static | Interactive HTML | Primary: Interactive, export: PyVis |
| **Inference** | Transitive + Louvain | None | Use AI-KG inference engine |

---

### 4.5 Validation Features (MAKGED from planned_features.md)

| Component | Role | Implementation |
|-----------|------|----------------|
| Head Forward Agent | Argues FOR triple validity based on source | `validators/makged.py` |
| Head Backward Agent | Argues AGAINST with counter-evidence | `validators/makged.py` |
| Tail Forward Agent | Second opinion FOR (different perspective) | `validators/makged.py` |
| Tail Backward Agent | Second opinion AGAINST | `validators/makged.py` |
| Vote Counter | Majority voting with confidence scores | `validators/makged.py` |
| Judge Agent | Tiebreaker for edge cases (uses Pro model) | `validators/makged.py` |

---

## 5. LLM Provider Configuration

### 5.1 Gemini API Setup

```env
# .env additions
GOOGLE_API_KEY=your_gemini_api_key

# Model configuration
GEMINI_MODEL_PRO=gemini-2.0-pro         # Complex reasoning
GEMINI_MODEL_FLASH=gemini-2.0-flash     # Fast tasks
```

### 5.2 Task-to-Model Mapping

| Task | Model | Reasoning |
|------|-------|-----------|
| SPO Triple Extraction | Gemini 2.0 Flash | Fast, structured output |
| Entity Resolution | Gemini 2.0 Flash | Semantic similarity |
| MAKGED Debate | Gemini 2.0 Flash | Quick iterations |
| Relationship Inference | Gemini 2.0 Pro | Complex reasoning |
| Shadow Oracle Chat | Gemini 2.0 Pro | User-facing quality |
| Risk Assessment | Gemini 2.0 Pro | Critical decisions |

### 5.3 Gemini Client Implementation

```python
# intelligence/llm/gemini.py
import google.generativeai as genai
from typing import Optional

class GeminiClient:
    def __init__(self, model: str = "gemini-2.0-flash"):
        genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
        self.model = genai.GenerativeModel(model)
    
    async def complete(
        self, 
        prompt: str, 
        context: dict = None,
        structured_output: bool = False
    ) -> str:
        formatted = self._format_prompt(prompt, context)
        response = await self.model.generate_content_async(formatted)
        return response.text
    
    async def extract_structured(
        self, 
        prompt: str, 
        schema: dict, 
        text: str
    ) -> dict:
        """LangExtract-style structured extraction"""
        response = await self.model.generate_content_async(
            formatted_prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        return json.loads(response.text)
```

---

## 6. Enricher API Selection

### 6.1 Recommended API Stack (Cost-Optimized)

| Purpose | API | Cost | Implementation |
|---------|-----|------|----------------|
| **Email Breach Check** | HaveIBeenPwned | Free (rate-limited) | `enrichers/breach.py` |
| **IP Geolocation** | ipinfo.io | Free (50k/month) | `enrichers/ip.py` |
| **Username Search** | Maigret (self-hosted) | Free | `enrichers/username.py` |
| **Domain WHOIS** | python-whois | Free | `enrichers/domain.py` |
| **DNS** | dnspython | Free | `enrichers/domain.py` |
| **Gravatar** | Gravatar API | Free | `enrichers/email.py` |

### 6.2 Optional Premium APIs (User-Configurable)

| Purpose | API Options | Cost | Enable via Settings |
|---------|-------------|------|---------------------|
| Enhanced Breach Data | DeHashed | Paid | Settings page toggle |
| IP Reputation | VirusTotal | Free tier | Settings page toggle |
| Advanced DNS Intel | SecurityTrails | Paid | Settings page toggle |

### 6.3 API Key Storage

```sql
-- Add to 02_DATABASE_SCHEMA.sql
CREATE TABLE api_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider TEXT NOT NULL,  -- 'hibp', 'virustotal', etc.
    api_key_encrypted TEXT NOT NULL,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## 7. Graph Page Rebuild Strategy

### 7.1 Current vs New Implementation

| Aspect | Current (`GraphCanvas.tsx`) | New Implementation |
|--------|---------------------------|-------------------|
| Lines of Code | 300 | ~500+ (more features) |
| Library | react-force-graph-2d/3d | Same + enhancements |
| Node Types | 8 hardcoded | Dynamic from schema |
| Filtering | Type only | Type, source, date, risk |
| ONSIT Integration | None | Full ONSIT node support |
| Inspector | Basic properties | Full evidence panel |
| Chat | None | Shadow Profile Chat |
| Clustering | None | Community visualization |
| Edge Types | Single style | Solid/dashed for inferred |

### 7.2 New Graph Page Features

```typescript
// New props for enhanced GraphCanvas
interface GraphCanvasProps {
    onNodeClick: (node: GraphNode) => void;
    selectedNodeId?: string | null;
    // NEW: ONSIT integration
    showONSITLayer: boolean;
    showGDPRLayer: boolean;
    showInferences: boolean;
    // NEW: Clustering
    highlightCommunity?: string;
    // NEW: Time filtering
    dateRange?: [Date, Date];
}
```

### 7.3 New Node Types for ONSIT

```typescript
// Add to nodeColors
const nodeColors: Record<string, string> = {
    // Existing...
    User: '#9333ea',
    Company: '#22c55e',
    // NEW ONSIT types
    ONSITFinding: '#f97316',      // Orange
    SocialProfile: '#ec4899',     // Pink
    BreachRecord: '#ef4444',      // Red (high risk)
    PublicDocument: '#8b5cf6',    // Purple
    CryptoWallet: '#6366f1',      // Indigo
    Credential: '#dc2626',        // Dark red (critical)
};
```

### 7.4 Route Compatibility

The new graph page will be accessible at the **same route** (`/dashboard/graph`) but with enhanced functionality:

```typescript
// frontend/app/dashboard/graph/page.tsx
// Same route, completely new implementation
export default function GraphPage() {
    // New implementation using rebuilt components
}
```

---

## 8. Authenticated Crawling Setup

### 8.1 Settings Page Design

```typescript
// frontend/app/dashboard/settings/page.tsx
export default function SettingsPage() {
    return (
        <div className="space-y-8">
            <section>
                <h2>ONSIT Credentials</h2>
                <p>Add credentials to crawl your own accounts</p>
                <CredentialsManager />
            </section>
            
            <section>
                <h2>API Keys</h2>
                <p>Configure enricher API access</p>
                <APIKeyManager />
            </section>
        </div>
    );
}
```

### 8.2 Credential Types Supported

| Platform Type | Auth Method | Storage |
|---------------|-------------|---------|
| Generic Website | Cookie string | Encrypted in DB |
| Generic Website | Session token | Encrypted in DB |
| Social Media | OAuth token | Encrypted in DB |
| Email Provider | App password | Encrypted in DB |

### 8.3 Security Implementation

```sql
-- Encrypted credential storage
CREATE TABLE user_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    platform_name TEXT NOT NULL,
    platform_url TEXT,
    credential_type TEXT,  -- 'cookie', 'token', 'oauth', 'password'
    credential_encrypted TEXT NOT NULL,  -- AES-256 encrypted
    last_used TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

```python
# intelligence/onsit/auth.py
from cryptography.fernet import Fernet

class CredentialManager:
    def __init__(self):
        self.fernet = Fernet(os.environ["CREDENTIAL_KEY"])
    
    def encrypt(self, credential: str) -> str:
        return self.fernet.encrypt(credential.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        return self.fernet.decrypt(encrypted.encode()).decode()
```

---

## 9. Phased Implementation Schedule

### Phase 1: Infrastructure (Week 1)

| Task | Files | Priority |
|------|-------|----------|
| Add Redis to docker-compose | `docker-compose.yml` | HIGH |
| Create intelligence service skeleton | `intelligence/main.py`, `Dockerfile` | HIGH |
| Set up Celery worker | `intelligence/tasks.py` | HIGH |
| Add Gemini client | `intelligence/llm/gemini.py` | HIGH |
| Update .env with new variables | `.env` | HIGH |

### Phase 2: N8N Translation (Week 2)

| Task | Files | Priority |
|------|-------|----------|
| Translate kg_ingestor | `intelligence/agents/kg_ingestor.py` | HIGH |
| Translate integrity_council (MAKGED) | `intelligence/validators/makged.py` | HIGH |
| Translate shadow_oracle | `intelligence/agents/shadow_oracle.py` | MEDIUM |
| Translate hybrid_rag | `intelligence/agents/hybrid_rag.py` | MEDIUM |
| Create FastAPI endpoints | `intelligence/api/*.py` | HIGH |

### Phase 3: ONSIT Engine (Week 3)

| Task | Files | Priority |
|------|-------|----------|
| Port Photon crawler core | `intelligence/onsit/crawler.py` | HIGH |
| Port regex patterns | `intelligence/onsit/extractors.py` | HIGH |
| Implement email enricher | `intelligence/onsit/enrichers/email.py` | HIGH |
| Implement username enricher | `intelligence/onsit/enrichers/username.py` | HIGH |
| Implement domain enricher | `intelligence/onsit/enrichers/domain.py` | MEDIUM |
| Implement breach enricher | `intelligence/onsit/enrichers/breach.py` | HIGH |

### Phase 4: Extraction Engine (Week 4)

| Task | Files | Priority |
|------|-------|----------|
| Port AI-KG chunker | `intelligence/extraction/chunker.py` | HIGH |
| Port SPO extractor | `intelligence/extraction/spo_extractor.py` | HIGH |
| Integrate LangExtract | `intelligence/extraction/grounded_extractor.py` | MEDIUM |
| Port entity resolver | `intelligence/extraction/entity_resolver.py` | HIGH |
| Port inference engine | `intelligence/extraction/inference_engine.py` | MEDIUM |

### Phase 5: Graph Page Rebuild (Week 5)

| Task | Files | Priority |
|------|-------|----------|
| Create new GraphCanvas | `frontend/components/graph/GraphCanvas.tsx` | HIGH |
| Create NodeInspector | `frontend/components/graph/NodeInspector.tsx` | HIGH |
| Create ShadowChat | `frontend/components/graph/ShadowChat.tsx` | MEDIUM |
| Create GraphToolbar | `frontend/components/graph/GraphToolbar.tsx` | MEDIUM |
| Wire up API routes | `frontend/app/api/graph/route.ts` | HIGH |

### Phase 6: ONSIT Frontend (Week 6)

| Task | Files | Priority |
|------|-------|----------|
| Create ONSIT page | `frontend/app/dashboard/onsit/page.tsx` | HIGH |
| Create DiscoveryForm | `frontend/components/onsit/DiscoveryForm.tsx` | HIGH |
| Create FindingsList | `frontend/components/onsit/FindingsList.tsx` | HIGH |
| Create ProgressTracker | `frontend/components/onsit/ProgressTracker.tsx` | MEDIUM |

### Phase 7: Settings & Polish (Week 7)

| Task | Files | Priority |
|------|-------|----------|
| Create Settings page | `frontend/app/dashboard/settings/page.tsx` | MEDIUM |
| Create CredentialsManager | `frontend/components/settings/CredentialsManager.tsx` | MEDIUM |
| Add sidebar navigation | `frontend/components/layout/Sidebar.tsx` | MEDIUM |
| End-to-end testing | `tests/` | HIGH |

---

## 10. Codebase Integration Map

### 10.1 API Route Wiring

```typescript
// frontend/app/api/intelligence/route.ts
export async function POST(req: Request) {
    const body = await req.json();
    
    // Proxy to Python intelligence service
    const response = await fetch('http://intelligence:8000/api/...');
    return Response.json(await response.json());
}
```

### 10.2 Database Connections

| Service | Databases Used | Connection |
|---------|---------------|------------|
| Next.js | PostgreSQL | Direct via Prisma |
| N8N | PostgreSQL, Neo4j | HTTP API + Direct |
| Intelligence | PostgreSQL, Neo4j, Qdrant, Redis | All direct |

### 10.3 Event Flow: ONSIT Discovery

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant IntelAPI as Intelligence API
    participant Celery
    participant Enrichers
    participant Neo4j
    participant N8N
    
    User->>Frontend: Submit identity
    Frontend->>IntelAPI: POST /onsit/discover
    IntelAPI->>Celery: Queue discovery task
    IntelAPI-->>Frontend: Return task_id
    
    loop For each enricher
        Celery->>Enrichers: Run enricher
        Enrichers->>Neo4j: Store findings
    end
    
    Celery->>N8N: Webhook: discovery complete
    N8N->>User: Send notification
    Frontend->>IntelAPI: Poll for results
    IntelAPI-->>Frontend: Return findings
```

### 10.4 Event Flow: GDPR PDF Processing

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant N8N
    participant IntelAPI as Intelligence API
    participant Celery
    participant MAKGED
    participant Neo4j
    
    User->>Frontend: Upload GDPR PDF
    Frontend->>N8N: POST /webhook/process-pdf
    N8N->>IntelAPI: POST /extract/pdf
    IntelAPI->>Celery: Queue extraction
    
    Celery->>Celery: Chunk document
    Celery->>Celery: Extract SPO triples
    
    loop For each triple
        Celery->>MAKGED: Validate triple
        alt Valid
            MAKGED->>Neo4j: MERGE triple
        else Invalid
            MAKGED->>Neo4j: Log rejection
        end
    end
    
    Celery->>N8N: Webhook: extraction complete
    N8N->>User: Notification
```

---

## 11. Verification Plan

### 11.1 Unit Tests

| Component | Test File | Run Command |
|-----------|-----------|-------------|
| Gemini Client | `intelligence/tests/test_gemini.py` | `pytest intelligence/tests/test_gemini.py` |
| Crawler | `intelligence/tests/test_crawler.py` | `pytest intelligence/tests/test_crawler.py` |
| Enrichers | `intelligence/tests/test_enrichers.py` | `pytest intelligence/tests/test_enrichers.py` |
| SPO Extractor | `intelligence/tests/test_spo.py` | `pytest intelligence/tests/test_spo.py` |
| MAKGED | `intelligence/tests/test_makged.py` | `pytest intelligence/tests/test_makged.py` |

### 11.2 Integration Tests

| Test | Command | Validation |
|------|---------|------------|
| ONSIT Pipeline | `pytest intelligence/tests/integration/test_onsit.py` | End-to-end discovery |
| Graph Ingestion | `pytest intelligence/tests/integration/test_ingestion.py` | PDF → Graph nodes |
| Neo4j Connection | `pytest intelligence/tests/integration/test_neo4j.py` | CRUD operations |

### 11.3 Manual Verification Steps

#### ONSIT Discovery Test

1. **Start all services**: `docker-compose up -d`
2. **Navigate to**: `http://localhost:3000/dashboard/onsit`
3. **Enter test identity**:
   - Email: `your_test_email@example.com`
   - Username: `your_test_username`
4. **Click "Start Discovery"**
5. **Expected results**:
   - Progress indicator shows status
   - Findings appear in list as discovered
   - Each finding shows source and risk level
6. **Verify in Graph**: Navigate to Graph page, filter by "ONSITFinding"

#### Graph Page Test

1. **Navigate to**: `http://localhost:3000/dashboard/graph`
2. **Verify controls**:
   - 2D/3D toggle works
   - Type filter dropdown populated
   - Zoom to fit button works
3. **Click a node**: Inspector panel shows properties
4. **Test Shadow Chat**: Ask "Who has my email?"
5. **Expected**: AI responds with relevant graph data

#### N8N Integration Test

1. **Navigate to**: `http://localhost:5678`
2. **Import test workflow** (if needed)
3. **Trigger GDPR PDF processing**
4. **Verify**: New nodes appear in Neo4j and Graph page

---

> **Document Version:** 1.0  
> **Created:** 2026-01-21  
> **Status:** AWAITING APPROVAL

---

## Appendix: Quick Reference

### Environment Variables Required

```env
# Existing
POSTGRES_USER=admin
POSTGRES_PASSWORD=securepassword
POSTGRES_DB=gdpr_local
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin

# NEW
GOOGLE_API_KEY=your_gemini_api_key
CREDENTIAL_KEY=your_fernet_key_for_encryption
REDIS_URL=redis://redis:6379/0
```

### Key Commands

```bash
# Start all services
docker-compose up -d

# View intelligence logs
docker logs gdpr_intelligence -f

# View Celery worker logs
docker logs gdpr_celery -f

# Run Python tests
docker exec gdpr_intelligence pytest tests/

# Run frontend tests
cd frontend && npm test
```
