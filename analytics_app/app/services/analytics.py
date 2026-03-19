from decimal import Decimal
from typing import Any, Awaitable, Callable, TypeVar

from pydantic import BaseModel
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.db import settings
from analytics_app.app.models.dto import (
    AudienceResponse,
    AudienceRow,
    ContentEventRow,
    ContentResponse,
    FeedbackResponse,
    FeedbackRow,
    FunnelResponse,
    FunnelStepRow,
    NewUsersRow,
    OverviewResponse,
    PaymentOverviewResponse,
    PaymentSourceRow,
    PaymentSourcesResponse,
    PaymentTimeseriesResponse,
    PaymentTimeseriesRow,
    PaymentUserDetailResponse,
    PaymentUserFeedbackRow,
    PaymentUserHistoryPaymentRow,
    PaymentUserStepRow,
    Period,
    RecentPaymentRow,
    RecentPaymentsResponse,
    Service,
    UTMResponse,
    UtmMarkRow,
    UtmTimeseriesRow,
    WishesResponse,
    WishRow,
)
from analytics_app.app.services import queries
from analytics_app.app.services.cache import TTLCache

R = TypeVar("R", bound=BaseModel)

RPP_FUNNEL_EVENTS = (
    ("file_received", settings.RPP_FILE_EVENT),
    ("survey_15min_sent", "survey_15min_sent"),
    ("continue_yes", "extra_yes"),
    ("reviews_opened", "reviews_opened"),
    ("wish_submitted", "wish_submitted"),
)

FARMA_FUNNEL_EVENTS = (("file_received", settings.FARMA_FILE_EVENT),)

FUNNEL_LABELS = {
    "registered": "Пользователи в базе",
    "file_received": "Получили файл",
    "survey_15min_sent": "Получили 15-минутный опрос",
    "continue_yes": "Согласились продолжить",
    "reviews_opened": "Открыли отзывы",
    "wish_submitted": "Отправили пожелание",
}

CONTENT_EVENT_LABELS = {
    "survey_15min_sent": "15-минутный опрос отправлен",
    "extra_yes": "Продолжить: да",
    "extra_no": "Продолжить: нет",
    "post_sent_1beg": "Beginner: пост 1",
    "post_sent_2beg": "Beginner: пост 2",
    "post_sent_3beg": "Beginner: пост 3",
    "post_sent_4beg": "Beginner: пост 4",
    "post_sent_5beg": "Beginner: пост 5",
    "post_sent_6beg": "Beginner: пост 6",
    "post_sent_7beg": "Beginner: пост 7",
    "post_sent_8beg": "Beginner: пост 8",
    "post_sent_7pro": "Pro: пост 7",
    "post_sent_8pro": "Pro: пост 8",
    "post_sent_9pro": "Pro: пост 9",
    "post_sent_10pro": "Pro: пост 10",
    "post_sent_11pro": "Pro: пост 11",
    "post_sent_12pro": "Pro: пост 12",
    "post_sent_final_up": "Финал вверх",
    "post_sent_final_down": "Финал вниз",
    "survey_yes": "Ответ на survey: да",
    "survey_no": "Ответ на survey: нет",
    "decided_continue": "Передумали продолжить",
    "reviews_opened": "Открыли отзывы",
    "wish_submitted": "Отправили пожелание",
}

SECTION_TTLS = {
    "overview": 30,
    "funnel": 60,
    "audience": 120,
    "content": 120,
    "utm": 180,
    "feedback": 60,
    "wishes": 20,
    "payments_overview": 30,
    "payments_timeseries": 60,
    "payments_sources": 60,
}

cache = TTLCache(ttl_seconds=settings.CACHE_TTL)


async def _exec_one(session: AsyncSession, stmt) -> dict[str, Any]:
    result = await session.execute(stmt)
    row = result.mappings().first()
    return dict(row) if row else {}


async def _exec_all(session: AsyncSession, stmt) -> list[dict[str, Any]]:
    result = await session.execute(stmt)
    return [dict(row) for row in result.mappings().all()]


def _cache_key(section: str, service: Service, period: Period) -> str:
    return f"{section}:{service.value}:{period.value}"


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100, 2)


def _to_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    return float(value)


def _to_optional_float(value: Decimal | float | int | None) -> float | None:
    if value is None:
        return None
    return float(value)


def _is_missing_table_error(exc: ProgrammingError) -> bool:
    message = str(exc)
    return "UndefinedTableError" in message or "does not exist" in message


async def _cached_section(
    section: str,
    service: Service,
    period: Period,
    session: AsyncSession,
    loader: Callable[[AsyncSession], Awaitable[R]],
    model: type[R],
    fallback: Callable[[], R] | None = None,
) -> R:
    key = _cache_key(section, service, period)
    cached = cache.get(key)
    if cached is not None:
        return model.model_validate(cached)

    try:
        payload = await loader(session)
    except ProgrammingError as exc:
        if fallback is not None and _is_missing_table_error(exc):
            payload = fallback()
        else:
            raise

    cache.set(
        key, payload.model_dump(mode="json"), ttl_seconds=SECTION_TTLS.get(section)
    )
    return payload


async def get_overview(
    session: AsyncSession, service: Service, period: Period
) -> OverviewResponse:
    async def loader(session: AsyncSession) -> OverviewResponse:
        total_users = await _exec_one(session, queries.total_users(service))
        utm_split = await _exec_one(session, queries.utm_split(service))
        file_clicks = await _exec_one(session, queries.file_clicks(service))
        return OverviewResponse(
            service=service,
            period=period,
            total_users=int(total_users.get("total_users", 0) or 0),
            file_clicks=int(file_clicks.get("clicks", 0) or 0),
            with_utm=int(utm_split.get("with_utm", 0) or 0),
            without_utm=int(utm_split.get("without_utm", 0) or 0),
        )

    return await _cached_section(
        "overview",
        service,
        period,
        session,
        loader,
        OverviewResponse,
        fallback=lambda: OverviewResponse(
            service=service,
            period=period,
            total_users=0,
            file_clicks=0,
            with_utm=0,
            without_utm=0,
        ),
    )


async def get_funnel(
    session: AsyncSession, service: Service, period: Period
) -> FunnelResponse:
    async def loader(session: AsyncSession) -> FunnelResponse:
        total_users = await _exec_one(session, queries.total_users(service))
        new_users = await _exec_all(session, queries.new_users(service, period))

        step_definitions = (
            RPP_FUNNEL_EVENTS if service == Service.RPP else FARMA_FUNNEL_EVENTS
        )
        event_counts = await _exec_all(
            session,
            queries.event_user_counts(
                service, tuple(event for _, event in step_definitions)
            ),
        )
        event_map = {
            row["event_name"]: int(row.get("users", 0) or 0) for row in event_counts
        }

        steps: list[FunnelStepRow] = []
        start_users = int(total_users.get("total_users", 0) or 0)
        previous_users = start_users
        steps.append(
            FunnelStepRow(
                key="registered",
                label=FUNNEL_LABELS["registered"],
                users=start_users,
                conversion_from_start=100.0 if start_users else None,
                conversion_from_previous=100.0 if start_users else None,
            )
        )

        for key, event_name in step_definitions:
            users = event_map.get(event_name, 0)
            steps.append(
                FunnelStepRow(
                    key=key,
                    label=FUNNEL_LABELS[key],
                    users=users,
                    conversion_from_start=_pct(users, start_users),
                    conversion_from_previous=_pct(users, previous_users),
                )
            )
            previous_users = users

        return FunnelResponse(
            service=service,
            period=period,
            new_users=[NewUsersRow.model_validate(item) for item in new_users],
            steps=steps,
        )

    return await _cached_section(
        "funnel",
        service,
        period,
        session,
        loader,
        FunnelResponse,
        fallback=lambda: FunnelResponse(
            service=service, period=period, new_users=[], steps=[]
        ),
    )


async def get_audience(
    session: AsyncSession, service: Service, period: Period
) -> AudienceResponse:
    async def loader(session: AsyncSession) -> AudienceResponse:
        if service != Service.RPP:
            return AudienceResponse(service=service, segments=[], branches=[])

        segments = await _exec_all(session, queries.segments_rpp())
        branches = await _exec_all(session, queries.branches_rpp())
        return AudienceResponse(
            service=service,
            segments=[
                AudienceRow(
                    name=str(item.get("segment") or ""),
                    users=int(item.get("users", 0) or 0),
                    pct=float(item["pct"]) if item.get("pct") is not None else None,
                )
                for item in segments
            ],
            branches=[
                AudienceRow(
                    name=str(item.get("branch") or ""),
                    users=int(item.get("users", 0) or 0),
                    pct=None,
                )
                for item in branches
            ],
        )

    return await _cached_section(
        "audience", service, period, session, loader, AudienceResponse
    )


async def get_content(
    session: AsyncSession, service: Service, period: Period
) -> ContentResponse:
    async def loader(session: AsyncSession) -> ContentResponse:
        rows = await _exec_all(
            session,
            queries.event_user_counts(service, tuple(CONTENT_EVENT_LABELS.keys())),
        )
        event_map = {row["event_name"]: int(row.get("users", 0) or 0) for row in rows}
        items = [
            ContentEventRow(key=key, label=label, users=event_map.get(key, 0))
            for key, label in CONTENT_EVENT_LABELS.items()
            if event_map.get(key, 0) > 0
        ]
        return ContentResponse(service=service, items=items)

    return await _cached_section(
        "content",
        service,
        period,
        session,
        loader,
        ContentResponse,
        fallback=lambda: ContentResponse(service=service, items=[]),
    )


async def get_utm(
    session: AsyncSession, service: Service, period: Period
) -> UTMResponse:
    async def loader(session: AsyncSession) -> UTMResponse:
        marks = await _exec_all(session, queries.utm_payment_efficiency(service))
        timeseries = await _exec_all(session, queries.utm_timeseries(service, period))
        return UTMResponse(
            service=service,
            period=period,
            marks=[
                UtmMarkRow(
                    utm_mark=str(item.get("utm_mark") or ""),
                    users=int(item.get("users", 0) or 0),
                    paid_users=int(item.get("paid_users", 0) or 0),
                    file_received_users=int(item.get("file_received_users", 0) or 0),
                    revenue_sum=round(_to_float(item.get("revenue_sum")), 2),
                    conversion_to_payment=_pct(
                        int(item.get("paid_users", 0) or 0),
                        int(item.get("users", 0) or 0),
                    ),
                )
                for item in marks
            ],
            timeseries=[UtmTimeseriesRow.model_validate(item) for item in timeseries],
        )

    return await _cached_section(
        "utm",
        service,
        period,
        session,
        loader,
        UTMResponse,
        fallback=lambda: UTMResponse(
            service=service, period=period, marks=[], timeseries=[]
        ),
    )


async def get_feedback(
    session: AsyncSession, service: Service, period: Period
) -> FeedbackResponse:
    async def loader(session: AsyncSession) -> FeedbackResponse:
        items = await _exec_all(session, queries.post_reactions(service))
        return FeedbackResponse(
            service=service,
            items=[
                FeedbackRow(
                    post_id=str(item.get("post_id") or ""),
                    likes=int(item.get("likes", 0) or 0),
                    dislikes=int(item.get("dislikes", 0) or 0),
                    rating=int(item.get("rating", 0) or 0),
                )
                for item in items
            ],
        )

    return await _cached_section(
        "feedback",
        service,
        period,
        session,
        loader,
        FeedbackResponse,
        fallback=lambda: FeedbackResponse(service=service, items=[]),
    )


async def get_wishes(
    session: AsyncSession, service: Service, period: Period
) -> WishesResponse:
    async def loader(session: AsyncSession) -> WishesResponse:
        items = await _exec_all(session, queries.wishes(service))
        return WishesResponse(
            service=service,
            items=[WishRow.model_validate(item) for item in items],
        )

    return await _cached_section(
        "wishes",
        service,
        period,
        session,
        loader,
        WishesResponse,
        fallback=lambda: WishesResponse(service=service, items=[]),
    )



async def get_payment_overview(
    session: AsyncSession, service: Service, period: Period
) -> PaymentOverviewResponse:
    async def loader(session: AsyncSession) -> PaymentOverviewResponse:
        raw = await _exec_one(session, queries.payment_overview(service))
        payment_clicks_count = int(raw.get("payment_clicks_count", 0) or 0)
        successful_payments_count = int(raw.get("successful_payments_count", 0) or 0)
        paid_users_count = int(raw.get("paid_users_count", 0) or 0)
        matched_successful_payments_count = int(
            raw.get("matched_successful_payments_count", 0) or 0
        )
        matched_paid_users_count = int(raw.get("matched_paid_users_count", 0) or 0)
        revenue_sum = _to_float(raw.get("revenue_sum"))
        matched_revenue_sum = _to_float(raw.get("matched_revenue_sum"))
        avg_payment_amount = _to_optional_float(raw.get("avg_payment_amount"))
        arppu = None
        if paid_users_count > 0:
            arppu = round(revenue_sum / paid_users_count, 2)

        return PaymentOverviewResponse(
            service=service,
            period=period,
            payment_clicks_count=payment_clicks_count,
            successful_payments_count=successful_payments_count,
            paid_users_count=paid_users_count,
            matched_successful_payments_count=matched_successful_payments_count,
            matched_paid_users_count=matched_paid_users_count,
            revenue_sum=round(revenue_sum, 2),
            matched_revenue_sum=round(matched_revenue_sum, 2),
            avg_payment_amount=(
                round(avg_payment_amount, 2)
                if avg_payment_amount is not None
                else None
            ),
            arppu=arppu,
            click_to_success_conversion=_pct(
                successful_payments_count,
                payment_clicks_count,
            ),
            unmatched_events_count=int(raw.get("unmatched_events_count", 0) or 0),
        )

    return await _cached_section(
        "payments_overview",
        service,
        period,
        session,
        loader,
        PaymentOverviewResponse,
        fallback=lambda: PaymentOverviewResponse(
            service=service,
            period=period,
            payment_clicks_count=0,
            successful_payments_count=0,
            paid_users_count=0,
            matched_successful_payments_count=0,
            matched_paid_users_count=0,
            revenue_sum=0.0,
            matched_revenue_sum=0.0,
            avg_payment_amount=None,
            arppu=None,
            click_to_success_conversion=None,
            unmatched_events_count=0,
        ),
    )


async def get_payment_timeseries(
    session: AsyncSession, service: Service, period: Period
) -> PaymentTimeseriesResponse:
    async def loader(session: AsyncSession) -> PaymentTimeseriesResponse:
        rows = await _exec_all(session, queries.payment_timeseries(service, period))
        return PaymentTimeseriesResponse(
            service=service,
            period=period,
            items=[
                PaymentTimeseriesRow(
                    period=item.get("period"),
                    payment_clicks_count=int(item.get("payment_clicks_count", 0) or 0),
                    successful_payments_count=int(item.get("successful_payments_count", 0) or 0),
                    revenue_sum=round(_to_float(item.get("revenue_sum")), 2),
                    paid_users_count=int(item.get("paid_users_count", 0) or 0),
                )
                for item in rows
            ],
        )

    return await _cached_section(
        "payments_timeseries",
        service,
        period,
        session,
        loader,
        PaymentTimeseriesResponse,
        fallback=lambda: PaymentTimeseriesResponse(
            service=service,
            period=period,
            items=[],
        ),
    )


async def get_payment_sources(
    session: AsyncSession, service: Service, period: Period
) -> PaymentSourcesResponse:
    async def loader(session: AsyncSession) -> PaymentSourcesResponse:
        rows = await _exec_all(session, queries.payment_sources(service))
        return PaymentSourcesResponse(
            service=service,
            period=period,
            items=[
                PaymentSourceRow(
                    tracked_sheet_id=int(item.get("tracked_sheet_id") or 0),
                    service=Service(
                        getattr(item.get("service"), "value", item.get("service"))
                        or service.value
                    ),
                    spreadsheet_id=str(item.get("spreadsheet_id") or ""),
                    sheet_name=str(item.get("sheet_name") or ""),
                    is_active=bool(item.get("is_active")),
                    events_count=int(item.get("events_count", 0) or 0),
                    payment_clicks_count=int(item.get("payment_clicks_count", 0) or 0),
                    successful_payments_count=int(item.get("successful_payments_count", 0) or 0),
                    revenue_sum=round(_to_float(item.get("revenue_sum")), 2),
                    unmatched_events_count=int(item.get("unmatched_events_count", 0) or 0),
                    last_sync_started_at=item.get("last_sync_started_at"),
                    last_sync_finished_at=item.get("last_sync_finished_at"),
                    last_sync_status=(
                        getattr(item.get("last_sync_status"), "value", item.get("last_sync_status"))
                        if item.get("last_sync_status") is not None
                        else None
                    ),
                    last_sync_error=item.get("last_sync_error"),
                    last_sync_rows_read=item.get("last_sync_rows_read"),
                    last_sync_rows_inserted=item.get("last_sync_rows_inserted"),
                )
                for item in rows
            ],
        )

    return await _cached_section(
        "payments_sources",
        service,
        period,
        session,
        loader,
        PaymentSourcesResponse,
        fallback=lambda: PaymentSourcesResponse(
            service=service,
            period=period,
            items=[],
        ),
    )



async def get_payment_user_detail(
    session: AsyncSession,
    service: Service,
    matched_user_tg_id: int,
) -> PaymentUserDetailResponse:
    async def loader(session: AsyncSession) -> PaymentUserDetailResponse:
        profile = await _exec_one(
            session,
            queries.payment_user_profile(service, matched_user_tg_id),
        )
        if not profile:
            raise ValueError("User not found in local database")

        step_definitions = (
            RPP_FUNNEL_EVENTS if service == Service.RPP else FARMA_FUNNEL_EVENTS
        )
        step_rows = await _exec_all(
            session,
            queries.payment_user_step_events(
                service,
                matched_user_tg_id,
                tuple(event_name for _, event_name in step_definitions),
            ),
        )
        step_map = {
            str(item.get("event_name") or ""): item.get("completed_at")
            for item in step_rows
        }

        feedback_rows = await _exec_all(
            session,
            queries.payment_user_feedback(service, matched_user_tg_id),
        )
        payment_rows = await _exec_all(
            session,
            queries.payment_user_payments(service, matched_user_tg_id),
        )

        return PaymentUserDetailResponse(
            service=service,
            matched_user_tg_id=matched_user_tg_id,
            username=profile.get("username"),
            join_date=profile.get("join_date"),
            utm_mark=profile.get("utm_mark"),
            steps=[
                PaymentUserStepRow(
                    key=key,
                    label=FUNNEL_LABELS.get(key, key),
                    completed_at=step_map.get(event_name),
                )
                for key, event_name in step_definitions
            ],
            feedback=[
                PaymentUserFeedbackRow(
                    timestamp=item.get("timestamp"),
                    post_id=str(item.get("post_id") or ""),
                    vote=str(item.get("vote") or ""),
                )
                for item in feedback_rows
            ],
            payments=[
                PaymentUserHistoryPaymentRow(
                    event_date=item.get("event_date"),
                    amount=round(_to_float(item.get("amount")), 2),
                    source_sheet_name=str(item.get("source_sheet_name") or ""),
                )
                for item in payment_rows
            ],
        )

    return await _cached_section(
        f"payment_user_detail_{matched_user_tg_id}",
        service,
        Period.DAY,
        session,
        loader,
        PaymentUserDetailResponse,
    )


async def get_recent_payments(
    session: AsyncSession,
    service: Service,
    limit: int = 10,
) -> RecentPaymentsResponse:
    async def loader(session: AsyncSession) -> RecentPaymentsResponse:
        rows = await _exec_all(session, queries.recent_payments(service, limit))
        return RecentPaymentsResponse(
            service=service,
            items=[
                RecentPaymentRow(
                    event_date=item.get("event_date"),
                    amount=round(_to_float(item.get("amount")), 2),
                    nickname=item.get("nickname"),
                    full_name=item.get("full_name"),
                    email=item.get("email"),
                    matched_user_tg_id=item.get("matched_user_tg_id"),
                    source_sheet_name=str(item.get("source_sheet_name") or ""),
                )
                for item in rows
            ],
        )

    return await _cached_section(
        f"recent_payments_{limit}",
        service,
        Period.DAY,
        session,
        loader,
        RecentPaymentsResponse,
        fallback=lambda: RecentPaymentsResponse(service=service, items=[]),
    )
