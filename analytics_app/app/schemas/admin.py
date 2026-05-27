from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from analytics_app.app.schemas.analytics import Service


class TrackedSheetCreateRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True, str_strip_whitespace=True)

    service: Service
    sheet_name: str
    spreadsheet_url: str | None = None
    spreadsheet_id: str | None = None
    poll_interval_seconds: int = Field(default=600, ge=1)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_source(self) -> "TrackedSheetCreateRequest":
        if not self.spreadsheet_url and not self.spreadsheet_id:
            raise ValueError("spreadsheet_url or spreadsheet_id is required")
        return self


class TrackedSheetUpdateRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=True, str_strip_whitespace=True)

    service: Service | None = None
    sheet_name: str | None = None
    spreadsheet_url: str | None = None
    spreadsheet_id: str | None = None
    poll_interval_seconds: int | None = Field(default=None, ge=1)
    is_active: bool | None = None


class TrackedSheetResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    id: int
    service: Service
    spreadsheet_id: str
    spreadsheet_url: str
    sheet_name: str
    sheet_gid: int | None = None
    is_active: bool
    poll_interval_seconds: int
    last_seen_row_num: int | None = None
    last_seen_source_fingerprint: str | None = None
    last_sync_started_at: datetime | None = None
    last_sync_finished_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None
    last_sync_rows_read: int | None = None
    last_sync_rows_inserted: int | None = None
    created_at: datetime
    updated_at: datetime


class TrackedSheetsListResponse(BaseModel):
    items: list[TrackedSheetResponse]


class TrackedSheetSyncResponse(BaseModel):
    tracked_sheet_id: int
    status: str
    rows_read: int = 0
    rows_inserted: int = 0
    invalid_rows: int = 0
    empty_rows: int = 0
    error: str | None = None
