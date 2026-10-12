"""Workspace settings — single-row config table."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class WorkspaceSettings(Base):
    """Exactly one row, enforced by the fixed primary key (id=1)."""

    __tablename__ = "workspace_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    name: Mapped[str] = mapped_column(String(100), default="Scale Lab")
    currency: Mapped[str] = mapped_column(String(5), default="USD")
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Paris")

    # Integration: OnlyChat
    oc_api_key: Mapped[str | None] = mapped_column(Text)
    oc_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    oc_last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Integration: GetMySocial
    gms_api_key: Mapped[str | None] = mapped_column(Text)
    gms_connected: Mapped[bool] = mapped_column(Boolean, default=False)
    gms_last_sync: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Integration: Telegram alert bot
    tg_bot_token: Mapped[str | None] = mapped_column(Text)
    tg_chat_id: Mapped[str | None] = mapped_column(String(100))
    tg_connected: Mapped[bool] = mapped_column(Boolean, default=False)

    # Integration: environment providers (GoLogin, GeeLark)
    env_providers: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    # Notifications preferences
    notifications: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
