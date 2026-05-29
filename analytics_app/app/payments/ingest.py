from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from analytics_app.app.models import PaymentEvent, SyncStatus, TrackedSheet
from analytics_app.app.payments.normalization import PaymentEventPayload


@dataclass(slots=True, frozen=True)
class PaymentIngestResult:
    rows_read: int
    rows_received: int
    rows_inserted: int
    last_seen_row_num: int | None
    last_seen_source_fingerprint: str | None


async def ingest_payment_events(
    session: AsyncSession,
    tracked_sheet: TrackedSheet,
    payloads: list[PaymentEventPayload],
    *,
    rows_read: int,
    processed_row_num: int | None,
    processed_fingerprint: str | None,
) -> PaymentIngestResult:
    rows_inserted = await _insert_payloads(session, payloads)

    tracked_sheet.last_seen_row_num = _max_checkpoint(
        tracked_sheet.last_seen_row_num,
        processed_row_num,
    )
    tracked_sheet.last_seen_source_fingerprint = (
        processed_fingerprint or tracked_sheet.last_seen_source_fingerprint
    )
    tracked_sheet.last_sync_finished_at = datetime.now(timezone.utc)
    tracked_sheet.last_sync_status = SyncStatus.OK
    tracked_sheet.last_sync_error = None
    tracked_sheet.last_sync_rows_read = rows_read
    tracked_sheet.last_sync_rows_inserted = rows_inserted

    await session.commit()

    return PaymentIngestResult(
        rows_read=rows_read,
        rows_received=len(payloads),
        rows_inserted=rows_inserted,
        last_seen_row_num=tracked_sheet.last_seen_row_num,
        last_seen_source_fingerprint=tracked_sheet.last_seen_source_fingerprint,
    )


async def mark_tracked_sheet_sync_error(
    session: AsyncSession,
    tracked_sheet: TrackedSheet,
    *,
    error_message: str,
) -> None:
    tracked_sheet.last_sync_finished_at = datetime.now(timezone.utc)
    tracked_sheet.last_sync_status = SyncStatus.ERROR
    tracked_sheet.last_sync_error = error_message
    await session.commit()


async def _insert_payloads(
    session: AsyncSession,
    payloads: list[PaymentEventPayload],
) -> int:
    if not payloads:
        return 0

    stmt = insert(PaymentEvent).values([_payload_to_record(payload) for payload in payloads])
    stmt = stmt.on_conflict_do_nothing()
    result = await session.execute(stmt)
    return int(result.rowcount or 0)


def _payload_to_record(payload: PaymentEventPayload) -> dict[str, object]:
    return {
        'service': payload.service,
        'tracked_sheet_id': payload.tracked_sheet_id,
        'source_sheet_name': payload.source_sheet_name,
        'source_row_num': payload.source_row_num,
        'source_fingerprint': payload.source_fingerprint,
        'platform_id': payload.platform_id,
        'email': payload.email,
        'full_name': payload.full_name,
        'nickname': payload.nickname,
        'event_date': payload.event_date,
        'event_type': payload.event_type,
        'amount': payload.amount,
        'raw_payment_value': payload.raw_payment_value,
        'user_id': payload.user_id,
        'farma_user_id': payload.farma_user_id,
        'sfbt_user_id': payload.sfbt_user_id,
        'matched_user_tg_id': payload.matched_user_tg_id,
    }


def _max_checkpoint(current_value: int | None, new_value: int | None) -> int | None:
    if current_value is None:
        return new_value
    if new_value is None:
        return current_value
    return max(current_value, new_value)
