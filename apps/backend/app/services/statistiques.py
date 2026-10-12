from collections.abc import Sequence
from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.statistique import DailyStat
from app.schemas.statistique import DailyStatCreate, StatsOverview


async def list_stats(
    db: AsyncSession,
    compte_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Sequence[DailyStat]:
    q = select(DailyStat).where(DailyStat.compte_id == compte_id).order_by(DailyStat.date)
    if date_from:
        q = q.where(DailyStat.date >= date_from)
    if date_to:
        q = q.where(DailyStat.date <= date_to)
    result = await db.execute(q)
    return result.scalars().all()


async def get_overview(db: AsyncSession, compte_id: UUID) -> StatsOverview:
    today = date.today()
    thirty_days_ago = today - timedelta(days=30)

    # Latest followers count (most recent stat)
    latest_q = (
        select(DailyStat.followers)
        .where(DailyStat.compte_id == compte_id)
        .order_by(DailyStat.date.desc())
        .limit(1)
    )
    latest_result = await db.execute(latest_q)
    total_followers = latest_result.scalar() or 0

    # Average engagement rate over last 30 days
    avg_q = (
        select(
            func.avg(
                func.case(
                    (DailyStat.followers > 0, DailyStat.engagements * 100.0 / DailyStat.followers),
                    else_=0.0,
                )
            )
        )
        .where(DailyStat.compte_id == compte_id)
        .where(DailyStat.date >= thirty_days_ago)
    )
    avg_result = await db.execute(avg_q)
    avg_engagement_rate = round(float(avg_result.scalar() or 0), 2)

    # Total reach last 30 days
    reach_q = (
        select(func.coalesce(func.sum(DailyStat.reach), 0))
        .where(DailyStat.compte_id == compte_id)
        .where(DailyStat.date >= thirty_days_ago)
    )
    reach_result = await db.execute(reach_q)
    total_reach_30d = int(reach_result.scalar() or 0)

    # Best day (highest engagements in last 30 days)
    best_q = (
        select(DailyStat.date)
        .where(DailyStat.compte_id == compte_id)
        .where(DailyStat.date >= thirty_days_ago)
        .order_by(DailyStat.engagements.desc())
        .limit(1)
    )
    best_result = await db.execute(best_q)
    best_day = best_result.scalar()

    return StatsOverview(
        total_followers=total_followers,
        avg_engagement_rate=avg_engagement_rate,
        total_reach_30d=total_reach_30d,
        best_day=best_day,
    )


async def create_stat(db: AsyncSession, data: DailyStatCreate) -> DailyStat:
    stat = DailyStat(**data.model_dump())
    db.add(stat)
    await db.commit()
    await db.refresh(stat)
    return stat


async def bulk_create_stats(db: AsyncSession, stats_list: list[DailyStatCreate]) -> list[DailyStat]:
    objs = [DailyStat(**s.model_dump()) for s in stats_list]
    db.add_all(objs)
    await db.commit()
    for o in objs:
        await db.refresh(o)
    return objs


async def delete_stats(
    db: AsyncSession,
    compte_id: UUID,
    date_from: date | None = None,
    date_to: date | None = None,
) -> int:
    """Delete stats for a compte in a date range (for reimport). Returns count deleted."""
    q = delete(DailyStat).where(DailyStat.compte_id == compte_id)
    if date_from:
        q = q.where(DailyStat.date >= date_from)
    if date_to:
        q = q.where(DailyStat.date <= date_to)
    result = await db.execute(q)
    await db.commit()
    return result.rowcount
