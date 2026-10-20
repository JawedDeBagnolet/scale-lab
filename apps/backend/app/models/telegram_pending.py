import uuid
from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class TelegramPending(Base):
    """A model who clicked /start on the bot but hasn't been linked to a persona yet."""

    __tablename__ = "telegram_pending"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    persona_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    tg_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    tg_username: Mapped[str | None] = mapped_column(String(100))
    tg_first_name: Mapped[str | None] = mapped_column(String(200))
    tg_lang: Mapped[str | None] = mapped_column(String(10))  # fr, en, es, th, vi
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
