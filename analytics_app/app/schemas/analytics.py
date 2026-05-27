from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict


class Service(str, Enum):
    RPP = "rpp"
    FARMA = "farma"
    SFBT = "sfbt"


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
