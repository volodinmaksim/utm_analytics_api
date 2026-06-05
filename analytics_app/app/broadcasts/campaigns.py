from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.broadcasts.audiences import resolve_broadcast_audience
from analytics_app.app.broadcasts.repository import (
    create_broadcast,
    create_broadcast_recipients,
    get_template_with_items,
)
from analytics_app.app.schemas import Service, AudienceType, AdminBroadcastResponse
from analytics_app.app.models import TelegramTemplateStatus


async def create_admin_broadcast(
    session: AsyncSession,
    *,
    service: Service,
    audience_type: AudienceType,
    audience_filter: dict[str, Any],
    template_id: int,
    scheduled_at: datetime,
) -> AdminBroadcastResponse:
    template = await get_template_with_items(
        session,
        template_id=template_id,
    )
    if template is None:
        raise ValueError("Template not found")
    if template.status != TelegramTemplateStatus.READY:
        raise ValueError("Template still collecting")

    target_tg_ids = await resolve_broadcast_audience(
        session,
        service=service,
        audience_type=audience_type,
        audience_filter=audience_filter,
    )

    broadcast = await create_broadcast(
        session,
        template_id=template_id,
        service=service,
        audience_filter=audience_filter,
        audience_type=audience_type,
        scheduled_at=scheduled_at,
    )
    await create_broadcast_recipients(
        session, broadcast_id=broadcast.id, tg_ids=target_tg_ids
    )
    await session.commit()
    await session.refresh(broadcast)
    return AdminBroadcastResponse(
        id=broadcast.id,
        template_id=template_id,
        service=service,
        audience_type=audience_type,
        audience_filter=audience_filter,
        status=broadcast.status,
        scheduled_at=broadcast.scheduled_at,
        created_at=broadcast.created_at,
        started_at=broadcast.started_at,
        finished_at=broadcast.finished_at,
    )
