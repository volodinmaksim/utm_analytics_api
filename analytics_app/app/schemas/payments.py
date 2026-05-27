from datetime import datetime

from pydantic import BaseModel, ConfigDict

from analytics_app.app.schemas.analytics import Period, Service


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
