from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)


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
    segment: Mapped[str] = mapped_column(String(15), nullable=True)
    join_date: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    utm_mark: Mapped[str] = mapped_column(String(100), nullable=True)

    events: Mapped[list["Events"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Events(Base):
    __tablename__ = "events"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    event_name: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="events")
