import asyncio
import json
from dataclasses import dataclass
from typing import Any

from analytics_app.app.db import settings

GOOGLE_SHEETS_RANGE_END_COLUMN = "J"
_GOOGLE_SHEETS_COLUMN_COUNT = 10


class GoogleSheetsConfigurationError(RuntimeError):
    pass


class GoogleSheetsReadError(RuntimeError):
    pass


@dataclass(slots=True, frozen=True)
class GoogleSheetRow:
    source_row_num: int
    full_name: str | None
    email: str | None
    raw_payment_value: str | None
    nickname: str | None
    event_date_raw: str | None
    platform_id_raw: str | None
    is_empty: bool


class GoogleSheetsClient:
    def __init__(
        self,
        *,
        credentials_file: str | None,
        credentials_json: str | None,
        scopes: tuple[str, ...],
    ) -> None:
        self.credentials_file = credentials_file
        self.credentials_json = credentials_json
        self.scopes = scopes
        self._service: Any | None = None

    async def fetch_rows(
        self,
        *,
        spreadsheet_id: str,
        sheet_name: str,
        start_row: int = 2,
    ) -> list[GoogleSheetRow]:
        if start_row < 1:
            raise ValueError("start_row must be greater than or equal to 1")

        return await asyncio.to_thread(
            self._fetch_rows_sync,
            spreadsheet_id,
            sheet_name,
            start_row,
        )

    def _fetch_rows_sync(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        start_row: int,
    ) -> list[GoogleSheetRow]:
        service = self.build_service()
        range_name = _build_grid_range(sheet_name=sheet_name, start_row=start_row)

        try:
            response = (
                service.spreadsheets()
                .get(
                    spreadsheetId=spreadsheet_id,
                    ranges=[range_name],
                    includeGridData=True,
                    fields="sheets(data(startRow,rowData(values(formattedValue))))",
                )
                .execute()
            )
        except Exception as exc:  # pragma: no cover - network/credentials path
            raise GoogleSheetsReadError(
                f"Failed to read spreadsheet {spreadsheet_id} / {sheet_name}: {exc}"
            ) from exc

        return _parse_sheet_rows(response, fallback_start_row=start_row)

    def build_service(self) -> Any:
        if self._service is not None:
            return self._service

        try:
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover - depends on optional deps
            raise GoogleSheetsConfigurationError(
                "Google Sheets dependency is missing. Install google-api-python-client."
            ) from exc

        credentials = self.build_credentials()
        self._service = build(
            "sheets",
            "v4",
            credentials=credentials,
            cache_discovery=False,
        )
        return self._service

    def build_credentials(self) -> Any:
        try:
            from google.oauth2.service_account import Credentials
        except ImportError as exc:  # pragma: no cover - depends on optional deps
            raise GoogleSheetsConfigurationError(
                "Google auth dependency is missing. Install google-auth."
            ) from exc

        if self.credentials_json:
            info = json.loads(self.credentials_json)
            return Credentials.from_service_account_info(info, scopes=self.scopes)

        if self.credentials_file:
            return Credentials.from_service_account_file(
                self.credentials_file,
                scopes=self.scopes,
            )

        raise GoogleSheetsConfigurationError(
            "Google Sheets credentials are not configured. Set GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE or GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON."
        )


def get_google_sheets_client() -> GoogleSheetsClient:
    return GoogleSheetsClient(
        credentials_file=settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE,
        credentials_json=settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON,
        scopes=_parse_scopes(settings.GOOGLE_SHEETS_SCOPES),
    )


def _parse_scopes(raw_scopes: str) -> tuple[str, ...]:
    scopes = tuple(scope.strip() for scope in raw_scopes.split(",") if scope.strip())
    if not scopes:
        raise GoogleSheetsConfigurationError(
            "GOOGLE_SHEETS_SCOPES must contain at least one scope"
        )
    return scopes


def _build_grid_range(*, sheet_name: str, start_row: int) -> str:
    safe_sheet_name = sheet_name.replace("'", "''")
    return f"'{safe_sheet_name}'!A{start_row}:{GOOGLE_SHEETS_RANGE_END_COLUMN}"


def _parse_sheet_rows(
    response: dict[str, Any],
    *,
    fallback_start_row: int,
) -> list[GoogleSheetRow]:
    sheets = response.get("sheets") or []
    if not sheets:
        return []

    data_blocks = sheets[0].get("data") or []
    if not data_blocks:
        return []

    data_block = data_blocks[0]
    start_row_index = int(data_block.get("startRow", fallback_start_row - 1))
    rows = data_block.get("rowData") or []

    parsed_rows: list[GoogleSheetRow] = []
    for offset, row in enumerate(rows):
        values = _extract_row_values(row)
        parsed_rows.append(
            GoogleSheetRow(
                source_row_num=start_row_index + offset + 1,
                full_name=_optional_value(values[0]),
                email=_optional_value(values[1]),
                raw_payment_value=_optional_value(values[2]),
                nickname=_optional_value(values[3]),
                event_date_raw=_optional_value(values[4]),
                platform_id_raw=_optional_value(values[9]),
                is_empty=not any(value.strip() for value in values),
            )
        )

    return parsed_rows


def _extract_row_values(row: dict[str, Any]) -> list[str]:
    cells = row.get("values") or []
    values = [
        _cell_formatted_value(cell) for cell in cells[:_GOOGLE_SHEETS_COLUMN_COUNT]
    ]
    if len(values) < _GOOGLE_SHEETS_COLUMN_COUNT:
        values.extend([""] * (_GOOGLE_SHEETS_COLUMN_COUNT - len(values)))
    return values


def _cell_formatted_value(cell: dict[str, Any]) -> str:
    return str(cell.get("formattedValue") or "").strip()


def _optional_value(value: str) -> str | None:
    return value or None
