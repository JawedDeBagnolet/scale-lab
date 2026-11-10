"""Scraper accounts service — CRUD + session management + proxy assignment."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scraper_account import ScraperAccount

logger = logging.getLogger("scraper_accounts")


# ── CRUD ─────────────────────────────────────────────────────────────────

async def list_accounts(
    db: AsyncSession,
    platform: str | None = None,
    status: str | None = None,
) -> list[ScraperAccount]:
    stmt = select(ScraperAccount).order_by(ScraperAccount.created_at.desc())
    if platform:
        stmt = stmt.where(ScraperAccount.platform == platform)
    if status:
        stmt = stmt.where(ScraperAccount.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_account(db: AsyncSession, account_id: UUID) -> ScraperAccount | None:
    return await db.get(ScraperAccount, account_id)


async def create_account(db: AsyncSession, data: dict) -> ScraperAccount:
    account = ScraperAccount(**data)
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def update_account(
    db: AsyncSession, account: ScraperAccount, data: dict
) -> ScraperAccount:
    for k, v in data.items():
        if hasattr(account, k):
            setattr(account, k, v)
    account.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(account)
    return account


async def delete_account(db: AsyncSession, account: ScraperAccount) -> None:
    await db.delete(account)
    await db.commit()


# ── Session management ───────────────────────────────────────────────────

async def save_session(
    db: AsyncSession,
    account_id: UUID,
    session_data: dict,
    user_agent: str | None = None,
    ds_user_id: str | None = None,
) -> ScraperAccount | None:
    """Save extracted session data to a scraper account."""
    account = await db.get(ScraperAccount, account_id)
    if not account:
        return None
    account.session_data = session_data
    if user_agent:
        account.user_agent = user_agent
    if ds_user_id:
        account.ds_user_id = ds_user_id
    account.status = "active"
    account.last_error = None
    account.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(account)
    logger.info("session saved for @%s (%s)", account.username, account.platform)
    return account


async def mark_error(
    db: AsyncSession,
    account_id: UUID,
    error: str,
    status: str = "expired",
) -> None:
    """Mark a scraper account as errored."""
    await db.execute(
        update(ScraperAccount)
        .where(ScraperAccount.id == account_id)
        .values(status=status, last_error=error, updated_at=datetime.now(UTC))
    )
    await db.commit()


async def track_usage(
    db: AsyncSession,
    account_id: UUID,
    bytes_delta: int = 0,
    requests_delta: int = 1,
) -> None:
    """Increment usage counters for a scraper account."""
    await db.execute(
        update(ScraperAccount)
        .where(ScraperAccount.id == account_id)
        .values(
            bytes_used=ScraperAccount.bytes_used + bytes_delta,
            requests_count=ScraperAccount.requests_count + requests_delta,
            last_used_at=datetime.now(UTC),
        )
    )
    await db.commit()


# ── Account picker ───────────────────────────────────────────────────────

async def pick_account(
    db: AsyncSession,
    platform: str = "ig",
    exclude_ids: list[UUID] | None = None,
) -> ScraperAccount | None:
    """Pick the least recently used active scraper account for a platform.

    Used for load balancing scraping tasks across multiple accounts.
    """
    stmt = (
        select(ScraperAccount)
        .where(
            ScraperAccount.platform == platform,
            ScraperAccount.status == "active",
            ScraperAccount.session_data.isnot(None),
        )
        .order_by(ScraperAccount.last_used_at.asc().nullsfirst())
        .limit(1)
    )
    if exclude_ids:
        stmt = stmt.where(ScraperAccount.id.notin_(exclude_ids))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
