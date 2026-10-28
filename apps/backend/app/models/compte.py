import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.persona import Persona


class Compte(Base):
    __tablename__ = "comptes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    handle: Mapped[str] = mapped_column(String(100))
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("personas.id", ondelete="SET NULL"), index=True
    )
    plateforme: Mapped[str] = mapped_column(String(10))                      # ig, th, x
    workflow: Mapped[str] = mapped_column(String(20), default="Onboarding")  # Onboarding, Warmup, Actif
    status: Mapped[str] = mapped_column(String(20), default="ok")            # ok, session, error, suspendu
    device_id: Mapped[str | None] = mapped_column(String(100))
    proxy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("proxies.id", ondelete="SET NULL")
    )
    env: Mapped[dict | None] = mapped_column(JSONB, default=dict)            # config environnement (GoLogin etc.)
    sessions: Mapped[int] = mapped_column(Integer, default=0)
    follows: Mapped[int] = mapped_column(Integer, default=0)
    creds_encrypted: Mapped[dict | None] = mapped_column(JSONB)              # {password, two_fa, token} chiffre
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )

    # Relations
    persona: Mapped["Persona | None"] = relationship(back_populates="comptes")
