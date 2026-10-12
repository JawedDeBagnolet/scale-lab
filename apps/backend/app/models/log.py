"""Journal d'événements et incidents."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMPTZ, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    timestamp: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, default=lambda: datetime.now(UTC), index=True
    )
    module: Mapped[str] = mapped_column(String(50), index=True)  # comptes, posting, liens, ...
    event_type: Mapped[str] = mapped_column(String(100))  # compte.error, publish.ok, link.created, ...
    level: Mapped[str] = mapped_column(String(10), default="info")  # info, warning, error, critical
    target: Mapped[str | None] = mapped_column(String(200))  # @handle, link URL, device ID, etc.
    cause: Mapped[str | None] = mapped_column(String(200))
    code: Mapped[str | None] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    meta: Mapped[dict | None] = mapped_column(JSONB, default=dict)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    module: Mapped[str] = mapped_column(String(50), index=True)
    event_type: Mapped[str] = mapped_column(String(100))
    target: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open, ack, resolved
    event_count: Mapped[int] = mapped_column(Integer, default=1)
    first_seen: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, default=lambda: datetime.now(UTC)
    )
    last_seen: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, default=lambda: datetime.now(UTC)
    )
    solutions: Mapped[dict | None] = mapped_column(JSONB, default=list)
    related_events: Mapped[list | None] = mapped_column(JSONB, default=list)
    meta: Mapped[dict | None] = mapped_column(JSONB, default=dict)


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    module: Mapped[str] = mapped_column(String(50))
    event_type: Mapped[str] = mapped_column(String(100))
    threshold_errors: Mapped[int] = mapped_column(Integer, default=3)
    threshold_actions: Mapped[int] = mapped_column(Integer, default=10)
    tg_enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, default=lambda: datetime.now(UTC)
    )
