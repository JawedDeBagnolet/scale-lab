import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Fan(Base):
    __tablename__ = "fans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oc_external_id: Mapped[str | None] = mapped_column(String(200), unique=True)  # OnlyChat fan ID
    pseudo: Mapped[str] = mapped_column(String(100))
    creator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    compte_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    platform_origin: Mapped[str] = mapped_column(String(10))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    total_spent: Mapped[int] = mapped_column(Integer, default=0)
    last_activity: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oc_external_id: Mapped[str | None] = mapped_column(String(200), unique=True)  # OnlyChat tx ID
    fan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("fans.id", ondelete="CASCADE")
    )
    creator_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    transaction_type: Mapped[str] = mapped_column(String(10))  # sub / ppv / tip
    amount: Mapped[int] = mapped_column(Integer)  # dollars
    script_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scripts.id", ondelete="SET NULL")
    )
    compte_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("comptes.id", ondelete="SET NULL")
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    oc_external_id: Mapped[str | None] = mapped_column(String(200), unique=True)  # OnlyChat script ID
    script_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    folder: Mapped[str | None] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[bool] = mapped_column(Boolean, default=False)
    steps: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)
    stats: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
