from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from analytics_app.app.schemas import Service


class TelegramTemplateKind(str, Enum):
    SINGLE = "single"
    ALBUM = "album"


class TelegramTemplateStatus(str, Enum):
    COLLECTING = "collecting"
    READY = "ready"


class BroadcastStatus(str, Enum):
    SCHEDULED = "scheduled"
    SENDING = "sending"
    SENT = "sent"
    CANCELLED = "cancelled"
    FAILED = "failed"


class AudienceType(str, Enum):
    ALL = "all"
    UTM = "utm"
    EVENT = "event"


class AdminTelegramTemplateListRow(BaseModel):
    id: int
    kind: TelegramTemplateKind
    preview_text: str | None = None
    items_count: int
    created_at: datetime


class AdminTelegramTemplateListResponse(BaseModel):
    items: list[AdminTelegramTemplateListRow]
    has_more: bool


class AdminTelegramTemplateSendTestResponse(BaseModel):
    template_id: int
    sent_messages_count: int


class AdminTelegramTemplateSendTestRequest(BaseModel):
    service: Service


class AdminBroadcastCreateRequest(BaseModel):
    template_id: int
    service: Service
    audience_type: AudienceType
    audience_filter: dict[str, Any] = Field(default_factory=dict)
    scheduled_at: datetime


class AdminBroadcastResponse(BaseModel):
    id: int
    template_id: int
    service: Service
    audience_type: AudienceType
    audience_filter: dict[str, Any]
    status: BroadcastStatus
    scheduled_at: datetime
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class AdminBroadcastListRow(BaseModel):
    id: int
    template_id: int
    service: Service
    audience_type: AudienceType
    status: BroadcastStatus
    scheduled_at: datetime
    created_at: datetime
    recipients_total: int = 0
    processing_count: int = 0
    sent_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    pending_count: int = 0


class AdminBroadcastListResponse(BaseModel):
    items: list[AdminBroadcastListRow]
    has_more: bool


class AdminBroadcastCancelResponse(BaseModel):
    id: int
    status: BroadcastStatus


class TelegramTemplateIngestRequest(BaseModel):
    service: Service | None = None
    message: dict[str, Any]


class TelegramTemplateIngestResponse(BaseModel):
    template_id: int
    status: TelegramTemplateStatus
    items_count: int
