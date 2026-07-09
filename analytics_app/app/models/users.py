from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from analytics_app.app.models.base import Base


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


class CbtbaseUser(Base):
    __tablename__ = "cbtbase_users"

    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100))
    join_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    utm_mark: Mapped[str | None] = mapped_column(String(100), nullable=True)

    events: Mapped[list["CbtbaseEvent"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    payment_events: Mapped[list["PaymentEvent"]] = relationship(
        back_populates="cbtbase_user",
    )


class CbtbaseEvent(Base):
    __tablename__ = "cbtbase_events"

    user_id: Mapped[int] = mapped_column(ForeignKey("cbtbase_users.id"), nullable=False)
    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    user: Mapped["CbtbaseUser"] = relationship(back_populates="events")


class PsygastroUser(Base):
    __tablename__ = "psygastro_users"

    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100))
    join_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    utm_mark: Mapped[str | None] = mapped_column(String(100), nullable=True)

    events: Mapped[list["PsygastroEvent"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    payment_events: Mapped[list["PaymentEvent"]] = relationship(
        back_populates="psygastro_user",
    )


class PsygastroEvent(Base):
    __tablename__ = "psygastro_events"

    user_id: Mapped[int] = mapped_column(ForeignKey("psygastro_users.id"), nullable=False)
    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    user: Mapped["PsygastroUser"] = relationship(back_populates="events")
