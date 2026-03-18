import asyncio
import json
from dataclasses import dataclass
from typing import Any

from analytics_app.app.db import settings

GOOGLE_SHEETS_READ_COLUMNS = ("A", "B", "C", "D", "E", "J")
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
    raw_values: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return not any(value.strip() for value in self.raw_values)


class GoogleSheetsClient:
    def __init__(
        self,
        *,
        service_account_file: str | None = None,
        service_account_json: str | None = None,
        scopes: tuple[str, ...] | None = None,
    ) -> None:
        self._service_account_file = service_account_file
        self._service_account_json = service_account_json
        self._scopes = scopes or _parse_scopes(settings.GOOGLE_SHEETS_SCOPES)
        self._service: Any | None = None

    @classmethod
    def from_settings(cls) -> "GoogleSheetsClient":
        return cls(
            service_account_file=settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE,
            service_account_json=settings.GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON,
            scopes=_parse_scopes(settings.GOOGLE_SHEETS_SCOPES),
        )

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
        service = self._get_service()
        range_name = _build_grid_range(sheet_name=sheet_name, start_row=start_row)

        try:
            response = (
                service.spreadsheets()
                .get(
                    spreadsheetId=spreadsheet_id,
                    ranges=[range_name],
                    includeGridData=True,
                    fields=(
                        "sheets(data(startRow,startColumn,rowData(values(formattedValue))))"
                    ),
                )
                .execute()
            )
        except Exception as exc:  # pragma: no cover - network/credentials path
            raise GoogleSheetsReadError(
                f"Failed to read spreadsheet {spreadsheet_id} / {sheet_name}: {exc}"
            ) from exc

        return _parse_sheet_rows(response, fallback_start_row=start_row)

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service

        try:
            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:  # pragma: no cover - depends on optional deps
            raise GoogleSheetsConfigurationError(
                "Google Sheets dependencies are missing. Install google-api-python-client and google-auth."
            ) from exc

        credentials = self._load_credentials(Credentials)
        self._service = build(
            "sheets",
            "v4",
            credentials=credentials,
            cache_discovery=False,
        )
        return self._service

    def _load_credentials(self, credentials_cls: Any) -> Any:
        if self._service_account_json:
            info = json.loads(self._service_account_json)
            return credentials_cls.from_service_account_info(info, scopes=self._scopes)

        if self._service_account_file:
            return credentials_cls.from_service_account_file(
                self._service_account_file,
                scopes=self._scopes,
            )

        raise GoogleSheetsConfigurationError(
            "Google Sheets credentials are not configured. Set GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE or GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON."
        )


def get_google_sheets_client() -> GoogleSheetsClient:
    return GoogleSheetsClient.from_settings()


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
    response: dict[str, Any], *, fallback_start_row: int
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
        raw_values = _extract_row_values(row)
        parsed_rows.append(
            GoogleSheetRow(
                source_row_num=start_row_index + offset + 1,
                full_name=_optional_value(raw_values[0]),
                email=_optional_value(raw_values[1]),
                raw_payment_value=_optional_value(raw_values[2]),
                nickname=_optional_value(raw_values[3]),
                event_date_raw=_optional_value(raw_values[4]),
                platform_id_raw=_optional_value(raw_values[9]),
                raw_values=tuple(raw_values),
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
