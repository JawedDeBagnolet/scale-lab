"""Pending Telegram group — stored when the bot is added to a group."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TelegramPendingGroup(Base):
    __tablename__ = "telegram_pending_group"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    chat_title: Mapped[str | None] = mapped_column(String(300))
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
