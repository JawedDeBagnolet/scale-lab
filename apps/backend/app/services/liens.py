from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lien import ClickEvent, Domain, TrackedLink
from app.schemas.lien import (
    ClickEventCreate,
    DomainCreate,
    LinkStats,
    TrackedLinkCreate,
)


# --- Links --------------------------------------------------------------------


async def list_links(
    db: AsyncSession,
    *,
    domain_id: UUID | None = None,
    plateforme: str | None = None,
    active: bool | None = None,
) -> Sequence[TrackedLink]:
    q = select(TrackedLink).order_by(TrackedLink.created_at.desc())
    if domain_id is not None:
        q = q.where(TrackedLink.domain_id == domain_id)
    if plateforme:
        q = q.where(TrackedLink.plateforme == plateforme)
    if active is not None:
        q = q.where(TrackedLink.active == active)
    result = await db.execute(q)
    return result.scalars().all()


async def get_link(db: AsyncSession, link_id: UUID) -> TrackedLink | None:
    return await db.get(TrackedLink, link_id)


async def create_link(db: AsyncSession, data: TrackedLinkCreate) -> TrackedLink:
    link = TrackedLink(**data.model_dump())
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return link


async def update_link(db: AsyncSession, link: TrackedLink, data: dict) -> TrackedLink:
    for k, v in data.items():
        setattr(link, k, v)
    await db.commit()
    await db.refresh(link)
    return link


async def delete_link(db: AsyncSession, link: TrackedLink) -> None:
    await db.delete(link)
    await db.commit()


async def get_link_stats(db: AsyncSession, link_id: UUID) -> LinkStats:
    now = datetime.now(UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    seven_days_ago = now - timedelta(days=7)

    total_q = select(func.count()).select_from(ClickEvent).where(
        ClickEvent.link_id == link_id
    )
    week_q = total_q.where(ClickEvent.clicked_at >= seven_days_ago)
    today_q = total_q.where(ClickEvent.clicked_at >= today_start)
    countries_q = (
        select(func.count(func.distinct(ClickEvent.country)))
        .select_from(ClickEvent)
        .where(ClickEvent.link_id == link_id)
    )

    total = (await db.execute(total_q)).scalar() or 0
    week = (await db.execute(week_q)).scalar() or 0
    today = (await db.execute(today_q)).scalar() or 0
    countries = (await db.execute(countries_q)).scalar() or 0

    return LinkStats(
        clicks_total=total,
        clicks_7d=week,
        clicks_today=today,
        unique_countries=countries,
    )


# --- Domains ------------------------------------------------------------------


async def get_domain(db: AsyncSession, domain_id: UUID) -> Domain | None:
    return await db.get(Domain, domain_id)


async def list_domains(db: AsyncSession) -> Sequence[Domain]:
    q = select(Domain).order_by(Domain.host)
    result = await db.execute(q)
    return result.scalars().all()


async def create_domain(db: AsyncSession, data: DomainCreate) -> Domain:
    domain = Domain(**data.model_dump())
    db.add(domain)
    await db.commit()
    await db.refresh(domain)
    return domain


async def update_domain(db: AsyncSession, domain: Domain, data: dict) -> Domain:
    for k, v in data.items():
        setattr(domain, k, v)
    await db.commit()
    await db.refresh(domain)
    return domain


async def delete_domain(db: AsyncSession, domain: Domain) -> None:
    await db.delete(domain)
    await db.commit()


# --- Clicks -------------------------------------------------------------------


async def record_click(
    db: AsyncSession, link_id: UUID, data: ClickEventCreate
) -> ClickEvent:
    click = ClickEvent(link_id=link_id, **data.model_dump())
    db.add(click)
    await db.commit()
    await db.refresh(click)
    return click


async def list_clicks(
    db: AsyncSession, link_id: UUID, limit: int = 100
) -> Sequence[ClickEvent]:
    q = (
        select(ClickEvent)
        .where(ClickEvent.link_id == link_id)
        .order_by(ClickEvent.clicked_at.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    return result.scalars().all()
