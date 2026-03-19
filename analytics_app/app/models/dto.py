from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Service(str, Enum):
    RPP = "rpp"
    FARMA = "farma"


class Period(str, Enum):
    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class OverviewResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    service: Service
    period: Period
    total_users: int
    file_clicks: int
    with_utm: int
    without_utm: int


class NewUsersRow(BaseModel):
    period: datetime | None
    new_users: int


class FunnelStepRow(BaseModel):
    key: str
    label: str
    users: int
    conversion_from_start: float | None = None
    conversion_from_previous: float | None = None


class FunnelResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    service: Service
    period: Period
    new_users: list[NewUsersRow]
    steps: list[FunnelStepRow]


class AudienceRow(BaseModel):
    name: str
    users: int
    pct: float | None = None


class AudienceResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    service: Service
    segments: list[AudienceRow]
    branches: list[AudienceRow]


class ContentEventRow(BaseModel):
    key: str
    label: str
    users: int


class ContentResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    service: Service
    items: list[ContentEventRow]


class UtmMarkRow(BaseModel):
    utm_mark: str
    users: int
    paid_users: int = 0
    file_received_users: int = 0
    revenue_sum: float = 0.0
    conversion_to_payment: float | None = None


class UtmTimeseriesRow(BaseModel):
    period: datetime | None
    with_utm: int
    without_utm: int


class UTMResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    service: Service
    period: Period
    marks: list[UtmMarkRow]
    timeseries: list[UtmTimeseriesRow]


class FeedbackRow(BaseModel):
    post_id: str
    likes: int
    dislikes: int
    rating: int


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    service: Service
    items: list[FeedbackRow]


class WishRow(BaseModel):
    timestamp: datetime | None
    wish_text: str


class WishesResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    service: Service
    items: list[WishRow]


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


class PaymentOverviewResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    service: Service
    period: Period
    payment_clicks_count: int
    successful_payments_count: int
    paid_users_count: int
    matched_successful_payments_count: int
    matched_paid_users_count: int
    revenue_sum: float
    matched_revenue_sum: float
    avg_payment_amount: float | None = None
    arppu: float | None = None
    click_to_success_conversion: float | None = None
    unmatched_events_count: int


class PaymentTimeseriesRow(BaseModel):
    period: datetime | None
    payment_clicks_count: int
    successful_payments_count: int
    revenue_sum: float
    paid_users_count: int


class PaymentTimeseriesResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    service: Service
    period: Period
    items: list[PaymentTimeseriesRow]


class PaymentSourceRow(BaseModel):
    tracked_sheet_id: int
    service: Service
    spreadsheet_id: str
    sheet_name: str
    is_active: bool
    events_count: int
    payment_clicks_count: int
    successful_payments_count: int
    revenue_sum: float
    unmatched_events_count: int
    last_sync_started_at: datetime | None = None
    last_sync_finished_at: datetime | None = None
    last_sync_status: str | None = None
    last_sync_error: str | None = None
    last_sync_rows_read: int | None = None
    last_sync_rows_inserted: int | None = None


class PaymentSourcesResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    service: Service
    period: Period
    items: list[PaymentSourceRow]


class RecentPaymentRow(BaseModel):
    event_date: datetime | None = None
    amount: float
    nickname: str | None = None
    full_name: str | None = None
    email: str | None = None
    matched_user_tg_id: int | None = None
    source_sheet_name: str


class RecentPaymentsResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    service: Service
    items: list[RecentPaymentRow]


class PaymentUserStepRow(BaseModel):
    key: str
    label: str
    completed_at: datetime | None = None


class PaymentUserFeedbackRow(BaseModel):
    timestamp: datetime | None = None
    post_id: str
    vote: str


class PaymentUserHistoryPaymentRow(BaseModel):
    event_date: datetime | None = None
    amount: float
    source_sheet_name: str


class PaymentUserDetailResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    service: Service
    matched_user_tg_id: int
    username: str | None = None
    join_date: datetime | None = None
    utm_mark: str | None = None
    steps: list[PaymentUserStepRow]
    feedback: list[PaymentUserFeedbackRow]
    payments: list[PaymentUserHistoryPaymentRow]
