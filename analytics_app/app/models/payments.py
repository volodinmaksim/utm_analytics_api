from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from analytics_app.app.models.base import Base
from analytics_app.app.models.enums import ServiceType, _enum_values, PaymentEventType


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
        Index(
            "ix_payment_events_cbtbase_user_id_event_date",
            "cbtbase_user_id",
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
    cbtbase_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("cbtbase_users.id"),
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
    cbtbase_user: Mapped["CbtbaseUser | None"] = relationship(
        back_populates="payment_events",
    )
