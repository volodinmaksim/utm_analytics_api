from datetime import datetime
from sqlalchemy import (
    UniqueConstraint,
    Index,
    Enum as SqlEnum,
    String,
    Text,
    BigInteger,
    Integer,
    DateTime,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from analytics_app.app.models.base import Base
from analytics_app.app.models.enums import ServiceType, _enum_values, SyncStatus


class TrackedSheet(Base):
    __tablename__ = "tracked_sheets"
    __table_args__ = (
        UniqueConstraint(
            "spreadsheet_id",
            "sheet_name",
            name="uq_tracked_sheets_spreadsheet_id_sheet_name",
        ),
        Index("ix_tracked_sheets_service_is_active", "service", "is_active"),
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
    spreadsheet_id: Mapped[str] = mapped_column(String(255), nullable=False)
    spreadsheet_url: Mapped[str] = mapped_column(Text, nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sheet_gid: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
    poll_interval_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=600,
        server_default="600",
    )
    last_seen_row_num: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_seen_source_fingerprint: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    last_sync_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_sync_finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_sync_status: Mapped[SyncStatus | None] = mapped_column(
        SqlEnum(
            SyncStatus,
            name="sync_status",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=True,
    )
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_sync_rows_read: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_sync_rows_inserted: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    payment_events: Mapped[list["PaymentEvent"]] = relationship(
        back_populates="tracked_sheet",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
