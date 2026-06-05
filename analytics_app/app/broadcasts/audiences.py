from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.broadcasts.repository import get_all_user_tg_ids_by_service

from analytics_app.app.schemas import Service, AudienceType


async def resolve_broadcast_audience(
    session: AsyncSession,
    *,
    service: Service,
    audience_type: AudienceType,
    audience_filter: dict[str, Any],
) -> list[int]:
    if audience_type == AudienceType.ALL:
        selected_ids: list[int] = await get_all_user_tg_ids_by_service(
            session,
            service=service,
        )
    else:
        raise ValueError("Unsupported audience type")
    return selected_ids
