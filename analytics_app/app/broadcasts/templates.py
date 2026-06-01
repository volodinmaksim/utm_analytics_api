from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.broadcasts import repository
from analytics_app.app.broadcasts.repository import (
    search_collecting_template_by_media_group,
    create_telegram_template,
    create_telegram_template_item,
    update_collecting_template_summary,
)
from analytics_app.app.schemas import (
    AdminTelegramTemplateListResponse,
    AdminTelegramTemplateListRow,
    Service,
)
from analytics_app.app.schemas.broadcasts import (
    TelegramTemplateIngestResponse,
    TelegramTemplateKind,
    TelegramTemplateStatus,
)

DEFAULT_TEMPLATES_LIMIT = 8
MAX_TEMPLATES_LIMIT = 100


async def get_list_admin_telegram_templates(
    session: AsyncSession,
    *,
    limit: int = DEFAULT_TEMPLATES_LIMIT,
) -> AdminTelegramTemplateListResponse:

    safe_limit = max(1, min(limit, MAX_TEMPLATES_LIMIT))

    templates = await repository.list_ready_telegram_templates(
        session,
        limit=safe_limit + 1,
    )

    has_more = len(templates) > safe_limit
    visible_templates = templates[:safe_limit]
    return AdminTelegramTemplateListResponse(
        items=[
            AdminTelegramTemplateListRow(
                id=template.id,
                kind=template.kind,
                preview_text=template.preview_text,
                items_count=template.items_count,
                created_at=template.created_at,
            )
            for template in visible_templates
        ],
        has_more=has_more,
    )


def extract_message_id(message: dict[str, Any]) -> int:
    return message["message_id"]


def extract_media_group_id(message: dict[str, Any]) -> str | None:
    return message.get("media_group_id")


def extract_chat_id(message: dict[str, Any]) -> int:
    return message["chat"]["id"]


def detect_content_type(message: dict[str, Any]) -> str:
    for content_type in (
        "text",
        "photo",
        "video",
        "animation",
        "document",
        "voice",
        "video_note",
        "audio",
        "sticker",
    ):
        if content_type in message:
            return content_type

    return "unknown"


def extract_preview_text(message: dict[str, Any]) -> str | None:
    text = message.get("text") or message.get("caption")
    if text is None:
        return None
    return text[:100]


async def ingest_telegram_message(
    session: AsyncSession,
    *,
    message: dict[str, Any],
) -> TelegramTemplateIngestResponse:
    message_id = extract_message_id(message)
    chat_id = extract_chat_id(message)
    media_group_id = extract_media_group_id(message)
    content_type = detect_content_type(message)
    preview_text = extract_preview_text(message)

    if media_group_id is None:
        template = await create_telegram_template(
            session,
            source_chat_id=chat_id,
            media_group_id=media_group_id,
            kind=TelegramTemplateKind.SINGLE,
            status=TelegramTemplateStatus.READY,
            preview_text=preview_text,
        )
    else:
        template = await search_collecting_template_by_media_group(
            session,
            source_chat_id=chat_id,
            media_group_id=media_group_id,
        )
        if template is None:
            template = await create_telegram_template(
                session,
                source_chat_id=chat_id,
                media_group_id=media_group_id,
                kind=TelegramTemplateKind.ALBUM,
                status=TelegramTemplateStatus.COLLECTING,
                preview_text=preview_text,
            )
    await create_telegram_template_item(
        session=session,
        template_id=template.id,
        source_message_id=message_id,
        content_type=content_type,
        raw_message_json=message,
    )
    if template.kind == TelegramTemplateKind.SINGLE:
        template.items_count = 1
    else:
        await update_collecting_template_summary(session, template_id=template.id)
    await session.commit()
    return TelegramTemplateIngestResponse(
        template_id=template.id,
        status=template.status,
        items_count=template.items_count,
    )
