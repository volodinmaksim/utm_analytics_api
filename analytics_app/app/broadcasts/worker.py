from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.broadcasts.exceptions import (
    TelegramRecipientSkipped,
    TelegramTemporaryError,
    TemplateSendError,
)
from analytics_app.app.broadcasts.repository import (
    try_mark_broadcast_sending,
    claim_pending_recipients,
    finish_broadcast_if_done,
    mark_recipient_failed_or_retry,
    mark_recipient_sent,
    mark_recipient_skipped,
    mark_broadcast_failed,
    release_processing_recipients_for_broadcast,
    get_processable_broadcasts,
)
from analytics_app.app.broadcasts.sender import send_telegram_template_to_chat
from analytics_app.app.schemas import Service
from analytics_app.app.models import BroadcastStatus

RECIPIENT_BATCH_LIMIT = 50
MAX_ATTEMPTS = 5
RETRY_DELAY_SECONDS = 30


async def process_broadcasts(
    session: AsyncSession,
    *,
    limit: int,
    worker_id: str,
) -> None:
    broadcasts = await get_processable_broadcasts(session, limit=limit)
    for broadcast in broadcasts:
        if broadcast.status == BroadcastStatus.SCHEDULED:
            broadcast = await try_mark_broadcast_sending(
                session,
                broadcast_id=broadcast.id,
            )
            if broadcast is None:
                await session.rollback()
                continue
            await session.commit()
        else:
            await session.commit()

        recipients = await claim_pending_recipients(
            session,
            broadcast_id=broadcast.id,
            limit=RECIPIENT_BATCH_LIMIT,
            worker_id=worker_id,
        )
        await session.commit()
        if not recipients:
            await finish_broadcast_if_done(session, broadcast_id=broadcast.id)
            await session.commit()
        else:
            broadcast_failed = False
            for recipient in recipients:
                try:
                    send_result = await send_telegram_template_to_chat(
                        session,
                        template_id=broadcast.template_id,
                        service=Service(broadcast.service.value),
                        chat_id=recipient.tg_id,
                    )
                    await mark_recipient_sent(
                        session,
                        recipient_id=recipient.id,
                        sent_message_ids=send_result.sent_message_ids,
                    )
                    await session.commit()
                except TelegramRecipientSkipped as exc:
                    await mark_recipient_skipped(
                        session,
                        recipient_id=recipient.id,
                        error=str(exc),
                    )
                    await session.commit()
                except TelegramTemporaryError as exc:
                    await mark_recipient_failed_or_retry(
                        session,
                        recipient_id=recipient.id,
                        error=str(exc),
                        max_attempts=MAX_ATTEMPTS,
                        retry_delay_seconds=RETRY_DELAY_SECONDS,
                    )
                    await session.commit()
                except TemplateSendError as exc:
                    broadcast_failed = True
                    await mark_broadcast_failed(
                        session,
                        broadcast_id=broadcast.id,
                        error=str(exc),
                    )
                    await release_processing_recipients_for_broadcast(
                        session,
                        broadcast_id=broadcast.id,
                        worker_id=worker_id,
                    )
                    await session.commit()
                    break
            if not broadcast_failed:
                await finish_broadcast_if_done(session, broadcast_id=broadcast.id)
                await session.commit()
