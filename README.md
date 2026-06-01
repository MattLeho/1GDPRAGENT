# 1GDPRAGENT: GDPR Automation System

A comprehensive, multi-agent AI system designed to automate the entire lifecycle of GDPR Data Subject Access Requests (DSARs) and data deletion requests. Built with an event-driven architecture using N8N, Next.js, PostgreSQL, Neo4j, and Google Gemini.

## 🌟 Overview

The **GDPR Automation App** empowers users to reclaim their data privacy by orchestrating specialized AI agents. It automates everything from reading complex privacy policies to drafting legally sound requests, monitoring email responses, parsing exported personal data, and building a secure, queryable "Shadow Profile" knowledge graph of a user's digital footprint.

## 🏗️ Architecture

The system uses a decoupled architecture where a Next.js frontend triggers specialized N8N AI agent workflows via webhooks. Data is stored securely in PostgreSQL (relational data/drafts) and Neo4j (graph connections for data points).

### Core Components
- **Next.js Frontend:** User interface for initiating requests and querying the Shadow Profile Oracle.
- **N8N Workflow Engine:** Orchestrates AI agents and handles scheduling, IMAP/SMTP integrations, and data parsing.
- **Google Gemini (PaLM):** The core intelligence layer driving all agents (policy analysis, drafting, classification, and graph extraction).
- **PostgreSQL:** Stores user profiles, credentials (encrypted), and request states.
- **Neo4j:** Stores the "Knowledge Graph" of companies, accounts, and extracted personal data points.

## 🤖 AI Agent Ecosystem

The application is powered by a suite of 8 specialized AI agents working together:

1. **Policy Analyzer (`01_policy_analyzer.json`)**
   - Scrapes and analyzes a company's privacy policy to extract the DPO email, request methods, and data retention policies.

2. **Request Drafter (`02_request_drafter.json`)**
   - Generates formal, legally compliant GDPR (Article 15/17) or CCPA request emails tailored to the specific company.

3. **Email Automator (`03a_email_sender.json` & `03b_inbox_monitor.json`)**
   - Sends the approved request via SMTP and actively monitors the inbox via IMAP to classify incoming responses (e.g., Acknowledgment, Data Attached, Rejection).

4. **Response Parser (`04_response_parser.json`)**
   - Processes data files received from companies (PDFs, ZIPs, CSVs, JSON).
   - Extracts structured personal information and assigns privacy risk levels (LOW/MEDIUM/HIGH).

5. **Knowledge Graph Ingestor (`05_kg_ingestor.json`)**
   - Converts the extracted personal data into graph nodes and relationships (triples).
   - Links shared identifiers (e.g., email, phone number) across different companies to map the user's digital footprint.

6. **Shadow Profile Oracle (`06_shadow_oracle.json`)**
   - A conversational agent that answers natural language questions about the user's data (e.g., "What companies have my location data?").
   - Translates questions into Cypher queries against the Neo4j database to provide evidence-backed answers.

7. **Integrity Council (MAKGED) (`07_integrity_council.json`)**
   - An internal validation system using a multi-agent debate framework (Forward, Backward, and Judge agents).
   - Debates and verifies proposed Knowledge Graph entries against source texts to prevent AI hallucinations.

## 🚀 Getting Started

Please refer to the detailed documentation located in the `App_Context_and_Plan/` directory:
- **[N8N Agent Import & Setup Instructions](App_Context_and_Plan/README.md):** Step-by-step guide to importing workflows and configuring credentials (Gemini, PostgreSQL, Neo4j, SMTP/IMAP).
- **[Detailed Agent Specs](App_Context_and_Plan/AgentDescriptions.md):** Deep dive into the input/output schemas and prompts for each agent.
- **[Database Setup](.agent/workflows/database-setup.md):** Instructions for starting and managing the required databases.

## 🔒 Privacy & Security

- **Local Execution:** Designed to be run locally (or self-hosted) so personal data exports never leave your control.
- **Encryption:** Identity fields and sensitive data can be encrypted in transit and at rest.
- **No Third-Party DBs:** All parsed GDPR data is stored in your local PostgreSQL and Neo4j instances.
