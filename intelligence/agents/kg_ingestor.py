"""
Knowledge Graph Ingestor Agent

Translates 05_kg_ingestor.json N8N workflow to Python.
Ingests extracted GDPR data into Neo4j knowledge graph.
"""

import json
import asyncio
from typing import Optional
from dataclasses import dataclass, field
from datetime import datetime

from llm.gemini import GeminiClient
from db.neo4j import get_neo4j_client
from db.postgres import get_postgres_client
from config import get_settings


settings = get_settings()


# Graph schema context for LLM (from N8N workflow)
GRAPH_SCHEMA = """
## GRAPH SCHEMA

### Node Types:
- `(:User {uid: 'root'})` - The root user (always exists)
- `(:Company {name, domain})` - Data controllers/companies
- `(:Account {username, platform, join_date})` - User accounts at companies
- `(:Attribute {value, type})` - Shared identifiers (email, phone, IP, device_id)
- `(:DataPoint {category, value, risk_level, source_request})` - Collected data
- `(:Persona {label, type})` - User personas (Professional, Gamer, etc)

### Relationship Types:
- `(:User)-[:HAS_ACCOUNT]->(:Account)`
- `(:Account)-[:HELD_BY]->(:Company)`
- `(:Company)-[:COLLECTS]->(:DataPoint)`
- `(:Account)-[:LINKED_TO]->(:Attribute)`
- `(:DataPoint)-[:DERIVED_FROM]->(:Attribute)`

### Data Categories:
- CONTACT_INFO, ACCOUNT_INFO, ACTIVITY_DATA, FINANCIAL_DATA
- TECHNICAL_DATA, LOCATION_DATA, COMMUNICATION_DATA
- MEDIA_DATA, BIOMETRIC_DATA, INFERRED_DATA, SENSITIVE_DATA
"""

CYPHER_GENERATION_PROMPT = """
You are an expert Neo4j Cypher generator for a GDPR Knowledge Graph system.
Your job is to convert extracted personal data into valid, accurate Cypher MERGE statements.

{schema}

## CYPHER RULES
1. Always use MERGE to avoid duplicates
2. Use lowercase for email addresses
3. Include timestamp: `created_at: datetime()`
4. Include source: `source_request: '{request_id}'`
5. Set risk_level: 'LOW', 'MEDIUM', or 'HIGH'
6. Escape special characters in string values

## COMPANY CONTEXT
Company: {company_name}
Request ID: {request_id}
Batch: {batch_num} (items {start_idx} to {end_idx})

## DATA ITEMS TO INGEST
{data_items}

## OUTPUT FORMAT
Return a JSON array of statement objects:
```json
[
  {{
    "description": "What this statement creates",
    "cypher": "MERGE (c:Company {{name: 'CompanyName'}}) ...",
    "isValid": true
  }}
]
```

Generate MERGE statements for each data item. Link data points to the company node.
Return ONLY the JSON array, no markdown.
"""


@dataclass
class DataItem:
    """Single data item to ingest."""
    type: str
    category: str
    value: str
    risk_level: str = "MEDIUM"


@dataclass
class IngestRequest:
    """Request to ingest data into knowledge graph."""
    company_name: str
    request_id: str
    extracted_data: list[dict] = field(default_factory=list)
    categories: dict = field(default_factory=dict)
    source: str = "manual"


@dataclass
class IngestResult:
    """Result of ingestion operation."""
    success: bool
    request_id: str
    company_name: str
    total_items: int
    statements_executed: int
    statements_errored: int
    errors: list[str] = field(default_factory=list)


class KGIngestorAgent:
    """
    Knowledge Graph Ingestor Agent.
    
    Translates the 05_kg_ingestor.json N8N workflow to Python.
    
    Flow:
    1. Receive extracted data from response parser
    2. Flatten into individual data items
    3. Batch into groups of 50
    4. For each batch:
       - Generate Cypher via LLM
       - Validate syntax
       - Execute via Neo4j
    5. Log progress
    """
    
    def __init__(
        self,
        batch_size: int = 50,
        log_progress: bool = True,
    ):
        """
        Initialize the ingestor.
        
        Args:
            batch_size: Max items per batch (default 50 from N8N)
            log_progress: Whether to log to PostgreSQL
        """
        self.batch_size = batch_size
        self.log_progress = log_progress
        self.llm = GeminiClient.get_flash_client()
        self.neo4j = get_neo4j_client()
        self.postgres = get_postgres_client()
    
    async def ingest(self, request: IngestRequest) -> IngestResult:
        """
        Ingest data into the knowledge graph.
        
        Args:
            request: Ingestion request with data
            
        Returns:
            IngestResult with stats
        """
        # Flatten data items
        data_items = self._flatten_data(request)
        
        if not data_items:
            return IngestResult(
                success=False,
                request_id=request.request_id,
                company_name=request.company_name,
                total_items=0,
                statements_executed=0,
                statements_errored=0,
                errors=["No data items to ingest"],
            )
        
        # Log start
        if self.log_progress and request.request_id:
            try:
                await self.postgres.log_message(
                    request.request_id,
                    f"🔄 Starting Knowledge Graph ingestion for {request.company_name}. "
                    f"Processing {len(data_items)} data items in batches of {self.batch_size}.",
                )
            except Exception:
                pass  # Don't fail on logging errors
        
        # Process in batches
        total_executed = 0
        total_errored = 0
        all_errors = []
        
        batches = self._create_batches(data_items)
        
        for batch_idx, batch in enumerate(batches):
            batch_result = await self._process_batch(
                batch=batch,
                batch_idx=batch_idx,
                total_batches=len(batches),
                request=request,
            )
            
            total_executed += batch_result["executed"]
            total_errored += batch_result["errored"]
            all_errors.extend(batch_result["errors"])
            
            # Log progress
            if self.log_progress and request.request_id:
                try:
                    progress = int(((batch_idx + 1) / len(batches)) * 100)
                    await self.postgres.log_message(
                        request.request_id,
                        f"📊 Batch {batch_idx + 1}/{len(batches)} complete: "
                        f"{batch_result['executed']} statements executed ({progress}% done)",
                    )
                except Exception:
                    pass
        
        # Log completion
        if self.log_progress and request.request_id:
            try:
                await self.postgres.log_message(
                    request.request_id,
                    f"✅ Knowledge Graph ingestion complete for {request.company_name}. "
                    f"{total_executed} data points added to your privacy graph.",
                )
                await self.postgres.update_request_notes(
                    request.request_id,
                    f"Knowledge Graph ingestion complete: {total_executed} statements executed, "
                    f"{total_errored} errors",
                )
            except Exception:
                pass
        
        return IngestResult(
            success=total_errored == 0,
            request_id=request.request_id,
            company_name=request.company_name,
            total_items=len(data_items),
            statements_executed=total_executed,
            statements_errored=total_errored,
            errors=all_errors[:10],  # Limit errors
        )
    
    def _flatten_data(self, request: IngestRequest) -> list[DataItem]:
        """Flatten categories and extracted data into DataItem list."""
        items = []
        
        # Add category-based data points
        for category, data in request.categories.items():
            examples = data.get("examples", []) if isinstance(data, dict) else []
            risk_level = data.get("riskLevel", "MEDIUM") if isinstance(data, dict) else "MEDIUM"
            
            for example in examples:
                items.append(DataItem(
                    type="datapoint",
                    category=category,
                    value=str(example),
                    risk_level=risk_level,
                ))
        
        # Add extracted entities
        for entity in request.extracted_data:
            items.append(DataItem(
                type=entity.get("type", "entity"),
                category=entity.get("category", "UNKNOWN"),
                value=str(entity.get("value", "")),
                risk_level=entity.get("riskLevel", "MEDIUM"),
            ))
        
        return items
    
    def _create_batches(self, items: list[DataItem]) -> list[list[DataItem]]:
        """Split items into batches."""
        batches = []
        for i in range(0, len(items), self.batch_size):
            batches.append(items[i:i + self.batch_size])
        return batches
    
    async def _process_batch(
        self,
        batch: list[DataItem],
        batch_idx: int,
        total_batches: int,
        request: IngestRequest,
    ) -> dict:
        """Process a single batch of data items."""
        result = {"executed": 0, "errored": 0, "errors": []}
        
        try:
            # Generate Cypher via LLM
            cypher_statements = await self._generate_cypher(
                batch=batch,
                batch_idx=batch_idx,
                request=request,
            )
            
            if not cypher_statements:
                result["errors"].append(f"Batch {batch_idx + 1}: No valid statements generated")
                return result
            
            # Execute statements
            exec_result = await self._execute_statements(cypher_statements)
            result["executed"] = exec_result["success_count"]
            result["errored"] = exec_result["error_count"]
            result["errors"].extend(exec_result["errors"])
            
        except Exception as e:
            result["errored"] = len(batch)
            result["errors"].append(f"Batch {batch_idx + 1} failed: {str(e)}")
        
        return result
    
    async def _generate_cypher(
        self,
        batch: list[DataItem],
        batch_idx: int,
        request: IngestRequest,
    ) -> list[dict]:
        """Generate Cypher statements for a batch using LLM."""
        
        # Format data items for prompt
        data_items_json = json.dumps([
            {
                "type": item.type,
                "category": item.category,
                "value": item.value,
                "riskLevel": item.risk_level,
            }
            for item in batch
        ], indent=2)
        
        start_idx = batch_idx * self.batch_size + 1
        end_idx = start_idx + len(batch) - 1
        
        prompt = CYPHER_GENERATION_PROMPT.format(
            schema=GRAPH_SCHEMA,
            company_name=request.company_name,
            request_id=request.request_id,
            batch_num=batch_idx + 1,
            start_idx=start_idx,
            end_idx=end_idx,
            data_items=data_items_json,
        )
        
        try:
            response = await self.llm.complete(prompt, temperature=0.1)
            return self._parse_cypher_response(response, request.company_name)
        except Exception as e:
            # Fallback: create basic company node
            return [{
                "description": "Fallback: Create company node",
                "cypher": f"MERGE (c:Company {{name: '{request.company_name.replace(chr(39), chr(39)+chr(39))}'}}) "
                         f"SET c.updated_at = datetime()",
                "isValid": True,
            }]
    
    def _parse_cypher_response(
        self,
        response: str,
        company_name: str,
    ) -> list[dict]:
        """Parse LLM response to extract Cypher statements."""
        try:
            # Find JSON array in response
            import re
            json_match = re.search(r'\[\s*\{[\s\S]*\}\s*\]', response)
            if json_match:
                statements = json.loads(json_match.group())
            else:
                statements = json.loads(response)
            
            # Filter valid statements
            valid = []
            for s in statements:
                cypher = s.get("cypher", "")
                is_valid = s.get("isValid", True)
                
                if cypher and is_valid and ("MERGE" in cypher.upper() or "CREATE" in cypher.upper()):
                    valid.append(s)
            
            return valid
            
        except json.JSONDecodeError:
            # Return fallback
            return [{
                "description": "Fallback: Create company node",
                "cypher": f"MERGE (c:Company {{name: '{company_name.replace(chr(39), chr(39)+chr(39))}'}}) "
                         f"SET c.updated_at = datetime()",
                "isValid": True,
            }]
    
    async def _execute_statements(
        self,
        statements: list[dict],
    ) -> dict:
        """Execute Cypher statements via Neo4j."""
        result = {"success_count": 0, "error_count": 0, "errors": []}
        
        neo4j_statements = [{"statement": s["cypher"]} for s in statements]
        
        try:
            batch_result = await self.neo4j.execute_batch(neo4j_statements)
            result["success_count"] = len(statements)
        except Exception as e:
            result["error_count"] = len(statements)
            result["errors"].append(str(e))
        
        return result


# Convenience function
async def ingest_to_graph(
    company_name: str,
    request_id: str,
    extracted_data: list[dict] = None,
    categories: dict = None,
    source: str = "manual",
) -> IngestResult:
    """
    Ingest data to knowledge graph.
    
    Convenience wrapper for KGIngestorAgent.
    """
    agent = KGIngestorAgent()
    request = IngestRequest(
        company_name=company_name,
        request_id=request_id,
        extracted_data=extracted_data or [],
        categories=categories or {},
        source=source,
    )
    return await agent.ingest(request)
