from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

import uuid


class IPhone(Base):
    __tablename__ = "iphones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(50))
    ios_version: Mapped[str] = mapped_column(String(20))
    rack: Mapped[str | None] = mapped_column(String(20))
    market: Mapped[str | None] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="offline")  # online, offline
    jailbreak: Mapped[bool] = mapped_column(Boolean, default=False)
    max_comptes: Mapped[int] = mapped_column(Integer, default=3)
    proxy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # --- Connection mode ----------------------------------------------------------
    # "usb"    : USB cable via pymobiledevice3 (default, legacy)
    # "tunnel" : reverse SSH tunnel exposing MCP + SSH on localhost
    connection_type: Mapped[str] = mapped_column(
        String(10), default="usb", server_default="usb"
    )
    # Ports exposed by the reverse SSH tunnel (only used when connection_type="tunnel")
    mcp_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ssh_port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # --------------------------------------------------------------------------
    telemetry: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
