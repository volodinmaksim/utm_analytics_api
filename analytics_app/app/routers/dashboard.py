from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.admin_auth import (
    AdminApiDep,
    ensure_admin_auth_configured,
    is_admin_authenticated,
    login_admin,
    logout_admin,
    verify_admin_password,
)
from analytics_app.app.broadcasts.campaigns import (
    create_admin_broadcast,
    get_admin_broadcasts_list,
    cancel_admin_broadcast,
    get_admin_broadcast_detail,
    get_admin_broadcast_audience_options,
)
from analytics_app.app.broadcasts.templates import (
    get_list_admin_telegram_templates,
    send_test_template_to_admin,
)
from analytics_app.app.clients.google_sheets import (
    GoogleSheetsConfigurationError,
    GoogleSheetsReadError,
)
from analytics_app.app.db import get_session, settings
from analytics_app.app.models import TrackedSheet
from analytics_app.app.payments.sync import sync_tracked_sheet_by_id
from analytics_app.app.payments.tracked_sheets import (
    normalize_spreadsheet_source,
    to_service_type,
    to_tracked_sheet_response,
    validate_tracked_sheet_access,
)
from analytics_app.app.schemas import (
    AdminTelegramTemplateListResponse,
    AudienceResponse,
    ContentResponse,
    FeedbackResponse,
    FunnelResponse,
    OverviewResponse,
    PaymentOverviewResponse,
    PaymentSourcesResponse,
    PaymentTimeseriesResponse,
    PaymentUserDetailResponse,
    RecentPaymentsResponse,
    Period,
    Service,
    TrackedSheetCreateRequest,
    TrackedSheetResponse,
    TrackedSheetsListResponse,
    TrackedSheetSyncResponse,
    TrackedSheetUpdateRequest,
    UTMResponse,
    WishesResponse,
    AdminTelegramTemplateSendTestResponse,
)
from analytics_app.app.schemas.broadcasts import (
    AdminTelegramTemplateSendTestRequest,
    AdminBroadcastResponse,
    AdminBroadcastCreateRequest,
    AdminBroadcastListResponse,
    AdminBroadcastCancelResponse,
    AdminBroadcastDetailResponse,
    BroadcastAudienceOptionsResponse,
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
    get_payment_user_detail,
    get_recent_payments,
    get_utm,
    get_wishes,
)

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parents[1] / "templates")
)
SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def _get_tracked_sheet_or_404(
    session: AsyncSession,
    tracked_sheet_id: int,
) -> TrackedSheet:
    tracked_sheet = await session.get(TrackedSheet, tracked_sheet_id)
    if tracked_sheet is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tracked sheet not found",
        )
    return tracked_sheet


def _admin_login_redirect(request: Request) -> RedirectResponse:
    return RedirectResponse(
        url=str(request.url_for("admin_login_page")),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/admin/login", response_class=HTMLResponse, name="admin_login_page")
async def admin_login_page(request: Request) -> HTMLResponse:
    ensure_admin_auth_configured()
    if is_admin_authenticated(request):
        return RedirectResponse(
            url=str(request.url_for("admin_page")),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return templates.TemplateResponse(
        request=request,
        name="admin_login.html",
        context={"error": None},
    )


@router.post("/admin/login", response_class=HTMLResponse)
async def admin_login_submit(request: Request) -> Response:
    ensure_admin_auth_configured()
    body = (await request.body()).decode("utf-8")
    password = (parse_qs(body).get("password") or [""])[0]
    if not verify_admin_password(password):
        return templates.TemplateResponse(
            request=request,
            name="admin_login.html",
            context={"error": "Invalid password"},
        )

    response = RedirectResponse(
        url=str(request.url_for("admin_page")),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    login_admin(response)
    return response


@router.post("/admin/logout")
async def admin_logout(request: Request) -> RedirectResponse:
    response = RedirectResponse(
        url=str(request.url_for("admin_login_page")),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    logout_admin(response)
    return response


@router.get("/admin", response_class=HTMLResponse, name="admin_page")
async def admin_page(request: Request) -> HTMLResponse:
    ensure_admin_auth_configured()
    if not is_admin_authenticated(request):
        return _admin_login_redirect(request)

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={"base_url": settings.BASE_URL.rstrip("/")},
    )


@router.get(
    "/admin/broadcasts",
    response_class=HTMLResponse,
    name="admin_broadcasts_page",
)
async def admin_broadcasts_page(request: Request) -> HTMLResponse:
    ensure_admin_auth_configured()
    if not is_admin_authenticated(request):
        return _admin_login_redirect(request)

    return templates.TemplateResponse(
        request=request,
        name="admin_broadcasts.html",
        context={"base_url": settings.BASE_URL.rstrip("/")},
    )


@router.get("/api/admin/tracked-sheets", response_model=TrackedSheetsListResponse)
async def list_tracked_sheets(
    _admin: AdminApiDep,
    session: SessionDep,
) -> TrackedSheetsListResponse:
    stmt = select(TrackedSheet).order_by(TrackedSheet.id.desc())
    items = (await session.execute(stmt)).scalars().all()
    return TrackedSheetsListResponse(
        items=[to_tracked_sheet_response(item) for item in items]
    )


@router.get(
    "/api/admin/telegram-templates",
    response_model=AdminTelegramTemplateListResponse,
)
async def list_telegram_templates(
    _admin: AdminApiDep,
    session: SessionDep,
    limit: int = Query(default=8, ge=1, le=100),
) -> AdminTelegramTemplateListResponse:
    return await get_list_admin_telegram_templates(session=session, limit=limit)


@router.post(
    "/api/admin/telegram-templates/{template_id}/send-test",
    response_model=AdminTelegramTemplateSendTestResponse,
)
async def check_template(
    _admin: AdminApiDep,
    session: SessionDep,
    template_id: int,
    data: AdminTelegramTemplateSendTestRequest,
) -> AdminTelegramTemplateSendTestResponse:
    return await send_test_template_to_admin(
        session,
        template_id=template_id,
        service=data.service,
    )


@router.post(
    "/api/admin/broadcasts",
    response_model=AdminBroadcastResponse,
)
async def admin_create_broadcast(
    _admin: AdminApiDep,
    session: SessionDep,
    data: AdminBroadcastCreateRequest,
) -> AdminBroadcastResponse:
    try:
        return await create_admin_broadcast(
            session,
            service=data.service,
            template_id=data.template_id,
            audience_type=data.audience_type,
            audience_filter=data.audience_filter,
            scheduled_at=data.scheduled_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/api/admin/broadcasts",
    response_model=AdminBroadcastListResponse,
)
async def admin_get_broadcasts(
    _admin: AdminApiDep,
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> AdminBroadcastListResponse:
    return await get_admin_broadcasts_list(session, limit=limit)


@router.get(
    "/api/admin/broadcast-audience-options",
    response_model=BroadcastAudienceOptionsResponse,
)
async def admin_get_broadcast_audience_options(
    _admin: AdminApiDep,
    session: SessionDep,
    service: Service,
) -> BroadcastAudienceOptionsResponse:
    return await get_admin_broadcast_audience_options(session, service=service)


@router.post(
    "/api/admin/broadcasts/{broadcast_id}/cancel",
    response_model=AdminBroadcastCancelResponse,
)
async def cancel_broadcast_by_id(
    _admin: AdminApiDep,
    session: SessionDep,
    broadcast_id: int,
) -> AdminBroadcastCancelResponse:
    return await cancel_admin_broadcast(session, broadcast_id=broadcast_id)


@router.get(
    "/api/admin/broadcasts/{broadcast_id}", response_model=AdminBroadcastDetailResponse
)
async def admin_get_broadcast_detail(
    _admin: AdminApiDep,
    session: SessionDep,
    broadcast_id: int,
) -> AdminBroadcastDetailResponse:
    return await get_admin_broadcast_detail(session, broadcast_id=broadcast_id)


@router.post(
    "/api/admin/tracked-sheets",
    response_model=TrackedSheetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_tracked_sheet(
    payload: TrackedSheetCreateRequest,
    _admin: AdminApiDep,
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
        message = str(getattr(exc, "orig", exc))
        if (
            "uq_tracked_sheets_spreadsheet_id_sheet_name" in message
            or "duplicate key value" in message
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tracked sheet with the same spreadsheet_id and sheet_name already exists",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
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
    _admin: AdminApiDep,
    session: SessionDep,
) -> TrackedSheetResponse:
    tracked_sheet = await _get_tracked_sheet_or_404(session, tracked_sheet_id)

    next_sheet_name = payload.sheet_name or tracked_sheet.sheet_name
    next_service = payload.service or Service(tracked_sheet.service.value)
    source_changed = (
        payload.spreadsheet_url is not None or payload.spreadsheet_id is not None
    )
    sheet_name_changed = (
        payload.sheet_name is not None
        and payload.sheet_name != tracked_sheet.sheet_name
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
        message = str(getattr(exc, "orig", exc))
        if (
            "uq_tracked_sheets_spreadsheet_id_sheet_name" in message
            or "duplicate key value" in message
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tracked sheet with the same spreadsheet_id and sheet_name already exists",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        ) from exc

    await session.refresh(tracked_sheet)
    return to_tracked_sheet_response(tracked_sheet)


@router.post(
    "/api/admin/tracked-sheets/{tracked_sheet_id}/activate",
    response_model=TrackedSheetResponse,
)
async def activate_tracked_sheet(
    tracked_sheet_id: int,
    _admin: AdminApiDep,
    session: SessionDep,
) -> TrackedSheetResponse:
    tracked_sheet = await _get_tracked_sheet_or_404(session, tracked_sheet_id)
    tracked_sheet.is_active = True
    await session.commit()
    await session.refresh(tracked_sheet)
    return to_tracked_sheet_response(tracked_sheet)


@router.post(
    "/api/admin/tracked-sheets/{tracked_sheet_id}/deactivate",
    response_model=TrackedSheetResponse,
)
async def deactivate_tracked_sheet(
    tracked_sheet_id: int,
    _admin: AdminApiDep,
    session: SessionDep,
) -> TrackedSheetResponse:
    tracked_sheet = await _get_tracked_sheet_or_404(session, tracked_sheet_id)
    tracked_sheet.is_active = False
    await session.commit()
    await session.refresh(tracked_sheet)
    return to_tracked_sheet_response(tracked_sheet)


@router.delete(
    "/api/admin/tracked-sheets/{tracked_sheet_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_tracked_sheet(
    tracked_sheet_id: int,
    _admin: AdminApiDep,
    session: SessionDep,
) -> Response:
    tracked_sheet = await _get_tracked_sheet_or_404(session, tracked_sheet_id)
    await session.delete(tracked_sheet)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/api/admin/tracked-sheets/{tracked_sheet_id}/sync",
    response_model=TrackedSheetSyncResponse,
)
async def sync_tracked_sheet(
    tracked_sheet_id: int,
    _admin: AdminApiDep,
    session: SessionDep,
) -> TrackedSheetSyncResponse:
    await _get_tracked_sheet_or_404(session, tracked_sheet_id)
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
    ensure_admin_auth_configured()
    if not is_admin_authenticated(request):
        return _admin_login_redirect(request)

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"base_url": settings.BASE_URL.rstrip("/")},
    )


@router.get("/api/analytics/overview", response_model=OverviewResponse)
async def overview(
    _admin: AdminApiDep,
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> OverviewResponse:
    return await get_overview(session=session, service=service, period=period)


@router.get("/api/analytics/funnel", response_model=FunnelResponse)
async def funnel(
    _admin: AdminApiDep,
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> FunnelResponse:
    return await get_funnel(session=session, service=service, period=period)


@router.get("/api/analytics/audience", response_model=AudienceResponse)
async def audience(
    _admin: AdminApiDep,
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> AudienceResponse:
    return await get_audience(session=session, service=service, period=period)


@router.get("/api/analytics/content", response_model=ContentResponse)
async def content(
    _admin: AdminApiDep,
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> ContentResponse:
    return await get_content(session=session, service=service, period=period)


@router.get("/api/analytics/utm", response_model=UTMResponse)
async def utm(
    _admin: AdminApiDep,
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> UTMResponse:
    return await get_utm(session=session, service=service, period=period)


@router.get("/api/analytics/feedback", response_model=FeedbackResponse)
async def feedback(
    _admin: AdminApiDep,
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> FeedbackResponse:
    return await get_feedback(session=session, service=service, period=period)


@router.get("/api/analytics/wishes", response_model=WishesResponse)
async def wishes(
    _admin: AdminApiDep,
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
    _admin: AdminApiDep,
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
    _admin: AdminApiDep,
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
    _admin: AdminApiDep,
    session: SessionDep,
    service: Service = Service.RPP,
    period: Period = Period.DAY,
) -> PaymentSourcesResponse:
    return await get_payment_sources(session=session, service=service, period=period)


@router.get(
    "/api/analytics/payments/recent",
    response_model=RecentPaymentsResponse,
)
async def recent_payments(
    _admin: AdminApiDep,
    session: SessionDep,
    service: Service = Service.RPP,
    limit: int = 10,
) -> RecentPaymentsResponse:
    safe_limit = max(1, min(limit, 100))
    return await get_recent_payments(session=session, service=service, limit=safe_limit)


@router.get(
    "/api/analytics/payments/user-detail",
    response_model=PaymentUserDetailResponse,
)
async def payment_user_detail(
    _admin: AdminApiDep,
    session: SessionDep,
    service: Service = Service.RPP,
    matched_user_tg_id: int = 0,
) -> PaymentUserDetailResponse:
    if matched_user_tg_id <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="matched_user_tg_id must be a positive integer",
        )

    try:
        return await get_payment_user_detail(
            session=session,
            service=service,
            matched_user_tg_id=matched_user_tg_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
