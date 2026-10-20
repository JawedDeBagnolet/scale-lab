import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.compte import Compte


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prs_id: Mapped[str | None] = mapped_column(String(100))              # OnlyChat ID
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    color: Mapped[str | None] = mapped_column(String(7))                  # hex #6d5ef0
    market: Mapped[str | None] = mapped_column(String(10))                # code marche (US, FR...)
    city: Mapped[str | None] = mapped_column(String(100))
    age: Mapped[int | None] = mapped_column(Integer)
    platforms: Mapped[list[str] | None] = mapped_column(ARRAY(String))    # ["ig", "th", "x"]
    niches: Mapped[list[str] | None] = mapped_column(ARRAY(String))       # slugs niches
    bios: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)  # [{platform, text}]
    prompt: Mapped[str | None] = mapped_column(Text)                      # AI prompt
    funnel: Mapped[str | None] = mapped_column(Text)
    telegram: Mapped[dict | None] = mapped_column(JSONB, default=dict)    # {bot, username, chat_id, langue, groupe, topic}
    photo_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Relations
    comptes: Mapped[list["Compte"]] = relationship(
        back_populates="persona", lazy="selectin", order_by="Compte.handle"
    )
