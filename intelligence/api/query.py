"""Authenticated API for the closed, typed privacy-query registry."""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from api.security import require_internal_request, require_profile_id
from privacy.contracts import PrivacyQueryResult
from privacy.query import PrivacyQueryService, PrivacyToolCall, TOOL_NAMES

router = APIRouter(
    prefix="/query", tags=["Privacy Query"], dependencies=[Depends(require_internal_request)]
)


@router.get("/tools")
async def list_tools(profile_id: Annotated[UUID, Depends(require_profile_id)]):
    return {"profileId": str(profile_id), "tools": TOOL_NAMES}


@router.post("", response_model=PrivacyQueryResult)
async def execute_typed_query(
    body: PrivacyToolCall, profile_id: Annotated[UUID, Depends(require_profile_id)]
):
    return await PrivacyQueryService().execute(profile_id=profile_id, call=body)
