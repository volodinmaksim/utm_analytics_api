from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.models import CbtbaseUser, FarmaUser, ServiceType, SfbtUser, User
from analytics_app.app.payments.normalization import PaymentEventPayload


SERVICE_MATCHING_CONFIG = {
    ServiceType.RPP: (User, "user_id"),
    ServiceType.FARMA: (FarmaUser, "farma_user_id"),
    ServiceType.SFBT: (SfbtUser, "sfbt_user_id"),
    ServiceType.CBTBASE: (CbtbaseUser, "cbtbase_user_id"),
}


async def match_payment_event(
    session: AsyncSession,
    payload: PaymentEventPayload,
) -> PaymentEventPayload:
    if payload.platform_id is None:
        return payload

    user_model, payload_field = SERVICE_MATCHING_CONFIG[payload.service]
    stmt = (
        select(user_model.id, user_model.tg_id)
        .where(user_model.tg_id == payload.platform_id)
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    if row is None:
        return payload

    setattr(payload, payload_field, int(row.id))
    payload.matched_user_tg_id = int(row.tg_id)
    return payload
