from datetime import UTC, datetime

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import TIMESTAMPTZ, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

import uuid


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    handle: Mapped[str] = mapped_column(String(100))
    plateforme: Mapped[str] = mapped_column(String(10))  # ig, th, x
    market: Mapped[str | None] = mapped_column(String(10))
    niche_id: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok, prive, renomme, banni
    source: Mapped[str | None] = mapped_column(String(50))  # manual, veille, import
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMPTZ,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
