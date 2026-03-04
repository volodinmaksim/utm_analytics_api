from __future__ import annotations

from typing import Literal

from sqlalchemy import select, func, text, case

from appv1.config import settings
from appv1.models import User, Events, FarmaUser, FarmaEvent

Service = Literal["rpp", "farma"]
Period = Literal["day", "week", "month"]


def total_users(service: Service):
    if service == "rpp":
        return select(func.count(User.id).label("total_users"))
    return select(func.count(FarmaUser.id).label("total_users"))


def new_users(service: Service, period: Period):
    if service == "rpp":
        period_col = func.date_trunc(period, User.join_date).label("period")
        return (
            select(period_col, func.count().label("new_users"))
            .group_by(text("period"))
            .order_by(text("period"))
        )

    period_col = func.date_trunc(period, FarmaUser.join_date).label("period")
    return (
        select(period_col, func.count().label("new_users"))
        .group_by(text("period"))
        .order_by(text("period"))
    )


def utm_split(service: Service):
    if service == "rpp":
        col = User.utm_mark
    else:
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
    return select(with_utm, without_utm)


def utm_timeseries(service: Service, period: Period):
    if service == "rpp":
        period_col = func.date_trunc(period, User.join_date).label("period")
        col = User.utm_mark
    else:
        period_col = func.date_trunc(period, FarmaUser.join_date).label("period")
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


def segments_rpp():
    base_total = (
        select(func.count(User.id))
        .where(User.segment.in_(("pro", "beginner")))
        .scalar_subquery()
    )

    pct = func.round(
        100.0
        * func.count(User.id)
        / func.nullif(func.cast(base_total, func.float), 0.0),
        2,
    ).label("pct")

    return (
        select(User.segment.label("segment"), func.count().label("users"), pct)
        .where(User.segment.in_(("pro", "beginner")))
        .group_by(User.segment)
        .order_by(User.segment)
    )


def post_reactions(service: Service):
    """
    Реальный формат из твоих роутеров: feedback_{vote_type}_{post_id}
    vote_type ожидаем like/dislike
    """
    ev = Events if service == "rpp" else FarmaEvent
    name = ev.event_name

    is_fb = name.like("feedback_%")

    vote_type = func.split_part(name, "_", 2).label("vote_type")
    post_id = func.split_part(name, "_", 3).label("post_id")

    likes = func.count().filter(vote_type == "like").label("likes")
    dislikes = func.count().filter(vote_type == "dislike").label("dislikes")
    rating = (
        func.count().filter(vote_type == "like")
        - func.count().filter(vote_type == "dislike")
    ).label("rating")

    return (
        select(post_id, likes, dislikes, rating)
        .select_from(ev)
        .where(is_fb)
        .where(post_id.is_not(None))
        .where(func.btrim(post_id) != "")
        .group_by(post_id)
        .order_by(text("rating DESC"), text("likes DESC"))
        .limit(settings.POSTS_LIMIT)
    )


def wishes(service: Service):
    ev = Events if service == "rpp" else FarmaEvent
    name = ev.event_name

    prefixes = [p.strip() for p in settings.WISH_PREFIXES.split(",") if p.strip()]
    if not prefixes:
        prefixes = ["user_wish:"]

    cond = None
    for p in prefixes:
        c = name.like(f"{p}%")
        cond = c if cond is None else (cond | c)

    wish_text = case(
        (
            name.like("user_wish:%"),
            func.btrim(func.substring(name, len("user_wish:") + 1)),
        ),
        else_=name,
    ).label("wish_text")

    return (
        select(ev.timestamp.label("timestamp"), wish_text)
        .where(cond)
        .order_by(ev.timestamp.desc())
        .limit(settings.WISHES_LIMIT)
    )


def file_clicks(service: Service):
    ev = Events if service == "rpp" else FarmaEvent
    target = settings.RPP_FILE_EVENT if service == "rpp" else settings.FARMA_FILE_EVENT

    return (
        select(func.count().label("clicks"))
        .select_from(ev)
        .where(ev.event_name == target)
    )


def file_clicks_timeseries(service: Service, period: Period):
    ev = Events if service == "rpp" else FarmaEvent
    target = settings.RPP_FILE_EVENT if service == "rpp" else settings.FARMA_FILE_EVENT

    period_col = func.date_trunc(period, ev.timestamp).label("period")

    return (
        select(period_col, func.count().label("clicks"))
        .select_from(ev)
        .where(ev.event_name == target)
        .group_by(text("period"))
        .order_by(text("period"))
    )
