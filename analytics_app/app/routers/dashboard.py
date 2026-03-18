from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.db import get_session, settings
from analytics_app.app.models.dto import (
    AudienceResponse,
    ContentResponse,
    FeedbackResponse,
    FunnelResponse,
    OverviewResponse,
    Period,
    Service,
    UTMResponse,
    WishesResponse,
)
from analytics_app.app.services.analytics import (
    get_audience,
    get_content,
    get_feedback,
    get_funnel,
    get_overview,
    get_utm,
    get_wishes,
)


router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"base_url": settings.BASE_URL.rstrip("/")},
    )


@router.get("/api/analytics/overview", response_model=OverviewResponse)
async def overview(
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> OverviewResponse:
    return await get_overview(session=session, service=service, period=period)


@router.get("/api/analytics/funnel", response_model=FunnelResponse)
async def funnel(
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> FunnelResponse:
    return await get_funnel(session=session, service=service, period=period)


@router.get("/api/analytics/audience", response_model=AudienceResponse)
async def audience(
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> AudienceResponse:
    return await get_audience(session=session, service=service, period=period)


@router.get("/api/analytics/content", response_model=ContentResponse)
async def content(
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> ContentResponse:
    return await get_content(session=session, service=service, period=period)


@router.get("/api/analytics/utm", response_model=UTMResponse)
async def utm(
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> UTMResponse:
    return await get_utm(session=session, service=service, period=period)


@router.get("/api/analytics/feedback", response_model=FeedbackResponse)
async def feedback(
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> FeedbackResponse:
    return await get_feedback(session=session, service=service, period=period)


@router.get("/api/analytics/wishes", response_model=WishesResponse)
async def wishes(
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> WishesResponse:
    return await get_wishes(session=session, service=service, period=period)
