from datetime import datetime

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sqlalchemy import (
    Enum as SqlEnum,
    BigInteger,
    String,
    Integer,
    DateTime,
    func,
    Index,
    UniqueConstraint,
    ForeignKey,
    Text,
    text,
)

from analytics_app.app.models.enums import (
    _enum_values,
    TelegramTemplateKind,
    ServiceType,
    TelegramTemplateStatus,
    BroadcastStatus,
    BroadcastRecipientStatus,
)
from analytics_app.app.models.base import Base


class TelegramTemplate(Base):
    __tablename__ = "telegram_templates"

    service: Mapped[ServiceType | None] = mapped_column(
        SqlEnum(
            ServiceType,
            name="service_type",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=True,
    )

    source_chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    media_group_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    kind: Mapped[TelegramTemplateKind] = mapped_column(
        SqlEnum(
            TelegramTemplateKind,
            name="telegram_template_kind",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    status: Mapped[TelegramTemplateStatus] = mapped_column(
        SqlEnum(
            TelegramTemplateStatus,
            name="telegram_template_status",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    preview_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    items_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    ready_after: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    items: Mapped[list["TelegramTemplateItem"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    broadcasts: Mapped[list["Broadcast"]] = relationship(back_populates="template")

    __table_args__ = (
        Index(
            "ix_telegram_templates_status_created_at",
            status,
            created_at.desc(),
        ),
        Index(
            "ix_telegram_templates_collecting_media_group",
            source_chat_id,
            media_group_id,
            status,
        ),
        Index(
            "ix_telegram_templates_status_ready_after",
            status,
            ready_after,
        ),
    )


class TelegramTemplateItem(Base):
    __tablename__ = "telegram_template_items"

    template_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False)
    raw_message_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    template: Mapped["TelegramTemplate"] = relationship(back_populates="items")

    __table_args__ = (
        UniqueConstraint(
            "template_id",
            "source_message_id",
            name="uq_template_items_template_message",
        ),
    )


class Broadcast(Base):
    __tablename__ = "broadcasts"

    template_id: Mapped[int] = mapped_column(
        ForeignKey("telegram_templates.id"),
        nullable=False,
    )
    service: Mapped[ServiceType] = mapped_column(
        SqlEnum(
            ServiceType,
            name="service_type",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    audience_type: Mapped[str] = mapped_column(String(50), nullable=False)
    audience_filter: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[BroadcastStatus] = mapped_column(
        SqlEnum(
            BroadcastStatus,
            name="broadcast_status",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    template: Mapped["TelegramTemplate"] = relationship(back_populates="broadcasts")
    recipients: Mapped[list["BroadcastRecipient"]] = relationship(
        cascade="all, delete-orphan",
        back_populates="broadcast",
        passive_deletes=True,
    )

    __table_args__ = (
        Index("ix_broadcasts_status_scheduled_at", "status", "scheduled_at"),
        Index("ix_broadcasts_created_at", created_at.desc()),
    )


class BroadcastRecipient(Base):
    __tablename__ = "broadcast_recipients"

    broadcast_id: Mapped[int] = mapped_column(
        ForeignKey("broadcasts.id", ondelete="CASCADE"), nullable=False
    )
    tg_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[BroadcastRecipientStatus] = mapped_column(
        SqlEnum(
            BroadcastRecipientStatus,
            name="broadcast_recipient_status",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    next_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_message_ids: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    broadcast: Mapped["Broadcast"] = relationship(back_populates="recipients")

    __table_args__ = (
        UniqueConstraint(
            "broadcast_id",
            "tg_id",
            name="uq_broadcast_recipients_broadcast_tg",
        ),
        Index(
            "ix_broadcast_recipients_status_next_attempt_id",
            "status",
            "next_attempt_at",
            "id",
        ),
        Index("ix_broadcast_recipients_broadcast_status", "broadcast_id", "status"),
    )
