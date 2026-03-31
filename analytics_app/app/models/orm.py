from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)


class ServiceType(str, Enum):
    RPP = "rpp"
    FARMA = "farma"
    SFBT = "sfbt"


class PaymentEventType(str, Enum):
    PAYMENT_CLICK = "payment_click"
    PAYMENT_SUCCESS = "payment_success"


class SyncStatus(str, Enum):
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"


def _enum_values(enum_cls: type[Enum]) -> list[str]:
    return [member.value for member in enum_cls]


class FarmaUser(Base):
    __tablename__ = "farma_users"

    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100))
    join_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    utm_mark: Mapped[str | None] = mapped_column(String(100), nullable=True)

    events: Mapped[list["FarmaEvent"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    payment_events: Mapped[list["PaymentEvent"]] = relationship(
        back_populates="farma_user",
    )


class FarmaEvent(Base):
    __tablename__ = "farma_events"

    user_id: Mapped[int] = mapped_column(ForeignKey("farma_users.id"), nullable=False)
    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    user: Mapped["FarmaUser"] = relationship(back_populates="events")


class User(Base):
    __tablename__ = "users"

    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100))
    segment: Mapped[str | None] = mapped_column(String(15), nullable=True)
    join_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    utm_mark: Mapped[str | None] = mapped_column(String(100), nullable=True)

    events: Mapped[list["Events"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    payment_events: Mapped[list["PaymentEvent"]] = relationship(
        back_populates="rpp_user",
    )


class Events(Base):
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_user_id_timestamp", "user_id", "timestamp"),)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    event_name: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="events")


class SfbtUser(Base):
    __tablename__ = "sfbt_users"

    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100))
    join_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    utm_mark: Mapped[str | None] = mapped_column(String(100), nullable=True)

    events: Mapped[list["SfbtEvent"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    payment_events: Mapped[list["PaymentEvent"]] = relationship(
        back_populates="sfbt_user",
    )


class SfbtEvent(Base):
    __tablename__ = "sfbt_events"

    user_id: Mapped[int] = mapped_column(ForeignKey("sfbt_users.id"), nullable=False)
    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    user: Mapped["SfbtUser"] = relationship(back_populates="events")


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


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    __table_args__ = (
        UniqueConstraint(
            "tracked_sheet_id",
            "source_row_num",
            name="uq_payment_events_tracked_sheet_id_source_row_num",
        ),
        UniqueConstraint(
            "source_fingerprint",
            name="uq_payment_events_source_fingerprint",
        ),
        Index("ix_payment_events_service_event_date", "service", "event_date"),
        Index("ix_payment_events_service_platform_id", "service", "platform_id"),
        Index("ix_payment_events_user_id_event_date", "user_id", "event_date"),
        Index(
            "ix_payment_events_farma_user_id_event_date",
            "farma_user_id",
            "event_date",
        ),
        Index(
            "ix_payment_events_sfbt_user_id_event_date",
            "sfbt_user_id",
            "event_date",
        ),
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
    tracked_sheet_id: Mapped[int] = mapped_column(
        ForeignKey("tracked_sheets.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_row_num: Mapped[int] = mapped_column(Integer, nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(128), nullable=False)
    platform_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nickname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    event_type: Mapped[PaymentEventType] = mapped_column(
        SqlEnum(
            PaymentEventType,
            name="payment_event_type",
            native_enum=False,
            values_callable=_enum_values,
        ),
        nullable=False,
    )
    amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    raw_payment_value: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    farma_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("farma_users.id"),
        nullable=True,
    )
    sfbt_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("sfbt_users.id"),
        nullable=True,
    )
    matched_user_tg_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    inserted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    tracked_sheet: Mapped["TrackedSheet"] = relationship(
        back_populates="payment_events"
    )
    rpp_user: Mapped["User | None"] = relationship(back_populates="payment_events")
    farma_user: Mapped["FarmaUser | None"] = relationship(
        back_populates="payment_events",
    )
    sfbt_user: Mapped["SfbtUser | None"] = relationship(
        back_populates="payment_events",
    )
