from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.target import Target
from app.schemas.target import TargetCreate


async def list_targets(
    db: AsyncSession,
    *,
    plateforme: str | None = None,
    market: str | None = None,
    niche_id: int | None = None,
    status: str | None = None,
) -> Sequence[Target]:
    q = select(Target).order_by(Target.handle)
    if plateforme:
        q = q.where(Target.plateforme == plateforme)
    if market:
        q = q.where(Target.market == market)
    if niche_id is not None:
        q = q.where(Target.niche_id == niche_id)
    if status:
        q = q.where(Target.status == status)
    result = await db.execute(q)
    return result.scalars().all()


async def get_target(db: AsyncSession, target_id: UUID) -> Target | None:
    return await db.get(Target, target_id)


async def create_target(db: AsyncSession, data: TargetCreate) -> Target:
    t = Target(**data.model_dump())
    db.add(t)
    await db.commit()
    await db.refresh(t)
    return t


async def bulk_create(db: AsyncSession, targets: list[TargetCreate]) -> list[Target]:
    objs = [Target(**t.model_dump()) for t in targets]
    db.add_all(objs)
    await db.commit()
    for o in objs:
        await db.refresh(o)
    return objs


async def update_target(db: AsyncSession, target: Target, data: dict) -> Target:
    for k, v in data.items():
        setattr(target, k, v)
    await db.commit()
    await db.refresh(target)
    return target


async def delete_target(db: AsyncSession, target: Target) -> None:
    await db.delete(target)
    await db.commit()
