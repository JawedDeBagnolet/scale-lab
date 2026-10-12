"""Scenarios d'automatisation, runs et plages horaires."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150))
    origin: Mapped[str] = mapped_column(String(20))  # spontane, login, creation
    couple: Mapped[str | None] = mapped_column(String(100))  # nom du couple persona/plateforme
    plateforme: Mapped[str | None] = mapped_column(String(10))  # ig, th, x
    slots: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)  # refs plages horaires
    steps: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)  # actions + presets + delais
    loop: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scenario_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    comptes: Mapped[list | None] = mapped_column(JSONB, default=list)  # list of compte UUIDs
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, paused, done, error
    blocked_accounts: Mapped[list | None] = mapped_column(JSONB, default=list)
    journal: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)  # log entries
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class PlageHoraire(Base):
    __tablename__ = "plages_horaires"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100))
    days: Mapped[list | None] = mapped_column(JSONB, default=list)  # [0..6] lundi=0
    ranges: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)  # [{start: "08:00", end: "12:00"}]
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
