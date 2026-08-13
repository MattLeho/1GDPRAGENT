"""Profile-scoped persistence for GDPR requests used by Python services."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from uuid import UUID

from db.postgres import PostgresClient, get_postgres_client


class RequestRepository:
    """The only Python module permitted to issue canonical request SQL."""

    def __init__(self, postgres: PostgresClient | None = None) -> None:
        self.postgres = postgres or get_postgres_client()

    @asynccontextmanager
    async def _connection(self, connection=None) -> AsyncIterator[Any]:
        if connection is not None:
            yield connection
            return
        pool = await self.postgres._get_pool()
        async with pool.acquire() as acquired:
            yield acquired

    async def exists(self, profile_id: UUID, request_id: UUID, *, connection=None) -> bool:
        async with self._connection(connection) as conn:
            return bool(await conn.fetchval(
                "SELECT 1 FROM requests WHERE id=$1 AND profile_id=$2",
                request_id, profile_id,
            ))

    async def create_draft(
        self,
        profile_id: UUID,
        *,
        company_name: str,
        company_url: str | None,
        domain: str | None,
        request_type: str,
        notes: str | None = None,
        connection=None,
    ) -> UUID:
        async with self._connection(connection) as conn:
            return await conn.fetchval(
                """INSERT INTO requests(
                       profile_id,company_name,company_url,domain,status,request_type,notes
                   ) VALUES($1,$2,$3,$4,'draft',$5,$6) RETURNING id""",
                profile_id, company_name, company_url, domain, request_type, notes,
            )

    async def append_message(
        self, profile_id: UUID, request_id: UUID, *, sender: str, content: str,
        connection=None,
    ) -> bool:
        async with self._connection(connection) as conn:
            result = await conn.execute(
                """INSERT INTO messages(request_id,sender,content,timestamp)
                   SELECT id,$3,$4,NOW() FROM requests WHERE id=$1 AND profile_id=$2""",
                request_id, profile_id, sender, content,
            )
            return result == "INSERT 0 1"

    async def append_notes(
        self, profile_id: UUID, request_id: UUID, notes: str, *, connection=None,
    ) -> bool:
        async with self._connection(connection) as conn:
            result = await conn.execute(
                """UPDATE requests
                   SET notes=COALESCE(notes,'') || E'\n\n[' || NOW() || '] ' || $3
                   WHERE id=$1 AND profile_id=$2""",
                request_id, profile_id, notes,
            )
            return result == "UPDATE 1"

    async def update_received_processing(
        self, received_data_id: UUID, analysis_run_id: UUID, *, status: str,
        processing_stage: str, processing_progress: int, error_message: str | None,
        connection=None,
    ) -> bool:
        """Update an artefact only through its analysis run's canonical profile."""
        async with self._connection(connection) as conn:
            result = await conn.execute(
                """UPDATE received_data rd
                   SET status=$3,processing_stage=$4,processing_progress=$5,error_message=$6,
                       derived_content_basis='task3_deterministic_pipeline',
                       provenance_status='source_artifact_registered'
                   FROM analysis_runs ar
                   WHERE rd.id=$1 AND ar.id=$2 AND rd.profile_id=ar.profile_id""",
                received_data_id, analysis_run_id, status, processing_stage,
                max(0, min(100, processing_progress)), error_message,
            )
            return result == "UPDATE 1"

    async def received_data_exists(self, profile_id: UUID, received_data_id: UUID, *, connection=None) -> bool:
        async with self._connection(connection) as conn:
            return bool(await conn.fetchval(
                "SELECT 1 FROM received_data WHERE id=$1 AND profile_id=$2",
                received_data_id, profile_id,
            ))

    async def get_received_data(self, profile_id: UUID, received_data_id: UUID, *, connection=None):
        async with self._connection(connection) as conn:
            row = await conn.fetchrow(
                "SELECT * FROM received_data WHERE id=$1 AND profile_id=$2",
                received_data_id, profile_id,
            )
            return dict(row) if row else None

    async def record_specialist_text(
        self, profile_id: UUID, received_data_id: UUID, *, field: str, text: str, connection=None,
    ) -> bool:
        if field not in {"transcript", "extracted_text"}:
            raise ValueError("unsupported specialist text field")
        async with self._connection(connection) as conn:
            result = await conn.execute(
                f"""UPDATE received_data SET {field}=$2,markdown_content=$2,status='completed',
                    processing_stage='completed',processing_progress=100,processing_completed_at=NOW(),
                    derived_content_basis='task2_specialist_router',provenance_status='specialist_candidate'
                    WHERE id=$1 AND profile_id=$3""",
                received_data_id, text, profile_id,
            )
            return result == "UPDATE 1"
