"""Typed Personal Insights APIs over one coherent temporal selection."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from db.postgres import get_postgres_client
from insights.models import (
    AIConversationInsight, ChangeInsight, ExternalContextEvent,
    InsightComparisonPeriod, InsightPeriod, InsightTrace, MediaLocationCandidate,
    ObservedInterestState, PeriodGranularity, PeriodOverview, PersonalEraView,
    PlaceInsight, ProjectEpisodeView, SearchInsight, TemporalCorrelationCandidate,
    TemporalMode,
)
from insights.service import InsightService


router = APIRouter(prefix="/insights", tags=["Personal Insights"])


class InsightRequest(BaseModel):
    subject_id: str
    period: InsightPeriod
    comparison: InsightComparisonPeriod | None = None


def insight_request(
    subject_id: Annotated[str, Query(min_length=1)],
    mode: TemporalMode = TemporalMode.PERIOD,
    granularity: PeriodGranularity = PeriodGranularity.MONTH,
    from_at: Annotated[datetime | None, Query(alias="from")] = None,
    to_at: Annotated[datetime | None, Query(alias="to")] = None,
    point: datetime | None = None,
    compare_from: Annotated[datetime | None, Query(alias="compareFrom")] = None,
    compare_to: Annotated[datetime | None, Query(alias="compareTo")] = None,
) -> InsightRequest:
    try:
        if mode is TemporalMode.POINT_IN_TIME:
            period = InsightPeriod(mode=mode, granularity=granularity, point_at=point)
            return InsightRequest(subject_id=subject_id, period=period)
        period = InsightPeriod(mode=mode, granularity=granularity, from_at=from_at, to_at=to_at)
        comparison = None
        if mode is TemporalMode.COMPARE:
            baseline = InsightPeriod(
                mode=TemporalMode.PERIOD, granularity=granularity,
                from_at=compare_from, to_at=compare_to,
            )
            comparison = InsightComparisonPeriod(current=period, baseline=baseline)
        return InsightRequest(subject_id=subject_id, period=period, comparison=comparison)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _kwargs(request: InsightRequest):
    return {"subject_id":request.subject_id,"period":request.period,"comparison":request.comparison}


@router.get("/overview",response_model=PeriodOverview)
async def overview(request: Annotated[InsightRequest, Depends(insight_request)]):
    return await InsightService().get_period_overview(**_kwargs(request))


@router.get("/interests",response_model=tuple[ObservedInterestState,...])
async def interests(request: Annotated[InsightRequest, Depends(insight_request)]):
    return await InsightService().get_interest_states(**_kwargs(request))


@router.get("/search",response_model=SearchInsight)
async def search(request: Annotated[InsightRequest, Depends(insight_request)]):
    return await InsightService().get_search_insights(**_kwargs(request))


@router.get("/ai-conversations",response_model=AIConversationInsight)
async def ai_conversations(request: Annotated[InsightRequest, Depends(insight_request)]):
    return await InsightService().get_ai_conversation_insights(**_kwargs(request))


@router.get("/places",response_model=PlaceInsight)
async def places(request: Annotated[InsightRequest, Depends(insight_request)]):
    return await InsightService().get_place_insights(**_kwargs(request))


class ChangesResponse(BaseModel):
    changes: tuple[ChangeInsight,...]
    project_episodes: tuple[ProjectEpisodeView,...]
    personal_eras: tuple[PersonalEraView,...]
    drift: dict[str,list[dict]]


@router.get("/changes",response_model=ChangesResponse)
async def changes(request: Annotated[InsightRequest, Depends(insight_request)]):
    service = InsightService()
    snapshot = await service.get_snapshot(**_kwargs(request))
    drift = await service.get_personal_drift(**_kwargs(request))
    return {"changes":snapshot.changes,"project_episodes":snapshot.project_episodes,"personal_eras":snapshot.personal_eras,"drift":drift}


@router.get("/context",response_model=tuple[TemporalCorrelationCandidate,...])
async def context(request: Annotated[InsightRequest, Depends(insight_request)]):
    return await InsightService().get_contextual_correlations(**_kwargs(request))


@router.get("/evidence/{insight_id}",response_model=InsightTrace)
async def evidence(insight_id: UUID):
    try:
        return await InsightService().trace_insight(insight_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class ContextEventImport(BaseModel):
    title: str = Field(min_length=1, max_length=1000)
    event_type: Literal["legislation","platform_change","product_release","public_policy","user_added","other"]
    occurred_at: datetime
    ended_at: datetime | None = None
    topics: tuple[str, ...] = Field(default=(), max_length=100)
    jurisdiction: str | None = Field(default=None, max_length=200)
    source_uri: str | None = Field(default=None, max_length=4000)
    source_artifact_id: UUID | None = None


@router.post("/context-events", status_code=201,response_model=ExternalContextEvent)
async def import_context_event(body: ContextEventImport):
    if body.ended_at and body.ended_at < body.occurred_at:
        raise HTTPException(status_code=422, detail="ended_at precedes occurred_at")
    postgres = get_postgres_client()
    rows = await postgres.execute(
        """INSERT INTO external_context_events
        (title,event_type,occurred_at,ended_at,topics,jurisdiction,source_uri,source_artifact_id,ingested_at)
        VALUES($1,$2,$3,$4,$5::jsonb,$6,$7,$8,$9) RETURNING *""",
        body.title,body.event_type,body.occurred_at,body.ended_at,
        __import__("json").dumps(body.topics),body.jurisdiction,body.source_uri,
        body.source_artifact_id,datetime.now(timezone.utc),
    )
    return dict(rows[0])


class MediaLocationConfirmation(BaseModel):
    artifact_id: UUID
    evidence_locator_id: UUID
    reviewed_by: str = Field(min_length=1,max_length=200)
    occurred_at: datetime | None = None
    lat: float | None = Field(default=None,ge=-90,le=90)
    lon: float | None = Field(default=None,ge=-180,le=180)
    place_label: str | None = Field(default=None,max_length=1000)
    analysis_run_id: UUID | None = None


@router.post("/media-location-confirmations",status_code=201,response_model=MediaLocationCandidate)
async def confirm_media_location(body: MediaLocationConfirmation):
    if (body.lat is None)!=(body.lon is None):
        raise HTTPException(status_code=422,detail="lat and lon must be supplied together")
    if body.lat is None and not body.place_label:
        raise HTTPException(status_code=422,detail="coordinates or a place label are required")
    try:
        return await InsightService().confirm_media_location(**body.model_dump())
    except LookupError as exc:
        raise HTTPException(status_code=404,detail=str(exc)) from exc
