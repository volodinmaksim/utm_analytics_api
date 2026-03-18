from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from analytics_app.app.db import get_session_factory, settings
from analytics_app.app.clients.google_sheets import (
    GoogleSheetsClient,
    get_google_sheets_client,
)
from analytics_app.app.models.orm import SyncStatus, TrackedSheet
from analytics_app.app.payments.ingest import (
    PaymentIngestResult,
    ingest_payment_events,
    mark_tracked_sheet_sync_error,
)
from analytics_app.app.payments.matching import match_payment_event
from analytics_app.app.payments.normalization import (
    PaymentRowStatus,
    SheetSourceContext,
    normalize_payment_row,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class SheetSyncResult:
    tracked_sheet_id: int
    status: str
    rows_read: int = 0
    rows_inserted: int = 0
    invalid_rows: int = 0
    empty_rows: int = 0
    error: str | None = None


async def sync_payments_once(
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    client: GoogleSheetsClient | None = None,
) -> list[SheetSyncResult]:
    session_factory = session_factory or get_session_factory()
    client = client or get_google_sheets_client()

    tracked_sheet_ids = await _get_due_tracked_sheet_ids(session_factory)
    if not tracked_sheet_ids:
        logger.info("No tracked sheets are due for sync")
        return []

    results: list[SheetSyncResult] = []
    for tracked_sheet_id in tracked_sheet_ids:
        result = await _sync_tracked_sheet(
            tracked_sheet_id=tracked_sheet_id,
            session_factory=session_factory,
            client=client,
        )
        results.append(result)

    return results


async def run_payments_worker(
    *,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    client: GoogleSheetsClient | None = None,
    sleep_seconds: int = 5,
) -> None:
    session_factory = session_factory or get_session_factory()
    client = client or get_google_sheets_client()

    while True:
        try:
            await sync_payments_once(session_factory=session_factory, client=client)
        except Exception:
            logger.exception("Payments sync loop failed")

        await asyncio.sleep(sleep_seconds)


async def _get_due_tracked_sheet_ids(
    session_factory: async_sessionmaker[AsyncSession],
) -> list[int]:
    async with session_factory() as session:
        stmt = (
            select(TrackedSheet)
            .where(TrackedSheet.is_active.is_(True))
            .order_by(TrackedSheet.id.asc())
        )
        tracked_sheets = (await session.execute(stmt)).scalars().all()

    return [sheet.id for sheet in tracked_sheets if _is_sheet_due(sheet)]


async def _sync_tracked_sheet(
    *,
    tracked_sheet_id: int,
    session_factory: async_sessionmaker[AsyncSession],
    client: GoogleSheetsClient,
) -> SheetSyncResult:
    async with session_factory() as session:
        tracked_sheet = await session.get(TrackedSheet, tracked_sheet_id)
        if tracked_sheet is None or not tracked_sheet.is_active:
            return SheetSyncResult(tracked_sheet_id=tracked_sheet_id, status="skipped")

        await _mark_sync_started(session, tracked_sheet)

    try:
        rows = await client.fetch_rows(
            spreadsheet_id=tracked_sheet.spreadsheet_id,
            sheet_name=tracked_sheet.sheet_name,
            start_row=_build_start_row(tracked_sheet),
        )
    except Exception as exc:
        return await _finish_with_error(
            tracked_sheet_id=tracked_sheet_id,
            session_factory=session_factory,
            error_message=str(exc),
        )

    async with session_factory() as session:
        tracked_sheet = await session.get(TrackedSheet, tracked_sheet_id)
        if tracked_sheet is None:
            return SheetSyncResult(tracked_sheet_id=tracked_sheet_id, status="skipped")

        context = SheetSourceContext(
            tracked_sheet_id=tracked_sheet.id,
            service=tracked_sheet.service,
            spreadsheet_id=tracked_sheet.spreadsheet_id,
            sheet_name=tracked_sheet.sheet_name,
            sheet_gid=tracked_sheet.sheet_gid,
        )

        payloads = []
        invalid_rows = 0
        empty_rows = 0

        try:
            for row in rows:
                result = normalize_payment_row(row, context)
                if result.status == PaymentRowStatus.EMPTY:
                    empty_rows += 1
                    continue
                if result.payload is None:
                    invalid_rows += 1
                    logger.warning(
                        "Skipping invalid payment row tracked_sheet_id=%s row_num=%s reason=%s",
                        tracked_sheet.id,
                        result.row_num,
                        result.reason,
                    )
                    continue

                payloads.append(await match_payment_event(session, result.payload))

            ingest_result = await ingest_payment_events(
                session,
                tracked_sheet,
                payloads,
                rows_read=len(rows),
                processed_row_num=max(
                    (row.source_row_num for row in rows), default=None
                ),
                processed_fingerprint=(
                    payloads[-1].source_fingerprint if payloads else None
                ),
            )
        except Exception as exc:
            await session.rollback()
            return await _finish_with_error(
                tracked_sheet_id=tracked_sheet_id,
                session_factory=session_factory,
                error_message=str(exc),
            )

    logger.info(
        "Tracked sheet synced tracked_sheet_id=%s rows_read=%s rows_inserted=%s invalid_rows=%s empty_rows=%s",
        tracked_sheet_id,
        ingest_result.rows_read,
        ingest_result.rows_inserted,
        invalid_rows,
        empty_rows,
    )
    return SheetSyncResult(
        tracked_sheet_id=tracked_sheet_id,
        status="ok",
        rows_read=ingest_result.rows_read,
        rows_inserted=ingest_result.rows_inserted,
        invalid_rows=invalid_rows,
        empty_rows=empty_rows,
    )


async def _mark_sync_started(
    session: AsyncSession, tracked_sheet: TrackedSheet
) -> None:
    tracked_sheet.last_sync_started_at = datetime.now(timezone.utc)
    tracked_sheet.last_sync_status = SyncStatus.RUNNING
    tracked_sheet.last_sync_error = None
    await session.commit()


async def _finish_with_error(
    *,
    tracked_sheet_id: int,
    session_factory: async_sessionmaker[AsyncSession],
    error_message: str,
) -> SheetSyncResult:
    async with session_factory() as session:
        tracked_sheet = await session.get(TrackedSheet, tracked_sheet_id)
        if tracked_sheet is not None:
            await mark_tracked_sheet_sync_error(
                session,
                tracked_sheet,
                error_message=error_message,
            )

    logger.error(
        "Tracked sheet sync failed tracked_sheet_id=%s error=%s",
        tracked_sheet_id,
        error_message,
    )
    return SheetSyncResult(
        tracked_sheet_id=tracked_sheet_id,
        status="error",
        error=error_message,
    )


def _build_start_row(tracked_sheet: TrackedSheet) -> int:
    if tracked_sheet.last_seen_row_num is None:
        return 2

    return max(2, tracked_sheet.last_seen_row_num - settings.PAYMENTS_SYNC_OVERLAP_ROWS)


def _is_sheet_due(tracked_sheet: TrackedSheet) -> bool:
    if tracked_sheet.last_sync_status == SyncStatus.RUNNING:
        return False

    if tracked_sheet.last_sync_finished_at is None:
        return True

    elapsed_seconds = (
        datetime.now(timezone.utc) - tracked_sheet.last_sync_finished_at
    ).total_seconds()
    return elapsed_seconds >= tracked_sheet.poll_interval_seconds
