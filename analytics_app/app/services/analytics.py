from typing import Any, Awaitable, Callable, TypeVar

from pydantic import BaseModel
from sqlalchemy.exc import ProgrammingError

from analytics_app.app.db import get_scoped_session, settings
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
    Period,
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
    ("file_received", 'Получить файл: "Пакет инструментов для работы с РПП от Ирины Ушаковой"'),
    ("survey_15min_sent", "survey_15min_sent"),
    ("continue_yes", "extra_yes"),
    ("reviews_opened", "reviews_opened"),
    ("wish_submitted", "wish_submitted"),
)

FARMA_FUNNEL_EVENTS = (
    ("file_received", 'Получить файл: "Гайд по серотониновому синдрому"'),
)

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
}

cache = TTLCache(ttl_seconds=settings.CACHE_TTL)


async def _exec_one(session, stmt) -> dict[str, Any]:
    result = await session.execute(stmt)
    row = result.mappings().first()
    return dict(row) if row else {}


async def _exec_all(session, stmt) -> list[dict[str, Any]]:
    result = await session.execute(stmt)
    return [dict(row) for row in result.mappings().all()]


def _cache_key(section: str, service: Service, period: Period) -> str:
    return f"{section}:{service.value}:{period.value}"


def _pct(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round((numerator / denominator) * 100, 2)


def _is_missing_table_error(exc: ProgrammingError) -> bool:
    message = str(exc)
    return "UndefinedTableError" in message or 'does not exist' in message


async def _cached_section(
    section: str,
    service: Service,
    period: Period,
    loader: Callable[[Any], Awaitable[R]],
    model: type[R],
    fallback: Callable[[], R] | None = None,
) -> R:
    key = _cache_key(section, service, period)
    cached = cache.get(key)
    if cached is not None:
        return model.model_validate(cached)

    scoped_session = get_scoped_session()
    session = scoped_session()
    try:
        payload = await loader(session)
    except ProgrammingError as exc:
        if fallback is not None and _is_missing_table_error(exc):
            payload = fallback()
        else:
            raise
    finally:
        await session.close()
        await scoped_session.remove()

    cache.set(
        key,
        payload.model_dump(mode="json"),
        ttl_seconds=SECTION_TTLS.get(section),
    )
    return payload


async def get_overview(service: Service, period: Period) -> OverviewResponse:
    async def loader(session) -> OverviewResponse:
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


async def get_funnel(service: Service, period: Period) -> FunnelResponse:
    async def loader(session) -> FunnelResponse:
        total_users = await _exec_one(session, queries.total_users(service))
        new_users = await _exec_all(session, queries.new_users(service, period))

        step_definitions = RPP_FUNNEL_EVENTS if service == Service.RPP else FARMA_FUNNEL_EVENTS
        event_counts = await _exec_all(
            session,
            queries.event_user_counts(service, tuple(event for _, event in step_definitions)),
        )
        event_map = {row["event_name"]: int(row.get("users", 0) or 0) for row in event_counts}

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
        loader,
        FunnelResponse,
        fallback=lambda: FunnelResponse(service=service, period=period, new_users=[], steps=[]),
    )


async def get_audience(service: Service, period: Period) -> AudienceResponse:
    async def loader(session) -> AudienceResponse:
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

    return await _cached_section("audience", service, period, loader, AudienceResponse)


async def get_content(service: Service, period: Period) -> ContentResponse:
    async def loader(session) -> ContentResponse:
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
        loader,
        ContentResponse,
        fallback=lambda: ContentResponse(service=service, items=[]),
    )


async def get_utm(service: Service, period: Period) -> UTMResponse:
    async def loader(session) -> UTMResponse:
        marks = await _exec_all(session, queries.utm_marks(service))
        timeseries = await _exec_all(session, queries.utm_timeseries(service, period))
        return UTMResponse(
            service=service,
            period=period,
            marks=[
                UtmMarkRow(
                    utm_mark=str(item.get("utm_mark") or ""),
                    users=int(item.get("users", 0) or 0),
                )
                for item in marks
            ],
            timeseries=[UtmTimeseriesRow.model_validate(item) for item in timeseries],
        )

    return await _cached_section(
        "utm",
        service,
        period,
        loader,
        UTMResponse,
        fallback=lambda: UTMResponse(service=service, period=period, marks=[], timeseries=[]),
    )


async def get_feedback(service: Service, period: Period) -> FeedbackResponse:
    async def loader(session) -> FeedbackResponse:
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
        loader,
        FeedbackResponse,
        fallback=lambda: FeedbackResponse(service=service, items=[]),
    )


async def get_wishes(service: Service, period: Period) -> WishesResponse:
    async def loader(session) -> WishesResponse:
        items = await _exec_all(session, queries.wishes(service))
        return WishesResponse(
            service=service,
            items=[WishRow.model_validate(item) for item in items],
        )

    return await _cached_section(
        "wishes",
        service,
        period,
        loader,
        WishesResponse,
        fallback=lambda: WishesResponse(service=service, items=[]),
    )
