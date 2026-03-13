from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from analytics_app.app.db import settings
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


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"base_url": settings.BASE_URL.rstrip("/")},
    )


@router.get("/api/analytics/overview", response_model=OverviewResponse)
async def overview(
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> OverviewResponse:
    return await get_overview(service=service, period=period)


@router.get("/api/analytics/funnel", response_model=FunnelResponse)
async def funnel(
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> FunnelResponse:
    return await get_funnel(service=service, period=period)


@router.get("/api/analytics/audience", response_model=AudienceResponse)
async def audience(
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> AudienceResponse:
    return await get_audience(service=service, period=period)


@router.get("/api/analytics/content", response_model=ContentResponse)
async def content(
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> ContentResponse:
    return await get_content(service=service, period=period)


@router.get("/api/analytics/utm", response_model=UTMResponse)
async def utm(
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> UTMResponse:
    return await get_utm(service=service, period=period)


@router.get("/api/analytics/feedback", response_model=FeedbackResponse)
async def feedback(
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> FeedbackResponse:
    return await get_feedback(service=service, period=period)


@router.get("/api/analytics/wishes", response_model=WishesResponse)
async def wishes(
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> WishesResponse:
    return await get_wishes(service=service, period=period)
