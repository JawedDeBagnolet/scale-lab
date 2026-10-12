from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.marche import Marche
from app.models.niche import Niche


async def list_niches(db: AsyncSession) -> Sequence[Niche]:
    result = await db.execute(select(Niche).order_by(Niche.id))
    return result.scalars().all()


async def list_marches(db: AsyncSession) -> Sequence[Marche]:
    result = await db.execute(select(Marche).order_by(Marche.code))
    return result.scalars().all()
