from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.models.orm import FarmaUser, ServiceType, User
from analytics_app.app.payments.normalization import PaymentEventPayload


async def match_payment_event(
    session: AsyncSession,
    payload: PaymentEventPayload,
) -> PaymentEventPayload:
    if payload.platform_id is None:
        return payload

    if payload.service == ServiceType.RPP:
        stmt = select(User.id, User.tg_id).where(User.tg_id == payload.platform_id).limit(1)
        row = (await session.execute(stmt)).first()
        if row is None:
            return payload
        payload.user_id = int(row.id)
        payload.matched_user_tg_id = int(row.tg_id)
        return payload

    stmt = select(FarmaUser.id, FarmaUser.tg_id).where(FarmaUser.tg_id == payload.platform_id).limit(1)
    row = (await session.execute(stmt)).first()
    if row is None:
        return payload
    payload.farma_user_id = int(row.id)
    payload.matched_user_tg_id = int(row.tg_id)
    return payload
