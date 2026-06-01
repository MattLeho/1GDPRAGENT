"""
Neo4j Client for Intelligence Service

Provides async database operations for the knowledge graph.
"""

import json
import httpx
from typing import Optional
from functools import lru_cache

from config import get_settings


settings = get_settings()


class Neo4jClient:
    """
    Async Neo4j client using HTTP API.
    
    Uses the Neo4j HTTP transaction API for executing Cypher queries.
    This approach works well with async Python and doesn't require
    the neo4j driver's connection pooling overhead.
    """
    
    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
    ):
        """
        Initialize Neo4j client.
        
        Args:
            uri: Neo4j bolt URI (converted to HTTP)
            user: Neo4j username
            password: Neo4j password
        """
        bolt_uri = uri or settings.neo4j_uri
        # Convert bolt:// to http:// and port 7687 to 7474
        self.base_url = bolt_uri.replace("bolt://", "http://").replace(":7687", ":7474")
        self.user = user or settings.neo4j_user
        self.password = password or settings.neo4j_password
        self.tx_endpoint = f"{self.base_url}/db/neo4j/tx/commit"
    
    async def execute(
        self,
        cypher: str,
        params: Optional[dict] = None,
    ) -> list[dict]:
        """
        Execute a single Cypher statement.
        
        Args:
            cypher: Cypher query string
            params: Optional query parameters
            
        Returns:
            List of result records as dicts
        """
        statement = {"statement": cypher}
        if params:
            statement["parameters"] = params
        
        return await self._execute_statements([statement])
    
    async def execute_batch(
        self,
        statements: list[dict],
    ) -> dict:
        """
        Execute multiple Cypher statements in a single transaction.
        
        Args:
            statements: List of {"statement": "...", "parameters": {...}} dicts
            
        Returns:
            Dict with results and errors
        """
        results = await self._execute_statements(statements)
        return {
            "success": True,
            "results_count": len(results),
            "results": results,
        }
    
    async def query(
        self,
        cypher: str,
        params: Optional[dict] = None,
    ) -> list[dict]:
        """
        Execute a read-only query and return results.
        
        Convenience wrapper around execute() for queries.
        
        Args:
            cypher: Cypher query string
            params: Optional query parameters
            
        Returns:
            List of result records as dicts
        """
        return await self.execute(cypher, params)
    
    async def _execute_statements(
        self,
        statements: list[dict],
    ) -> list[dict]:
        """
        Execute statements via Neo4j HTTP API.
        
        Args:
            statements: List of statement dicts
            
        Returns:
            Flattened list of all result records
        """
        payload = {"statements": statements}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.tx_endpoint,
                json=payload,
                auth=(self.user, self.password),
                headers={"Content-Type": "application/json"},
                timeout=60.0,
            )
            
            if response.status_code >= 400:
                raise Exception(f"Neo4j error: {response.status_code} - {response.text}")
            
            data = response.json()
            
            # Check for Neo4j errors
            if data.get("errors"):
                error_msgs = [e.get("message", str(e)) for e in data["errors"]]
                raise Exception(f"Neo4j query errors: {'; '.join(error_msgs)}")
            
            # Flatten results from all statements
            all_records = []
            for result in data.get("results", []):
                columns = result.get("columns", [])
                for row in result.get("data", []):
                    record = {}
                    for i, col in enumerate(columns):
                        if i < len(row.get("row", [])):
                            record[col] = row["row"][i]
                    if record:
                        all_records.append(record)
            
            return all_records
    
    async def check_connection(self) -> bool:
        """
        Test the Neo4j connection.
        
        Returns:
            True if connected, raises exception otherwise
        """
        try:
            await self.execute("RETURN 1 as test")
            return True
        except Exception as e:
            raise Exception(f"Neo4j connection failed: {e}")


@lru_cache
def get_neo4j_client() -> Neo4jClient:
    """Get cached Neo4j client instance."""
    return Neo4jClient()
