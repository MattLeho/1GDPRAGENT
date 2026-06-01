# N8N Agent Import Instructions

## Prerequisites

1. **N8N Running**: Ensure your N8N instance is running at `http://localhost:5678`
2. **Credentials Ready**: You'll need to set up credentials before workflows will run

---

## Step 1: Set Up Google Gemini Credentials

1. Open N8N at `http://localhost:5678`
2. Go to **Settings** → **Credentials**
3. Click **Add Credential**
4. Search for **Google Gemini (PaLM)**
5. Configure:
   - **Name**: `Google Gemini API`
   - **API Key**: set this in your local `.env` file. Do not commit real API keys.
   - Leave Host as default: `https://generativelanguage.googleapis.com`
6. Click **Save**

---

## Step 2: Set Up PostgreSQL Credentials

1. Go to **Settings** → **Credentials**
2. Click **Add Credential**
3. Search for **Postgres**
4. Configure:
   - **Name**: `GDPR Postgres`
   - **Host**: `postgres` (Docker network) or `localhost`
   - **Port**: `5432`
   - **Database**: `gdpr_local`
   - **User**: `admin` (from your .env)
   - **Password**: `securepassword` (from your .env)
5. Click **Save** and **Test Connection**

---

## Step 3: Set Up Neo4j Credentials (for Knowledge Graph agents)

1. Go to **Settings** → **Credentials**
2. Click **Add Credential**
3. Search for **Neo4j**
4. Configure:
   - **Name**: `GDPR Neo4j`
   - **Host**: `bolt://neo4j:7687` (Docker network) or `bolt://localhost:7687`
   - **User**: `neo4j`
   - **Password**: Your Neo4j password (from .env)
5. Click **Save** and **Test Connection**

---

## Step 4: Set Up Email Credentials (for Email agents)

### SMTP (Sending emails)
1. Go to **Settings** → **Credentials**
2. Click **Add Credential**
3. Search for **SMTP**
4. Configure with your email provider settings

### IMAP (Reading emails)
1. Add another credential for **IMAP**
2. Configure with your email provider's IMAP server

---

## Step 5: Import Workflow Templates

### Import Each Workflow:

1. In N8N, go to **Workflows** → **Add Workflow** → **Import from File**
2. Import each JSON file in order:

| Order | Filename | Description |
|-------|----------|-------------|
| 1 | `01_policy_analyzer.json` | Analyzes privacy policies |
| 2 | `02_request_drafter.json` | Drafts GDPR request emails |
| 3 | `03a_email_sender.json` | Sends approved requests |
| 4 | `03b_inbox_monitor.json` | Monitors for responses |
| 5 | `04_response_parser.json` | Parses GDPR data exports |
| 6 | `05_kg_ingestor.json` | Populates Knowledge Graph |
| 7 | `06_shadow_oracle.json` | Chat about your data |
| 8 | `07_integrity_council.json` | Validates graph entries |

---

## Step 6: Update Credential IDs

After importing, you need to connect your saved credentials to each workflow:

### For each imported workflow:

1. Open the workflow
2. Click on each node that shows a ⚠️ warning icon
3. Select the appropriate credential from the dropdown:
   - **Google Gemini Chat Model** nodes → Select `Google Gemini API`
   - **Postgres** nodes → Select `GDPR Postgres`
   - **Neo4j** nodes → Select `GDPR Neo4j`
   - **Email** nodes → Select your SMTP/IMAP credentials
4. Click **Save**

---

## Step 7: Activate Scheduled Workflow

The Inbox Monitor workflow runs on a schedule (every 15 minutes):

1. Open `03b_inbox_monitor` workflow
2. Toggle the **Active** switch to ON
3. This will start monitoring your inbox for company responses

---

## Step 8: Test the Workflows

### Test Policy Analyzer:
```bash
curl -X POST http://localhost:5678/webhook/analyze-policy \
  -H "Content-Type: application/json" \
  -d '{"url": "spotify.com", "requestType": "access"}'
```

### Test Request Drafter:
```bash
curl -X POST http://localhost:5678/webhook/draft-request \
  -H "Content-Type: application/json" \
  -d '{
    "requestType": "access",
    "companyName": "Spotify",
    "dpoEmail": "privacy@spotify.com",
    "identity": {
      "name": "John Doe",
      "email": "john@example.com"
    }
  }'
```

### Test Shadow Oracle Chat:
```bash
curl -X POST http://localhost:5678/webhook/shadow-chat \
  -H "Content-Type: application/json" \
  -d '{"question": "What companies have my data?"}'
```

---

## Webhook URL Reference

These are the webhook URLs your Next.js frontend should call:

| Feature | Webhook URL |
|---------|-------------|
| Analyze Policy | `http://localhost:5678/webhook/analyze-policy` |
| Draft Request | `http://localhost:5678/webhook/draft-request` |
| Send Request | `http://localhost:5678/webhook/send-request` |
| Parse Response | `http://localhost:5678/webhook/parse-response` |
| Ingest to Graph | `http://localhost:5678/webhook/ingest-data` |
| Shadow Chat | `http://localhost:5678/webhook/shadow-chat` |
| Validate Triple | `http://localhost:5678/webhook/validate-triple` |

---

## Troubleshooting

### "Credential not found" Error
- Re-open the node and re-select the credential from the dropdown
- Make sure the credential was saved successfully

### "Connection refused" to Postgres/Neo4j
- If using Docker, use `postgres` instead of `localhost`
- Ensure containers are on the same Docker network (`gdpr-net`)

### Gemini API Errors
- Check your API key is valid
- Ensure you have quota remaining on your Google Cloud account
- Try switching between `gemini-1.5-pro` and `gemini-1.5-flash` models

### Webhook Not Responding
- Make sure the workflow is saved
- Check that N8N is running
- For production, ensure webhooks are accessible externally

---

## Next Steps

1. **Connect Frontend**: Update your Next.js `/api/*` routes to proxy to these webhooks
2. **Seed Database**: Run seed scripts to populate test data
3. **Test End-to-End**: Submit a test GDPR request and verify it flows through all agents
4. **Enable Scheduling**: Activate the inbox monitor for automatic response handling
