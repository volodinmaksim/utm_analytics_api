from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.broadcasts.repository import (
    get_template_with_items,
)
from analytics_app.app.db import settings
from analytics_app.app.schemas import Service, TelegramTemplateKind
import httpx

from analytics_app.app.schemas.broadcasts import TelegramTemplateStatus


def get_bot_token_by_service(service: Service) -> str | None:
    if service == Service.RPP:
        return settings.RPP_BOT_TOKEN.get_secret_value()
    if service == Service.FARMA:
        return settings.FARMA_BOT_TOKEN.get_secret_value()
    if service == Service.SFBT:
        return settings.SFBT_BOT_TOKEN.get_secret_value()
    return None


def check_telegram_response(response: httpx.Response) -> None:
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise ValueError(data)


async def send_telegram_template_to_chat(
    session: AsyncSession,
    *,
    template_id: int,
    service: Service,
    chat_id: int,
) -> int:
    template = await get_template_with_items(
        session,
        template_id=template_id,
    )
    if template is None:
        raise ValueError("Template not found")

    token = get_bot_token_by_service(service)
    if token is None:
        raise ValueError("Service|Token not found")

    if template.status != TelegramTemplateStatus.READY:
        raise ValueError("Template is not ready")

    async with httpx.AsyncClient(timeout=10) as client:
        if template.kind == TelegramTemplateKind.SINGLE:
            if not template.items:
                raise ValueError("Item not found")
            item = template.items[0]
            response = await client.post(
                f"https://api.telegram.org/bot{token}/copyMessage",
                json={
                    "chat_id": chat_id,
                    "from_chat_id": template.source_chat_id,
                    "message_id": item.source_message_id,
                },
            )
            check_telegram_response(response)
            return 1
        else:
            items = sorted(template.items, key=lambda item: item.source_message_id)
            if not items:
                raise ValueError("Items not found")
            message_ids = [item.source_message_id for item in items]
            response = await client.post(
                f"https://api.telegram.org/bot{token}/copyMessages",
                json={
                    "chat_id": chat_id,
                    "from_chat_id": template.source_chat_id,
                    "message_ids": message_ids,
                },
            )
            check_telegram_response(response)
            return len(items)
