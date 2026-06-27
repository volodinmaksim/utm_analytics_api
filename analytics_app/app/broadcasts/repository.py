from collections.abc import Sequence
from datetime import datetime, timezone, timedelta
from typing import Any

from sqlalchemy import select, case, func, Row, or_, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from analytics_app.app.models import (
    TelegramTemplate,
    TelegramTemplateStatus,
    TelegramTemplateItem,
    Broadcast,
    BroadcastRecipient,
    User,
    FarmaUser,
    CbtbaseUser,
    SfbtUser,
)
from analytics_app.app.schemas import (
    TelegramTemplateKind,
    Service,
    AudienceType,
    BroadcastStatus,
)
from analytics_app.app.schemas.broadcasts import BroadcastRecipientStatus


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
        .order_by(TelegramTemplate.id)
        .limit(1)
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

    count_result = await session.execute(
        select(func.count(TelegramTemplateItem.id)).where(
            TelegramTemplateItem.template_id == template_id
        )
    )
    template.items_count = count_result.scalar_one()

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


async def get_template_with_items(
    session: AsyncSession, *, template_id: int
) -> TelegramTemplate | None:
    stmt = (
        select(TelegramTemplate)
        .where(TelegramTemplate.id == template_id)
        .options(selectinload(TelegramTemplate.items))
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def create_broadcast(
    session: AsyncSession,
    *,
    template_id: int,
    service: Service,
    audience_type: AudienceType,
    audience_filter: dict[str, Any],
    scheduled_at: datetime,
) -> Broadcast:
    broadcast = Broadcast(
        template_id=template_id,
        service=service,
        audience_type=audience_type,
        audience_filter=audience_filter,
        status=BroadcastStatus.SCHEDULED,
        scheduled_at=scheduled_at,
    )

    session.add(broadcast)
    await session.flush()
    return broadcast


async def create_broadcast_recipients(
    session: AsyncSession,
    *,
    broadcast_id: int,
    tg_ids: list[int],
) -> list[BroadcastRecipient]:
    recipients = []

    for tg_id in tg_ids:
        recipient = BroadcastRecipient(
            broadcast_id=broadcast_id,
            tg_id=tg_id,
            status=BroadcastRecipientStatus.PENDING,
        )
        recipients.append(recipient)

    session.add_all(recipients)
    await session.flush()
    return recipients


async def get_all_user_tg_ids_by_service(
    session: AsyncSession,
    *,
    service: Service,
) -> list[int]:
    if service == Service.RPP:
        user_model = User
    elif service == Service.FARMA:
        user_model = FarmaUser
    elif service == Service.SFBT:
        user_model = SfbtUser
    elif service == Service.CBTBASE:
        user_model = CbtbaseUser
    else:
        raise ValueError("Unknown service")

    stmt = select(user_model.tg_id).order_by(user_model.tg_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def list_broadcasts_with_counts(
    session: AsyncSession,
    *,
    limit: int,
) -> Sequence[Row]:
    stmt = (
        select(
            Broadcast,
            func.count(BroadcastRecipient.id).label("recipients_total"),
            func.sum(
                case(
                    (BroadcastRecipient.status == BroadcastRecipientStatus.SENT, 1),
                    else_=0,
                )
            ).label("sent_count"),
            func.sum(
                case(
                    (BroadcastRecipient.status == BroadcastRecipientStatus.PENDING, 1),
                    else_=0,
                )
            ).label("pending_count"),
            func.sum(
                case(
                    (
                        BroadcastRecipient.status
                        == BroadcastRecipientStatus.PROCESSING,
                        1,
                    ),
                    else_=0,
                )
            ).label("processing_count"),
            func.sum(
                case(
                    (BroadcastRecipient.status == BroadcastRecipientStatus.FAILED, 1),
                    else_=0,
                )
            ).label("failed_count"),
            func.sum(
                case(
                    (BroadcastRecipient.status == BroadcastRecipientStatus.SKIPPED, 1),
                    else_=0,
                )
            ).label("skipped_count"),
        )
        .outerjoin(BroadcastRecipient)
        .group_by(Broadcast.id)
        .order_by(Broadcast.created_at.desc())
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.all()


async def get_broadcast_by_id(
    session: AsyncSession,
    *,
    broadcast_id: int,
) -> Broadcast | None:
    stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_due_scheduled_broadcasts(
    session: AsyncSession,
    *,
    limit: int,
) -> list[Broadcast]:
    stmt = (
        select(Broadcast)
        .where(Broadcast.status == BroadcastStatus.SCHEDULED)
        .where(Broadcast.scheduled_at <= func.now())
        .order_by(Broadcast.scheduled_at)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def try_mark_broadcast_sending(
    session: AsyncSession,
    *,
    broadcast_id: int,
) -> Broadcast | None:
    stmt = (
        select(Broadcast)
        .where(Broadcast.id == broadcast_id)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    broadcast = result.scalar_one_or_none()

    if broadcast is None:
        return None

    if broadcast.status == BroadcastStatus.SENDING:
        return broadcast

    if broadcast.status != BroadcastStatus.SCHEDULED:
        return None

    broadcast.status = BroadcastStatus.SENDING
    broadcast.started_at = datetime.now(timezone.utc)

    await session.flush()
    return broadcast


async def claim_pending_recipients(
    session: AsyncSession,
    *,
    broadcast_id: int,
    limit: int,
    worker_id: str,
) -> list[BroadcastRecipient]:
    stmt = (
        select(BroadcastRecipient)
        .where(BroadcastRecipient.broadcast_id == broadcast_id)
        .where(BroadcastRecipient.status == BroadcastRecipientStatus.PENDING)
        .where(
            or_(
                BroadcastRecipient.next_attempt_at.is_(None),
                BroadcastRecipient.next_attempt_at <= func.now(),
            )
        )
        .order_by(BroadcastRecipient.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    recipients = list(result.scalars().all())

    for recipient in recipients:
        recipient.status = BroadcastRecipientStatus.PROCESSING
        recipient.locked_at = datetime.now(timezone.utc)
        recipient.locked_by = worker_id
        recipient.attempts += 1

    await session.flush()
    return recipients


async def mark_recipient_sent(
    session: AsyncSession,
    *,
    recipient_id: int,
    sent_message_ids: list[int],
) -> BroadcastRecipient:
    stmt = select(BroadcastRecipient).where(BroadcastRecipient.id == recipient_id)
    result = await session.execute(stmt)
    recipient = result.scalar_one_or_none()
    if recipient is None:
        raise ValueError("Recipient not found or locked")

    if recipient.status != BroadcastRecipientStatus.PROCESSING:
        raise ValueError("Recipient status is not processing")

    recipient.status = BroadcastRecipientStatus.SENT
    recipient.sent_at = datetime.now(timezone.utc)
    recipient.last_error = None
    recipient.locked_at = None
    recipient.locked_by = None
    recipient.sent_message_ids = sent_message_ids

    await session.flush()
    return recipient


async def mark_recipient_failed_or_retry(
    session: AsyncSession,
    *,
    recipient_id: int,
    error: str,
    max_attempts: int,
    retry_delay_seconds: int,
) -> BroadcastRecipient:
    stmt = select(BroadcastRecipient).where(BroadcastRecipient.id == recipient_id)
    result = await session.execute(stmt)
    recipient = result.scalar_one_or_none()

    if recipient is None:
        raise ValueError("Recipient not found")

    if recipient.status != BroadcastRecipientStatus.PROCESSING:
        raise ValueError("Recipient status is not processing")

    recipient.last_error = error
    recipient.locked_at = None
    recipient.locked_by = None

    if recipient.attempts >= max_attempts:
        recipient.status = BroadcastRecipientStatus.FAILED
        recipient.next_attempt_at = None
    else:
        recipient.status = BroadcastRecipientStatus.PENDING
        recipient.next_attempt_at = datetime.now(timezone.utc) + timedelta(
            seconds=retry_delay_seconds
        )

    await session.flush()
    return recipient


async def finish_broadcast_if_done(
    session: AsyncSession,
    *,
    broadcast_id: int,
) -> Broadcast | None:
    active_stmt = (
        select(func.count(BroadcastRecipient.id))
        .where(BroadcastRecipient.broadcast_id == broadcast_id)
        .where(
            BroadcastRecipient.status.in_(
                [
                    BroadcastRecipientStatus.PENDING,
                    BroadcastRecipientStatus.PROCESSING,
                ]
            )
        )
    )
    active_result = await session.execute(active_stmt)
    active_count = active_result.scalar_one()

    if active_count > 0:
        return None

    failed_stmt = (
        select(func.count(BroadcastRecipient.id))
        .where(BroadcastRecipient.broadcast_id == broadcast_id)
        .where(BroadcastRecipient.status == BroadcastRecipientStatus.FAILED)
    )
    failed_result = await session.execute(failed_stmt)
    failed_count = failed_result.scalar_one()

    broadcast_stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
    broadcast_result = await session.execute(broadcast_stmt)
    broadcast = broadcast_result.scalar_one_or_none()

    if broadcast is None:
        raise ValueError("Broadcast not found")

    if failed_count > 0:
        broadcast.status = BroadcastStatus.FAILED
    else:
        broadcast.status = BroadcastStatus.SENT

    broadcast.finished_at = datetime.now(timezone.utc)

    await session.flush()
    return broadcast


async def mark_recipient_skipped(
    session: AsyncSession,
    *,
    recipient_id: int,
    error: str | None = None,
) -> BroadcastRecipient:
    stmt = select(BroadcastRecipient).where(BroadcastRecipient.id == recipient_id)
    result = await session.execute(stmt)
    recipient = result.scalar_one_or_none()

    if recipient is None:
        raise ValueError("Recipient not found")

    if recipient.status != BroadcastRecipientStatus.PROCESSING:
        raise ValueError("Recipient status is not processing")

    recipient.status = BroadcastRecipientStatus.SKIPPED
    recipient.last_error = error
    recipient.locked_at = None
    recipient.locked_by = None
    recipient.next_attempt_at = None

    await session.flush()
    return recipient


async def mark_broadcast_failed(
    session: AsyncSession,
    *,
    broadcast_id: int,
    error: str | None = None,
) -> Broadcast:
    stmt = select(Broadcast).where(Broadcast.id == broadcast_id)
    result = await session.execute(stmt)
    broadcast = result.scalar_one_or_none()

    if broadcast is None:
        raise ValueError("Broadcast not found")

    broadcast.status = BroadcastStatus.FAILED
    broadcast.last_error = error
    broadcast.finished_at = datetime.now(timezone.utc)

    await session.flush()
    return broadcast


async def release_processing_recipients_for_broadcast(
    session: AsyncSession,
    *,
    broadcast_id: int,
    worker_id: str,
) -> None:
    stmt = (
        update(BroadcastRecipient)
        .where(BroadcastRecipient.broadcast_id == broadcast_id)
        .where(BroadcastRecipient.status == BroadcastRecipientStatus.PROCESSING)
        .where(BroadcastRecipient.locked_by == worker_id)
        .values(
            status=BroadcastRecipientStatus.PENDING,
            locked_at=None,
            locked_by=None,
            next_attempt_at=None,
        )
    )
    await session.execute(stmt)
    await session.flush()


async def release_stale_processing_recipients(
    session: AsyncSession,
    *,
    stale_after_seconds: int,
) -> int:
    stale_before = datetime.now(timezone.utc) - timedelta(seconds=stale_after_seconds)
    stmt = (
        update(BroadcastRecipient)
        .where(BroadcastRecipient.status == BroadcastRecipientStatus.PROCESSING)
        .where(BroadcastRecipient.locked_at.is_not(None))
        .where(BroadcastRecipient.locked_at < stale_before)
        .values(
            status=BroadcastRecipientStatus.PENDING,
            locked_at=None,
            locked_by=None,
            next_attempt_at=None,
        )
    )
    result = await session.execute(stmt)
    await session.flush()
    return int(result.rowcount or 0)


async def get_processable_broadcasts(
    session: AsyncSession,
    *,
    limit: int,
) -> list[Broadcast]:
    stmt = (
        select(Broadcast)
        .where(
            or_(
                and_(
                    Broadcast.status == BroadcastStatus.SCHEDULED,
                    Broadcast.scheduled_at <= func.now(),
                ),
                Broadcast.status == BroadcastStatus.SENDING,
            )
        )
        .order_by(Broadcast.scheduled_at, Broadcast.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def mark_expired_collecting_templates_ready(
    session: AsyncSession,
    *,
    limit: int,
) -> list[TelegramTemplate]:
    stmt = (
        select(TelegramTemplate)
        .where(
            and_(
                TelegramTemplate.status == TelegramTemplateStatus.COLLECTING,
                TelegramTemplate.ready_after <= func.now(),
            )
        )
        .order_by(TelegramTemplate.ready_after, TelegramTemplate.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    templates = list(result.scalars().all())

    for template in templates:
        count_result = await session.execute(
            select(func.count(TelegramTemplateItem.id)).where(
                TelegramTemplateItem.template_id == template.id
            )
        )
        template.items_count = count_result.scalar_one()
        template.status = TelegramTemplateStatus.READY

    await session.flush()
    return templates
