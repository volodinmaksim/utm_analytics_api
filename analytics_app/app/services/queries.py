from sqlalchemy import Numeric, case, cast, exists, func, select, text

from analytics_app.app.db import settings
from analytics_app.app.schemas.analytics import Period, Service
from analytics_app.app.models import (
    Events,
    CbtbaseEvent,
    CbtbaseUser,
    FarmaEvent,
    FarmaUser,
    PaymentEvent,
    PaymentEventType,
    PsygastroEvent,
    PsygastroUser,
    SfbtEvent,
    SfbtUser,
    TrackedSheet,
    User,
)


FEEDBACK_POSITIVE_VOTES = ("like", "up")
FEEDBACK_NEGATIVE_VOTES = ("dislike", "down")

SERVICE_QUERY_CONFIG = {
    Service.RPP: {
        "user_model": User,
        "event_model": Events,
        "payment_user_fk": "user_id",
        "file_event_name": settings.RPP_FILE_EVENT,
    },
    Service.FARMA: {
        "user_model": FarmaUser,
        "event_model": FarmaEvent,
        "payment_user_fk": "farma_user_id",
        "file_event_name": settings.FARMA_FILE_EVENT,
    },
    Service.SFBT: {
        "user_model": SfbtUser,
        "event_model": SfbtEvent,
        "payment_user_fk": "sfbt_user_id",
        "file_event_name": settings.SFBT_FILE_EVENT,
    },
    Service.CBTBASE: {
        "user_model": CbtbaseUser,
        "event_model": CbtbaseEvent,
        "payment_user_fk": "cbtbase_user_id",
        "file_event_name": settings.CBTBASE_FILE_EVENT,
    },
    Service.PSYGASTRO: {
        "user_model": PsygastroUser,
        "event_model": PsygastroEvent,
        "payment_user_fk": "psygastro_user_id",
        "file_event_name": settings.PSYGASTRO_FILE_EVENT,
    },
}


def _wish_prefixes() -> list[str]:
    prefixes = [prefix.strip() for prefix in settings.WISH_PREFIXES.split(",")]
    return [prefix for prefix in prefixes if prefix] or ["user_wish:"]


def _event_model(service: Service):
    return SERVICE_QUERY_CONFIG[service]["event_model"]


def _user_model(service: Service):
    return SERVICE_QUERY_CONFIG[service]["user_model"]


def _payment_user_join_col(service: Service):
    return getattr(PaymentEvent, SERVICE_QUERY_CONFIG[service]["payment_user_fk"])


def _file_event_name(service: Service) -> str:
    return str(SERVICE_QUERY_CONFIG[service]["file_event_name"])


def _payment_identity_expr():
    return func.coalesce(PaymentEvent.matched_user_tg_id, PaymentEvent.platform_id)


def _payment_period_col(period: Period):
    return func.date_trunc(period.value, PaymentEvent.event_date).label("period")


def _matched_payment_after_join_condition(service: Service):
    user_model = _user_model(service)
    join_col = _payment_user_join_col(service)
    return (
        join_col.is_not(None)
        & PaymentEvent.event_date.is_not(None)
        & exists(
            select(1)
            .select_from(user_model)
            .where(user_model.id == join_col)
            .where(user_model.join_date.is_not(None))
            .where(PaymentEvent.event_date >= user_model.join_date)
        )
    )


def total_users(service: Service):
    user_model = _user_model(service)
    return select(func.count(user_model.id).label("total_users"))


def new_users(service: Service, period: Period):
    user_model = _user_model(service)
    period_col = func.date_trunc(period.value, user_model.join_date).label("period")
    return (
        select(period_col, func.count().label("new_users"))
        .group_by(text("period"))
        .order_by(text("period"))
    )


def utm_split(service: Service):
    col = _user_model(service).utm_mark

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
    user_model = _user_model(service)
    period_col = func.date_trunc(period.value, user_model.join_date).label("period")
    col = user_model.utm_mark

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
    col = _user_model(service).utm_mark
    normalized_utm = func.btrim(col).label("utm_mark")

    return (
        select(normalized_utm, func.count().label("users"))
        .where(col.is_not(None))
        .where(func.btrim(col) != "")
        .group_by(normalized_utm)
        .order_by(text("users DESC"), text("utm_mark ASC"))
    )


def utm_payment_efficiency(service: Service):
    user_model = _user_model(service)
    join_col = _payment_user_join_col(service)
    event_model = _event_model(service)
    file_event_name = _file_event_name(service)

    utm_col = func.btrim(user_model.utm_mark).label("utm_mark")
    success_amount = cast(PaymentEvent.amount, Numeric)
    file_received_condition = exists(
        select(1)
        .select_from(event_model)
        .where(event_model.user_id == user_model.id)
        .where(event_model.event_name == file_event_name)
    )

    return (
        select(
            utm_col,
            func.count(func.distinct(user_model.id)).label("users"),
            func.count(func.distinct(user_model.id))
            .filter(file_received_condition)
            .label("file_received_users"),
            func.count(func.distinct(user_model.id))
            .filter(PaymentEvent.id.is_not(None))
            .label("paid_users"),
            func.coalesce(func.sum(success_amount), 0).label("revenue_sum"),
        )
        .select_from(user_model)
        .outerjoin(
            PaymentEvent,
            (join_col == user_model.id)
            & (PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS)
            & (PaymentEvent.service == service.value)
            & (PaymentEvent.event_date.is_not(None))
            & (user_model.join_date.is_not(None))
            & (PaymentEvent.event_date >= user_model.join_date),
        )
        .where(user_model.utm_mark.is_not(None))
        .where(func.btrim(user_model.utm_mark) != "")
        .group_by(utm_col)
        .order_by(text("revenue_sum DESC"), text("users DESC"), text("utm_mark ASC"))
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
    target = _file_event_name(service)

    return select(func.count().label("clicks")).select_from(ev).where(ev.event_name == target)


def file_clicks_timeseries(service: Service, period: Period):
    ev = _event_model(service)
    target = _file_event_name(service)
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
    matched_success = (
        (PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS)
        & _matched_payment_after_join_condition(service)
    )

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
            func.count()
            .filter(matched_success)
            .label("matched_successful_payments_count"),
            func.count(func.distinct(PaymentEvent.matched_user_tg_id))
            .filter(matched_success)
            .label("matched_paid_users_count"),
            func.coalesce(
                func.sum(success_amount).filter(
                    PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS
                ),
                0,
            ).label("revenue_sum"),
            func.coalesce(func.sum(success_amount).filter(matched_success), 0).label(
                "matched_revenue_sum"
            ),
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


def recent_payments(service: Service, limit: int = 10):
    return (
        select(
            PaymentEvent.event_date.label("event_date"),
            cast(PaymentEvent.amount, Numeric).label("amount"),
            PaymentEvent.nickname.label("nickname"),
            PaymentEvent.full_name.label("full_name"),
            PaymentEvent.email.label("email"),
            PaymentEvent.matched_user_tg_id.label("matched_user_tg_id"),
            PaymentEvent.source_sheet_name.label("source_sheet_name"),
        )
        .select_from(PaymentEvent)
        .where(PaymentEvent.service == service.value)
        .where(PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS)
        .where(_matched_payment_after_join_condition(service))
        .order_by(PaymentEvent.event_date.desc().nullslast(), PaymentEvent.id.desc())
        .limit(limit)
    )


def payment_user_profile(service: Service, matched_user_tg_id: int):
    user_model = _user_model(service)
    return (
        select(
            user_model.username.label("username"),
            user_model.tg_id.label("matched_user_tg_id"),
            user_model.join_date.label("join_date"),
            user_model.utm_mark.label("utm_mark"),
        )
        .select_from(user_model)
        .where(user_model.tg_id == matched_user_tg_id)
    )


def payment_user_step_events(service: Service, matched_user_tg_id: int, event_names: tuple[str, ...]):
    ev = _event_model(service)
    user_model = _user_model(service)
    user_join = ev.user_id == user_model.id
    user_filter = user_model.tg_id == matched_user_tg_id

    return (
        select(
            ev.event_name.label("event_name"),
            func.max(ev.timestamp).label("completed_at"),
        )
        .select_from(ev)
        .join(user_model, user_join)
        .where(user_filter)
        .where(ev.event_name.in_(event_names))
        .group_by(ev.event_name)
    )


def payment_user_feedback(service: Service, matched_user_tg_id: int, limit: int = 10):
    ev = _event_model(service)
    name = ev.event_name
    vote_type = func.split_part(name, "_", 2).label("vote")
    post_id = func.split_part(name, "_", 3).label("post_id")
    user_model = _user_model(service)
    user_join = ev.user_id == user_model.id
    user_filter = user_model.tg_id == matched_user_tg_id

    return (
        select(
            ev.timestamp.label("timestamp"),
            post_id,
            vote_type,
        )
        .select_from(ev)
        .join(user_model, user_join)
        .where(user_filter)
        .where(name.like("feedback_%") | name.like("fb_%"))
        .where(post_id.is_not(None))
        .where(func.btrim(post_id) != "")
        .order_by(ev.timestamp.desc())
        .limit(limit)
    )


def payment_user_payments(service: Service, matched_user_tg_id: int, limit: int = 20):
    return (
        select(
            PaymentEvent.event_date.label("event_date"),
            cast(PaymentEvent.amount, Numeric).label("amount"),
            PaymentEvent.source_sheet_name.label("source_sheet_name"),
        )
        .select_from(PaymentEvent)
        .where(PaymentEvent.service == service.value)
        .where(PaymentEvent.event_type == PaymentEventType.PAYMENT_SUCCESS)
        .where(PaymentEvent.matched_user_tg_id == matched_user_tg_id)
        .where(_matched_payment_after_join_condition(service))
        .order_by(PaymentEvent.event_date.desc().nullslast(), PaymentEvent.id.desc())
        .limit(limit)
    )
