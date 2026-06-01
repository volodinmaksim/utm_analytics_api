from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.models import (
    TelegramTemplate,
    TelegramTemplateStatus,
    TelegramTemplateItem,
)
from analytics_app.app.schemas import TelegramTemplateKind


async def list_ready_telegram_templates(
    session: AsyncSession,
    *,
    limit: int,
) -> list[TelegramTemplate]:
    stmt = (
        select(TelegramTemplate)
        .where(TelegramTemplate.status == TelegramTemplateStatus.READY)
        .order_by(TelegramTemplate.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_collecting_template_by_media_group(
    session: AsyncSession,
    *,
    source_chat_id: int,
    media_group_id: str,
) -> TelegramTemplate | None:
    stmt = (
        select(TelegramTemplate)
        .where(TelegramTemplate.source_chat_id == source_chat_id)
        .where(TelegramTemplate.media_group_id == media_group_id)
        .where(TelegramTemplate.status == TelegramTemplateStatus.COLLECTING)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_telegram_template(
    session: AsyncSession,
    *,
    source_chat_id: int,
    media_group_id: str | None,
    kind: TelegramTemplateKind,
    status: TelegramTemplateStatus,
    preview_text: str | None,
) -> TelegramTemplate:
    if status == TelegramTemplateStatus.COLLECTING:
        ready_after = datetime.now(timezone.utc) + timedelta(seconds=3)
    else:
        ready_after = None
    telegram_template = TelegramTemplate(
        service=None,
        source_chat_id=source_chat_id,
        media_group_id=media_group_id,
        kind=kind,
        status=status,
        preview_text=preview_text,
        ready_after=ready_after,
    )
    session.add(telegram_template)
    await session.flush()
    return telegram_template


async def create_telegram_template_item(
    session: AsyncSession,
    *,
    template_id: int,
    source_message_id: int,
    content_type: str,
    raw_message_json: dict[str, Any],
) -> TelegramTemplateItem:
    telegram_template_item = TelegramTemplateItem(
        template_id=template_id,
        source_message_id=source_message_id,
        content_type=content_type,
        raw_message_json=raw_message_json,
    )
    session.add(telegram_template_item)
    await session.flush()
    return telegram_template_item


async def update_collecting_template_summary(
    session: AsyncSession,
    *,
    template_id: int,
) -> TelegramTemplate:
    stmt = await session.execute(
        select(TelegramTemplate).where(TelegramTemplate.id == template_id)
    )
    template = stmt.scalar_one_or_none()

    if not template:
        raise ValueError("Template not found")

    if template.status != TelegramTemplateStatus.COLLECTING:
        raise ValueError("Template is not collecting")

    template.items_count += 1
    template.ready_after = datetime.now(timezone.utc) + timedelta(seconds=5)

    await session.flush()
    return template


async def mark_template_ready_if_expired(
    session: AsyncSession,
    *,
    template_id: int,
) -> TelegramTemplate:
    stmt = await session.execute(
        select(TelegramTemplate).where(TelegramTemplate.id == template_id)
    )
    template = stmt.scalar_one_or_none()

    if not template:
        raise ValueError("Template not found")

    if template.status != TelegramTemplateStatus.COLLECTING:
        raise ValueError("Template is not collecting")

    current_time = datetime.now(timezone.utc)
    if template.ready_after is not None and template.ready_after <= current_time:
        template.status = TelegramTemplateStatus.READY

    await session.flush()
    return template
