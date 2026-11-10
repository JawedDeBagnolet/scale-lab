"""Scraper accounts — comptes dédiés au scraping via API privée (IG, Threads, X).

Séparés des comptes du module Comptes (automation iPhone).
Stockent la session complète (headers, cookies, tokens) extraite après login
sur l'iPhone via ScaleTweak, et utilisent des proxies Scrapigo en interne.
"""

from datetime import UTC, datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

import uuid


class ScraperAccount(Base):
    __tablename__ = "scraper_accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    platform: Mapped[str] = mapped_column(String(10))  # ig, threads, x
    username: Mapped[str] = mapped_column(String(100))
    password: Mapped[str | None] = mapped_column(Text, nullable=True)  # chiffré

    # Session extraite — le JSON complet (authorization, cookies, headers, etc.)
    session_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ds_user_id: Mapped[str | None] = mapped_column(String(50), nullable=True)  # IG user PK

    # Proxy Scrapigo — config auto-générée (sticky session ID, country, etc.)
    proxy_country: Mapped[str] = mapped_column(String(5), default="FR")
    proxy_sticky_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, active, expired, banned, rate_limited
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Consommation
    bytes_used: Mapped[int] = mapped_column(BigInteger, default=0)
    requests_count: Mapped[int] = mapped_column(Integer, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
