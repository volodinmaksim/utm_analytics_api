from sqlalchemy import Numeric, case, cast, func, select, text

from analytics_app.app.db import settings
from analytics_app.app.models.dto import Period, Service
from analytics_app.app.models.orm import (
    Events,
    FarmaEvent,
    FarmaUser,
    PaymentEvent,
    PaymentEventType,
    TrackedSheet,
    User,
)


FEEDBACK_POSITIVE_VOTES = ("like", "up")
FEEDBACK_NEGATIVE_VOTES = ("dislike", "down")


def _wish_prefixes() -> list[str]:
    prefixes = [prefix.strip() for prefix in settings.WISH_PREFIXES.split(",")]
    return [prefix for prefix in prefixes if prefix] or ["user_wish:"]


def _event_model(service: Service):
    return Events if service == Service.RPP else FarmaEvent


def _payment_identity_expr():
    return func.coalesce(PaymentEvent.matched_user_tg_id, PaymentEvent.platform_id)


def _payment_period_col(period: Period):
    return func.date_trunc(period.value, PaymentEvent.event_date).label("period")


def total_users(service: Service):
    if service == Service.RPP:
        return select(func.count(User.id).label("total_users"))
    return select(func.count(FarmaUser.id).label("total_users"))


def new_users(service: Service, period: Period):
    if service == Service.RPP:
        period_col = func.date_trunc(period.value, User.join_date).label("period")
        return (
            select(period_col, func.count().label("new_users"))
            .group_by(text("period"))
            .order_by(text("period"))
        )

    period_col = func.date_trunc(period.value, FarmaUser.join_date).label("period")
    return (
        select(period_col, func.count().label("new_users"))
        .group_by(text("period"))
        .order_by(text("period"))
    )


def utm_split(service: Service):
    col = User.utm_mark if service == Service.RPP else FarmaUser.utm_mark

    with_utm = (
        func.count()
        .filter((col.is_not(None)) & (func.btrim(col) != ""))
        .label("with_utm")
    )
    without_utm = (
        func.count()
        .filter((col.is_(None)) | (func.btrim(col) == ""))
        .label("without_utm")
    )
    return select(with_utm, without_utm)


def utm_timeseries(service: Service, period: Period):
    if service == Service.RPP:
        period_col = func.date_trunc(period.value, User.join_date).label("period")
        col = User.utm_mark
    else:
        period_col = func.date_trunc(period.value, FarmaUser.join_date).label("period")
        col = FarmaUser.utm_mark

    with_utm = (
        func.count()
        .filter((col.is_not(None)) & (func.btrim(col) != ""))
        .label("with_utm")
    )
    without_utm = (
        func.count()
        .filter((col.is_(None)) | (func.btrim(col) == ""))
        .label("without_utm")
    )

    return (
        select(period_col, with_utm, without_utm)
        .group_by(text("period"))
        .order_by(text("period"))
    )


def utm_marks(service: Service):
    col = User.utm_mark if service == Service.RPP else FarmaUser.utm_mark
    normalized_utm = func.btrim(col).label("utm_mark")

    return (
        select(normalized_utm, func.count().label("users"))
        .where(col.is_not(None))
        .where(func.btrim(col) != "")
        .group_by(normalized_utm)
        .order_by(text("users DESC"), text("utm_mark ASC"))
    )


def segments_rpp():
    base_total = (
        select(func.count(User.id))
        .where(User.segment.in_(("pro", "beginner")))
        .scalar_subquery()
    )

    denom = func.nullif(cast(base_total, Numeric), 0)
    ratio = (cast(func.count(User.id), Numeric) * 100) / denom
    pct = func.round(ratio, 2).label("pct")

    return (
        select(User.segment.label("segment"), func.count().label("users"), pct)
        .where(User.segment.in_(("pro", "beginner")))
        .group_by(User.segment)
        .order_by(User.segment)
    )


def branches_rpp():
    branch = case(
        (User.segment == "beginner", "beginner"),
        (User.segment == "pro", "pro"),
        else_="not_selected",
    ).label("branch")

    return (
        select(branch, func.count(User.id).label("users"))
        .group_by(branch)
        .order_by(text("users DESC"), text("branch ASC"))
    )


def event_user_counts(service: Service, event_names: tuple[str, ...]):
    ev = _event_model(service)
    return (
        select(
            ev.event_name.label("event_name"),
            func.count(func.distinct(ev.user_id)).label("users"),
        )
        .where(ev.event_name.in_(event_names))
        .group_by(ev.event_name)
    )


def post_reactions(service: Service):
    ev = _event_model(service)
    name = ev.event_name

    vote_type = func.split_part(name, "_", 2).label("vote_type")
    post_id = func.split_part(name, "_", 3).label("post_id")
    likes = func.count().filter(vote_type.in_(FEEDBACK_POSITIVE_VOTES)).label("likes")
    dislikes = func.count().filter(vote_type.in_(FEEDBACK_NEGATIVE_VOTES)).label("dislikes")
    rating = (
        func.count().filter(vote_type.in_(FEEDBACK_POSITIVE_VOTES))
        - func.count().filter(vote_type.in_(FEEDBACK_NEGATIVE_VOTES))
    ).label("rating")

    return (
        select(post_id, likes, dislikes, rating)
        .select_from(ev)
        .where(name.like("feedback_%") | name.like("fb_%"))
        .where(post_id.is_not(None))
        .where(func.btrim(post_id) != "")
        .group_by(post_id)
        .order_by(text("rating DESC"), text("likes DESC"))
        .limit(settings.POSTS_LIMIT)
    )


def wishes(service: Service):
    ev = _event_model(service)
    name = ev.event_name

    condition = None
    for prefix in _wish_prefixes():
        current = name.like(f"{prefix}%")
        condition = current if condition is None else (condition | current)

    wish_text = case(
        (
            name.like("user_wish:%"),
            func.btrim(func.substring(name, len("user_wish:") + 1)),
        ),
        else_=name,
    ).label("wish_text")

    return (
        select(ev.timestamp.label("timestamp"), wish_text)
        .where(condition)
        .order_by(ev.timestamp.desc())
        .limit(settings.WISHES_LIMIT)
    )


def file_clicks(service: Service):
    ev = _event_model(service)
    target = settings.RPP_FILE_EVENT if service == Service.RPP else settings.FARMA_FILE_EVENT

    return select(func.count().label("clicks")).select_from(ev).where(ev.event_name == target)


def file_clicks_timeseries(service: Service, period: Period):
    ev = _event_model(service)
    target = settings.RPP_FILE_EVENT if service == Service.RPP else settings.FARMA_FILE_EVENT
    period_col = func.date_trunc(period.value, ev.timestamp).label("period")

    return (
        select(period_col, func.count().label("clicks"))
        .select_from(ev)
        .where(ev.event_name == target)
        .group_by(text("period"))
        .order_by(text("period"))
    )


def payment_overview(service: Service):
    payment_identity = _payment_identity_expr()
    success_amount = cast(PaymentEvent.amount, Numeric)

    return (
        select(
            func.count()
            .filter(PaymentEvent.event_type == PaymentEventType.PAYMENT_CLICK)
            .label("payment_clicks_count"),
            func.count()
            .filter(PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS)
            .label("successful_payments_count"),
            func.count(func.distinct(payment_identity))
            .filter(
                (PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS)
                & (payment_identity.is_not(None))
            )
            .label("paid_users_count"),
            func.coalesce(
                func.sum(success_amount).filter(
                    PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS
                ),
                0,
            ).label("revenue_sum"),
            func.avg(success_amount)
            .filter(PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS)
            .label("avg_payment_amount"),
            func.count()
            .filter(
                (PaymentEvent.matched_user_tg_id.is_(None))
                & (PaymentEvent.event_type.in_((
                    PaymentEventType.PAYMENT_CLICK,
                    PaymentEventType.PAYMENT_SUCCESS,
                )))
            )
            .label("unmatched_events_count"),
        )
        .select_from(PaymentEvent)
        .where(PaymentEvent.service == service.value)
    )


def payment_timeseries(service: Service, period: Period):
    period_col = _payment_period_col(period)
    payment_identity = _payment_identity_expr()
    success_amount = cast(PaymentEvent.amount, Numeric)

    return (
        select(
            period_col,
            func.count()
            .filter(PaymentEvent.event_type == PaymentEventType.PAYMENT_CLICK)
            .label("payment_clicks_count"),
            func.count()
            .filter(PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS)
            .label("successful_payments_count"),
            func.coalesce(
                func.sum(success_amount).filter(
                    PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS
                ),
                0,
            ).label("revenue_sum"),
            func.count(func.distinct(payment_identity))
            .filter(
                (PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS)
                & (payment_identity.is_not(None))
            )
            .label("paid_users_count"),
        )
        .select_from(PaymentEvent)
        .where(PaymentEvent.service == service.value)
        .where(PaymentEvent.event_date.is_not(None))
        .group_by(text("period"))
        .order_by(text("period"))
    )


def payment_sources(service: Service):
    success_amount = cast(PaymentEvent.amount, Numeric)

    return (
        select(
            TrackedSheet.id.label("tracked_sheet_id"),
            TrackedSheet.service.label("service"),
            TrackedSheet.spreadsheet_id.label("spreadsheet_id"),
            TrackedSheet.sheet_name.label("sheet_name"),
            TrackedSheet.is_active.label("is_active"),
            func.count(PaymentEvent.id).label("events_count"),
            func.count(PaymentEvent.id)
            .filter(PaymentEvent.event_type == PaymentEventType.PAYMENT_CLICK)
            .label("payment_clicks_count"),
            func.count(PaymentEvent.id)
            .filter(PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS)
            .label("successful_payments_count"),
            func.coalesce(
                func.sum(success_amount).filter(
                    PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS
                ),
                0,
            ).label("revenue_sum"),
            func.count(PaymentEvent.id)
            .filter(PaymentEvent.matched_user_tg_id.is_(None))
            .label("unmatched_events_count"),
            TrackedSheet.last_sync_started_at.label("last_sync_started_at"),
            TrackedSheet.last_sync_finished_at.label("last_sync_finished_at"),
            TrackedSheet.last_sync_status.label("last_sync_status"),
            TrackedSheet.last_sync_error.label("last_sync_error"),
            TrackedSheet.last_sync_rows_read.label("last_sync_rows_read"),
            TrackedSheet.last_sync_rows_inserted.label("last_sync_rows_inserted"),
        )
        .select_from(TrackedSheet)
        .outerjoin(PaymentEvent, PaymentEvent.tracked_sheet_id == TrackedSheet.id)
        .where(TrackedSheet.service == service.value)
        .group_by(
            TrackedSheet.id,
            TrackedSheet.service,
            TrackedSheet.spreadsheet_id,
            TrackedSheet.sheet_name,
            TrackedSheet.is_active,
            TrackedSheet.last_sync_started_at,
            TrackedSheet.last_sync_finished_at,
            TrackedSheet.last_sync_status,
            TrackedSheet.last_sync_error,
            TrackedSheet.last_sync_rows_read,
            TrackedSheet.last_sync_rows_inserted,
        )
        .order_by(TrackedSheet.id.desc())
    )
