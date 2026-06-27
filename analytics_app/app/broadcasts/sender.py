from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.broadcasts.exceptions import (
    TemplateSendError,
    TelegramRecipientSkipped,
    TelegramTemporaryError,
)
from analytics_app.app.broadcasts.repository import (
    get_template_with_items,
)
from analytics_app.app.db import settings
from analytics_app.app.schemas import Service, TelegramTemplateKind
import httpx

from analytics_app.app.schemas.broadcasts import TelegramTemplateStatus


@dataclass(frozen=True)
class TelegramSendResult:
    sent_messages_count: int
    sent_message_ids: list[int]


def get_bot_token_by_service(service: Service) -> str | None:
    if service == Service.RPP:
        return settings.RPP_BOT_TOKEN.get_secret_value()
    if service == Service.FARMA:
        return settings.FARMA_BOT_TOKEN.get_secret_value()
    if service == Service.SFBT:
        return settings.SFBT_BOT_TOKEN.get_secret_value()
    if service == Service.CBTBASE and settings.CBTBASE_BOT_TOKEN is not None:
        return settings.CBTBASE_BOT_TOKEN.get_secret_value()
    return None


def check_telegram_response(response: httpx.Response) -> dict:
    try:
        data = response.json()
    except ValueError as exc:
        raise TelegramTemporaryError("Invalid Telegram response") from exc

    if data.get("ok"):
        return data

    error_code = data.get("error_code", response.status_code)
    description = str(data.get("description", "") or "")
    description_lower = description.lower()

    if (
        error_code == 403
        or "bot was blocked" in description_lower
        or "chat not found" in description_lower
    ):
        raise TelegramRecipientSkipped(
            description or f"Telegram returned {error_code} for recipient"
        )

    if error_code == 429 or error_code >= 500:
        raise TelegramTemporaryError(
            description or f"Telegram temporary error {error_code}"
        )

    raise TelegramTemporaryError(description or f"Telegram error {error_code}")


def describe_network_error(action: str, exc: Exception) -> str:
    message = str(exc).strip()
    if message:
        return f"{action}: {exc.__class__.__name__}: {message}"
    return f"{action}: {exc.__class__.__name__}"


async def send_telegram_template_to_chat(
    session: AsyncSession,
    *,
    template_id: int,
    service: Service,
    chat_id: int,
) -> TelegramSendResult:
    template = await get_template_with_items(
        session,
        template_id=template_id,
    )
    if template is None:
        raise TemplateSendError("Template not found")

    token = get_bot_token_by_service(service)
    if token is None:
        raise TemplateSendError("Service|Token not found")

    if template.status != TelegramTemplateStatus.READY:
        raise TemplateSendError("Template is not ready")

    async with httpx.AsyncClient(timeout=10) as client:
        if template.kind == TelegramTemplateKind.SINGLE:
            if not template.items:
                raise TemplateSendError("Item not found")
            item = template.items[0]
            try:
                response = await client.post(
                    f"https://api.telegram.org/bot{token}/copyMessage",
                    json={
                        "chat_id": chat_id,
                        "from_chat_id": template.source_chat_id,
                        "message_id": item.source_message_id,
                    },
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                raise TelegramTemporaryError(
                    describe_network_error("copyMessage request failed", exc)
                ) from exc

            data = check_telegram_response(response)
            sent_message_id = data["result"]["message_id"]
            return TelegramSendResult(
                sent_messages_count=1,
                sent_message_ids=[sent_message_id],
            )
        else:
            items = sorted(template.items, key=lambda item: item.source_message_id)
            if not items:
                raise TemplateSendError("Items not found")
            message_ids = [item.source_message_id for item in items]
            try:
                response = await client.post(
                    f"https://api.telegram.org/bot{token}/copyMessages",
                    json={
                        "chat_id": chat_id,
                        "from_chat_id": template.source_chat_id,
                        "message_ids": message_ids,
                    },
                )
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                raise TelegramTemporaryError(
                    describe_network_error("copyMessages request failed", exc)
                ) from exc

            data = check_telegram_response(response)
            sent_message_ids = [item["message_id"] for item in data["result"]]

            return TelegramSendResult(
                sent_messages_count=len(sent_message_ids),
                sent_message_ids=sent_message_ids,
            )
