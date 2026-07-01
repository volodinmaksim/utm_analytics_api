from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.broadcasts.repository import (
    get_all_user_tg_ids_by_service,
    get_user_tg_ids_by_event,
    get_user_tg_ids_by_utm,
)

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
    elif audience_type == AudienceType.UTM:
        utm_mark = str(
            audience_filter.get("utm_mark") or audience_filter.get("utm") or ""
        ).strip()
        if not utm_mark:
            raise ValueError("UTM audience requires utm_mark")
        selected_ids = await get_user_tg_ids_by_utm(
            session,
            service=service,
            utm_mark=utm_mark,
        )
    elif audience_type == AudienceType.EVENT:
        event_name = str(audience_filter.get("event_name") or "").strip()
        if not event_name:
            raise ValueError("Event audience requires event_name")
        selected_ids = await get_user_tg_ids_by_event(
            session,
            service=service,
            event_name=event_name,
        )
    else:
        raise ValueError("Unsupported audience type")
    return selected_ids
