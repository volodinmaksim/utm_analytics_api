from sqlalchemy import Numeric, case, cast, func, select, text

from analytics_app.app.db import settings
from analytics_app.app.models.dto import Period, Service
from analytics_app.app.models.orm import Events, FarmaEvent, FarmaUser, User


FEEDBACK_POSITIVE_VOTES = ("like", "up")
FEEDBACK_NEGATIVE_VOTES = ("dislike", "down")


def _wish_prefixes() -> list[str]:
    prefixes = [prefix.strip() for prefix in settings.WISH_PREFIXES.split(",")]
    return [prefix for prefix in prefixes if prefix] or ["user_wish:"]


def _event_model(service: Service):
    return Events if service == Service.RPP else FarmaEvent


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
