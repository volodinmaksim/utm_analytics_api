from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.broadcasts.audiences import resolve_broadcast_audience
from analytics_app.app.broadcasts.repository import (
    create_broadcast,
    create_broadcast_recipients,
    get_template_with_items,
    list_broadcasts_with_counts,
    get_broadcast_by_id,
    get_broadcast_status_summary,
    get_broadcast_error_summary,
    get_broadcast_with_counts_by_id,
    list_event_audience_options,
    list_utm_audience_options,
)
from analytics_app.app.models import TelegramTemplateStatus, BroadcastStatus
from analytics_app.app.schemas import (
    Service,
    AudienceType,
    AdminBroadcastResponse,
    AdminBroadcastListResponse,
    AdminBroadcastListRow,
    AdminBroadcastCancelResponse,
    BroadcastStatus as BroadcastSchemaStatus,
    BroadcastAudienceOptionsResponse,
    BroadcastAudienceOption,
)
from analytics_app.app.schemas.broadcasts import (
    AdminBroadcastDetailResponse,
    BroadcastTemplateSummary,
    BroadcastAudienceSummary,
    BroadcastRecipientStatusSummary,
    BroadcastRecipientErrorSummary,
)
from analytics_app.app.services.analytics import (
    FUNNEL_LABELS,
    SERVICE_CONTENT_EVENT_LABELS,
    SERVICE_FUNNEL_EVENTS,
)

FILE_EVENT_PREFIX = "Получить файл:"
TECHNICAL_EVENT_MARKERS = ("_scheduled:",)


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
    if not target_tg_ids:
        raise ValueError("Audience is empty")

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


async def get_admin_broadcasts_list(
    session: AsyncSession,
    *,
    limit: int,
) -> AdminBroadcastListResponse:
    safe_limit = max(1, min(limit, 100))
    rows = await list_broadcasts_with_counts(session, limit=safe_limit + 1)
    has_more = len(rows) > safe_limit
    visible_rows = rows[:safe_limit]

    items: list[AdminBroadcastListRow] = []
    for row in visible_rows:
        broadcast = row[0]
        recipients_total = row.recipients_total or 0
        sent_count = row.sent_count or 0
        pending_count = row.pending_count or 0
        processing_count = row.processing_count or 0
        failed_count = row.failed_count or 0
        skipped_count = row.skipped_count or 0
        item = AdminBroadcastListRow(
            id=broadcast.id,
            template_id=broadcast.template_id,
            service=broadcast.service,
            audience_type=broadcast.audience_type,
            status=broadcast.status,
            scheduled_at=broadcast.scheduled_at,
            created_at=broadcast.created_at,
            recipients_total=recipients_total,
            processing_count=processing_count,
            sent_count=sent_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            pending_count=pending_count,
        )
        items.append(item)
    return AdminBroadcastListResponse(
        items=items,
        has_more=has_more,
    )


async def cancel_admin_broadcast(
    session: AsyncSession,
    *,
    broadcast_id: int,
) -> AdminBroadcastCancelResponse:
    broadcast = await get_broadcast_by_id(session, broadcast_id=broadcast_id)
    if broadcast is None:
        raise ValueError("Broadcast not found")
    if broadcast.status != BroadcastStatus.SCHEDULED:
        raise ValueError("Broadcast already started sending")

    broadcast.status = BroadcastStatus.CANCELLED
    await session.commit()
    return AdminBroadcastCancelResponse(
        id=broadcast.id,
        status=BroadcastSchemaStatus(broadcast.status),
    )


def get_event_label_map(service: Service) -> dict[str, str]:
    labels: dict[str, str] = {}
    for key, event_name in SERVICE_FUNNEL_EVENTS.get(service, ()):
        labels[event_name] = FUNNEL_LABELS.get(key, event_name)
    labels.update(SERVICE_CONTENT_EVENT_LABELS.get(service, {}))
    return labels


def is_file_received_event(event_name: str) -> bool:
    return event_name.strip().startswith(FILE_EVENT_PREFIX)


def format_file_received_event_label(event_name: str) -> str:
    file_name = event_name.strip()[len(FILE_EVENT_PREFIX) :].strip()
    return f"Получили файл: {file_name}" if file_name else "Получили файл"


def is_technical_event(event_name: str) -> bool:
    return any(marker in event_name for marker in TECHNICAL_EVENT_MARKERS)


async def get_admin_broadcast_audience_options(
    session: AsyncSession,
    *,
    service: Service,
) -> BroadcastAudienceOptionsResponse:
    utm_rows = await list_utm_audience_options(session, service=service)
    event_rows = await list_event_audience_options(session, service=service)
    event_labels = get_event_label_map(service)

    utm_marks = [
        BroadcastAudienceOption(
            value=utm_mark,
            label=utm_mark,
            count=count,
        )
        for utm_mark, count in utm_rows
    ]
    events: list[BroadcastAudienceOption] = []
    for event_name, count in event_rows:
        if is_technical_event(event_name):
            continue
        if is_file_received_event(event_name):
            label = format_file_received_event_label(event_name)
        elif event_name in event_labels:
            label = event_labels[event_name]
        else:
            continue

        events.append(
            BroadcastAudienceOption(
                value=event_name,
                label=label,
                count=count,
            )
        )
    events.sort(key=lambda item: item.label.lower())

    return BroadcastAudienceOptionsResponse(
        utm_marks=utm_marks,
        events=events,
    )


def format_audience_label(
    audience_type: AudienceType,
    audience_filter: dict,
) -> str:
    if audience_type == AudienceType.ALL:
        return "Все пользователи"
    if audience_type == AudienceType.UTM:
        value = audience_filter.get("utm_mark") or audience_filter.get("utm")
        return f"UTM: {value}" if value else "UTM"
    if audience_type == AudienceType.EVENT:
        value = audience_filter.get("event_name")
        if not value:
            return "Событие"
        if is_file_received_event(str(value)):
            return format_file_received_event_label(str(value))
        return f"Событие: {value}"
    return audience_type.value


async def get_admin_broadcast_detail(
    session: AsyncSession,
    *,
    broadcast_id: int,
) -> AdminBroadcastDetailResponse:
    row = await get_broadcast_with_counts_by_id(session, broadcast_id=broadcast_id)
    if row is None:
        raise ValueError("Broadcast not found")

    broadcast = row.Broadcast

    status_rows = await get_broadcast_status_summary(
        session,
        broadcast_id=broadcast_id,
    )
    error_rows = await get_broadcast_error_summary(
        session,
        broadcast_id=broadcast_id,
    )

    return AdminBroadcastDetailResponse(
        id=broadcast.id,
        template_id=broadcast.template_id,
        service=broadcast.service,
        audience_type=broadcast.audience_type,
        status=broadcast.status,
        scheduled_at=broadcast.scheduled_at,
        created_at=broadcast.created_at,
        recipients_total=row.recipients_total or 0,
        processing_count=row.processing_count or 0,
        sent_count=row.sent_count or 0,
        failed_count=row.failed_count or 0,
        skipped_count=row.skipped_count or 0,
        pending_count=row.pending_count or 0,
        last_error=broadcast.last_error or None,
        started_at=broadcast.started_at,
        finished_at=broadcast.finished_at,
        template=BroadcastTemplateSummary(
            id=broadcast.template.id,
            kind=broadcast.template.kind,
            preview_text=broadcast.template.preview_text,
            items_count=broadcast.template.items_count,
        ),
        audience=BroadcastAudienceSummary(
            audience_type=broadcast.audience_type,
            audience_filter=broadcast.audience_filter or {},
            label=format_audience_label(
                broadcast.audience_type,
                broadcast.audience_filter or {},
            ),
        ),
        status_summary=[
            BroadcastRecipientStatusSummary(status=status, count=count)
            for status, count in status_rows
        ],
        error_summary=[
            BroadcastRecipientErrorSummary(status=status, reason=reason, count=count)
            for status, reason, count in error_rows
        ],
    )
