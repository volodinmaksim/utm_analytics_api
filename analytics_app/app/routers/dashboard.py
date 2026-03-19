from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.clients.google_sheets import (
    GoogleSheetsConfigurationError,
    GoogleSheetsReadError,
)
from analytics_app.app.db import get_session, settings
from analytics_app.app.models.dto import (
    AudienceResponse,
    ContentResponse,
    FeedbackResponse,
    FunnelResponse,
    OverviewResponse,
    PaymentOverviewResponse,
    PaymentSourcesResponse,
    PaymentTimeseriesResponse,
    Period,
    Service,
    TrackedSheetCreateRequest,
    TrackedSheetResponse,
    TrackedSheetsListResponse,
    TrackedSheetSyncResponse,
    TrackedSheetUpdateRequest,
    UTMResponse,
    WishesResponse,
)
from analytics_app.app.models.orm import TrackedSheet
from analytics_app.app.payments.sync import sync_tracked_sheet_by_id
from analytics_app.app.payments.tracked_sheets import (
    normalize_spreadsheet_source,
    to_service_type,
    to_tracked_sheet_response,
    validate_tracked_sheet_access,
)
from analytics_app.app.services.analytics import (
    get_audience,
    get_content,
    get_feedback,
    get_funnel,
    get_overview,
    get_payment_overview,
    get_payment_sources,
    get_payment_timeseries,
    get_utm,
    get_wishes,
)


router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)
SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/api/admin/tracked-sheets", response_model=TrackedSheetsListResponse)
async def list_tracked_sheets(session: SessionDep) -> TrackedSheetsListResponse:
    stmt = select(TrackedSheet).order_by(TrackedSheet.id.desc())
    items = (await session.execute(stmt)).scalars().all()
    return TrackedSheetsListResponse(
        items=[to_tracked_sheet_response(item) for item in items]
    )


@router.post(
    "/api/admin/tracked-sheets",
    response_model=TrackedSheetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tracked_sheet(
    payload: TrackedSheetCreateRequest,
    session: SessionDep,
) -> TrackedSheetResponse:
    try:
        source = normalize_spreadsheet_source(
            spreadsheet_url=payload.spreadsheet_url,
            spreadsheet_id=payload.spreadsheet_id,
        )
        await validate_tracked_sheet_access(
            spreadsheet_id=source.spreadsheet_id,
            sheet_name=payload.sheet_name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except GoogleSheetsReadError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except GoogleSheetsConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    tracked_sheet = TrackedSheet(
        service=to_service_type(payload.service),
        spreadsheet_id=source.spreadsheet_id,
        spreadsheet_url=source.spreadsheet_url,
        sheet_name=payload.sheet_name,
        sheet_gid=source.sheet_gid,
        is_active=payload.is_active,
        poll_interval_seconds=payload.poll_interval_seconds,
    )
    session.add(tracked_sheet)

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tracked sheet with the same spreadsheet_id and sheet_name already exists",
        ) from exc

    await session.refresh(tracked_sheet)
    return to_tracked_sheet_response(tracked_sheet)


@router.patch(
    "/api/admin/tracked-sheets/{tracked_sheet_id}",
    response_model=TrackedSheetResponse,
)
async def update_tracked_sheet(
    tracked_sheet_id: int,
    payload: TrackedSheetUpdateRequest,
    session: SessionDep,
) -> TrackedSheetResponse:
    tracked_sheet = await session.get(TrackedSheet, tracked_sheet_id)
    if tracked_sheet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracked sheet not found",
        )

    next_sheet_name = payload.sheet_name or tracked_sheet.sheet_name
    next_service = payload.service or Service(tracked_sheet.service.value)
    source_changed = (
        payload.spreadsheet_url is not None or payload.spreadsheet_id is not None
    )
    sheet_name_changed = (
        payload.sheet_name is not None and payload.sheet_name != tracked_sheet.sheet_name
    )

    if source_changed:
        try:
            next_source = normalize_spreadsheet_source(
                spreadsheet_url=payload.spreadsheet_url,
                spreadsheet_id=payload.spreadsheet_id,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc
    else:
        next_source = normalize_spreadsheet_source(
            spreadsheet_url=tracked_sheet.spreadsheet_url,
            spreadsheet_id=tracked_sheet.spreadsheet_id,
        )

    if source_changed or sheet_name_changed:
        try:
            await validate_tracked_sheet_access(
                spreadsheet_id=next_source.spreadsheet_id,
                sheet_name=next_sheet_name,
            )
        except GoogleSheetsReadError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc
        except GoogleSheetsConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

    tracked_sheet.service = to_service_type(next_service)
    tracked_sheet.spreadsheet_id = next_source.spreadsheet_id
    tracked_sheet.spreadsheet_url = next_source.spreadsheet_url
    tracked_sheet.sheet_gid = next_source.sheet_gid
    tracked_sheet.sheet_name = next_sheet_name

    if payload.poll_interval_seconds is not None:
        tracked_sheet.poll_interval_seconds = payload.poll_interval_seconds
    if payload.is_active is not None:
        tracked_sheet.is_active = payload.is_active

    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tracked sheet with the same spreadsheet_id and sheet_name already exists",
        ) from exc

    await session.refresh(tracked_sheet)
    return to_tracked_sheet_response(tracked_sheet)


@router.post(
    "/api/admin/tracked-sheets/{tracked_sheet_id}/sync",
    response_model=TrackedSheetSyncResponse,
)
async def sync_tracked_sheet(
    tracked_sheet_id: int,
    session: SessionDep,
) -> TrackedSheetSyncResponse:
    tracked_sheet = await session.get(TrackedSheet, tracked_sheet_id)
    if tracked_sheet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracked sheet not found",
        )

    result = await sync_tracked_sheet_by_id(tracked_sheet_id)
    return TrackedSheetSyncResponse(
        tracked_sheet_id=result.tracked_sheet_id,
        status=result.status,
        rows_read=result.rows_read,
        rows_inserted=result.rows_inserted,
        invalid_rows=result.invalid_rows,
        empty_rows=result.empty_rows,
        error=result.error,
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


@router.get(
    "/api/analytics/payments/overview",
    response_model=PaymentOverviewResponse,
)
async def payments_overview(
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> PaymentOverviewResponse:
    return await get_payment_overview(session=session, service=service, period=period)


@router.get(
    "/api/analytics/payments/timeseries",
    response_model=PaymentTimeseriesResponse,
)
async def payments_timeseries(
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> PaymentTimeseriesResponse:
    return await get_payment_timeseries(
        session=session,
        service=service,
        period=period,
    )


@router.get(
    "/api/analytics/payments/sources",
    response_model=PaymentSourcesResponse,
)
async def payments_sources(
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> PaymentSourcesResponse:
    return await get_payment_sources(session=session, service=service, period=period)
