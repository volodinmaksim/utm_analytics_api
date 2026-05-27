import re
from dataclasses import dataclass

from analytics_app.app.clients.google_sheets import GoogleSheetsClient, get_google_sheets_client
from analytics_app.app.schemas.admin import TrackedSheetResponse
from analytics_app.app.schemas.analytics import Service
from analytics_app.app.models.orm import ServiceType, TrackedSheet

_SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")
_GID_RE = re.compile(r"[?#&]gid=(\d+)")


@dataclass(slots=True, frozen=True)
class SpreadsheetSource:
    spreadsheet_id: str
    spreadsheet_url: str
    sheet_gid: int | None


def normalize_spreadsheet_source(
    *,
    spreadsheet_url: str | None,
    spreadsheet_id: str | None,
) -> SpreadsheetSource:
    normalized_url = spreadsheet_url.strip() if spreadsheet_url else None
    normalized_id = spreadsheet_id.strip() if spreadsheet_id else None

    extracted_id = _extract_spreadsheet_id(normalized_url) if normalized_url else None
    extracted_gid = _extract_sheet_gid(normalized_url) if normalized_url else None

    if normalized_id and extracted_id and normalized_id != extracted_id:
        raise ValueError("spreadsheet_id does not match spreadsheet_url")

    final_id = normalized_id or extracted_id
    if not final_id:
        raise ValueError("Unable to determine spreadsheet_id")

    final_url = normalized_url or f"https://docs.google.com/spreadsheets/d/{final_id}/edit"
    return SpreadsheetSource(
        spreadsheet_id=final_id,
        spreadsheet_url=final_url,
        sheet_gid=extracted_gid,
    )


async def validate_tracked_sheet_access(
    *,
    spreadsheet_id: str,
    sheet_name: str,
    client: GoogleSheetsClient | None = None,
) -> None:
    client = client or get_google_sheets_client()
    await client.fetch_rows(
        spreadsheet_id=spreadsheet_id,
        sheet_name=sheet_name,
        start_row=2,
    )


def to_service_type(service: Service | str) -> ServiceType:
    if isinstance(service, Service):
        return ServiceType(service.value)
    return ServiceType(service)


def to_tracked_sheet_response(tracked_sheet: TrackedSheet) -> TrackedSheetResponse:
    return TrackedSheetResponse(
        id=tracked_sheet.id,
        service=Service(tracked_sheet.service.value),
        spreadsheet_id=tracked_sheet.spreadsheet_id,
        spreadsheet_url=tracked_sheet.spreadsheet_url,
        sheet_name=tracked_sheet.sheet_name,
        sheet_gid=tracked_sheet.sheet_gid,
        is_active=tracked_sheet.is_active,
        poll_interval_seconds=tracked_sheet.poll_interval_seconds,
        last_seen_row_num=tracked_sheet.last_seen_row_num,
        last_seen_source_fingerprint=tracked_sheet.last_seen_source_fingerprint,
        last_sync_started_at=tracked_sheet.last_sync_started_at,
        last_sync_finished_at=tracked_sheet.last_sync_finished_at,
        last_sync_status=(
            tracked_sheet.last_sync_status.value
            if tracked_sheet.last_sync_status is not None
            else None
        ),
        last_sync_error=tracked_sheet.last_sync_error,
        last_sync_rows_read=tracked_sheet.last_sync_rows_read,
        last_sync_rows_inserted=tracked_sheet.last_sync_rows_inserted,
        created_at=tracked_sheet.created_at,
        updated_at=tracked_sheet.updated_at,
    )


def _extract_spreadsheet_id(spreadsheet_url: str | None) -> str | None:
    if not spreadsheet_url:
        return None
    match = _SPREADSHEET_ID_RE.search(spreadsheet_url)
    if match is not None:
        return match.group(1)
    return None


def _extract_sheet_gid(spreadsheet_url: str | None) -> int | None:
    if not spreadsheet_url:
        return None
    match = _GID_RE.search(spreadsheet_url)
    if match is None:
        return None
    return int(match.group(1))
