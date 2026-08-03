"""
PostgreSQL Client for Intelligence Service

Provides async database operations for logging and state management.
"""

import asyncpg
from typing import Optional
from uuid import UUID

from config import get_settings


settings = get_settings()


class PostgresClient:
    """
    Async PostgreSQL client for logging and state management.
    
    Used for:
    - Logging ingestion progress to messages table
    - Updating request status
    - Tracking agent activity
    """
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize PostgreSQL client.
        
        Args:
            database_url: PostgreSQL connection URL
        """
        self.database_url = database_url or settings.database_url
        self._pool = None
    
    async def _get_pool(self):
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
            )
        return self._pool
    
    async def log_message(
        self,
        profile_id: UUID,
        request_id: UUID,
        content: str,
        sender: str = "agent",
    ) -> None:
        """Append a message through the canonical profile-owned boundary."""
        from request_domain import RequestRepository
        if not await RequestRepository(self).append_message(
            profile_id, request_id, sender=sender, content=content,
        ):
            raise LookupError("request does not exist for canonical profile")
    
    async def update_request_notes(
        self,
        profile_id: UUID,
        request_id: UUID,
        notes: str,
    ) -> None:
        """Append operational notes through the canonical boundary."""
        from request_domain import RequestRepository
        if not await RequestRepository(self).append_notes(profile_id, request_id, notes):
            raise LookupError("request does not exist for canonical profile")
    
    async def execute(
        self,
        query: str,
        *args,
    ) -> list:
        """
        Execute a raw SQL query.
        
        Args:
            query: SQL query string
            *args: Query parameters
            
        Returns:
            List of result records
        """
        pool = await self._get_pool()
        
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)
    
    async def check_connection(self) -> bool:
        """
        Test the PostgreSQL connection.
        
        Returns:
            True if connected, raises exception otherwise
        """
        try:
            pool = await self._get_pool()
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            raise Exception(f"PostgreSQL connection failed: {e}")
    
    async def close(self):
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None


# Module-level client instance
_postgres_client: Optional[PostgresClient] = None


def get_postgres_client() -> PostgresClient:
    """Get PostgreSQL client instance."""
    global _postgres_client
    if _postgres_client is None:
        _postgres_client = PostgresClient()
    return _postgres_client
