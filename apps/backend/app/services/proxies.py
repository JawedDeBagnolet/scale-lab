from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proxy import Proxy
from app.schemas.proxy import ProxyCreate


async def list_proxies(
    db: AsyncSession,
    *,
    pool: str | None = None,
    status: str | None = None,
    country: str | None = None,
) -> Sequence[Proxy]:
    q = select(Proxy).order_by(Proxy.pool, Proxy.ip)
    if pool:
        q = q.where(Proxy.pool == pool)
    if status:
        q = q.where(Proxy.status == status)
    if country:
        q = q.where(Proxy.country == country)
    result = await db.execute(q)
    return result.scalars().all()


async def get_proxy(db: AsyncSession, proxy_id: UUID) -> Proxy | None:
    return await db.get(Proxy, proxy_id)


async def create_proxy(db: AsyncSession, data: ProxyCreate) -> Proxy:
    p = Proxy(**data.model_dump())
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


async def update_proxy(db: AsyncSession, proxy: Proxy, data: dict) -> Proxy:
    for k, v in data.items():
        setattr(proxy, k, v)
    await db.commit()
    await db.refresh(proxy)
    return proxy


async def delete_proxy(db: AsyncSession, proxy: Proxy) -> None:
    await db.delete(proxy)
    await db.commit()
